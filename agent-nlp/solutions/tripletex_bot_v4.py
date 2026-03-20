"""
NM i AI 2026 - Tripletex AI Accounting Agent (tripletex_bot_v4)

Structured workflow architecture: LLM extracts fields, Python executes API calls.
Eliminates Gemini function calling (MALFORMED_FUNCTION_CALL) entirely.

Architecture: POST /solve -> Gemini extracts {task_type, fields} -> Python API sequence
"""

import asyncio
import base64
import json
import logging
import os
import re
import time
import traceback
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from google import genai
from google.genai import types

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tripletex_bot")

app = FastAPI(title="Tripletex AI Agent", version="4.0")

GCP_PROJECT = os.getenv("GCP_PROJECT", "ai-nm26osl-1779")
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
DEADLINE_SECONDS = 280

try:
    gemini_client = genai.Client(
        vertexai=True,
        project=GCP_PROJECT,
        location=GCP_LOCATION,
    )
except Exception as e:
    log.error("FATAL: Gemini client init failed: %s", e)
    raise

# ---------------------------------------------------------------------------
# Extraction prompt: ONE call, no function calling, just JSON output
# ---------------------------------------------------------------------------
EXTRACTION_PROMPT = """You are a task classifier for a Norwegian accounting system (Tripletex).
Given an accounting task prompt (in any of 7 languages: Norwegian, English, Spanish, Portuguese, Nynorsk, German, French), extract the task type and all field values.

Return ONLY valid JSON. No markdown, no explanation, no code fences.

## Task types (pick exactly one):
- create_customer
- create_employee
- create_employee_with_employment (use when prompt mentions salary/arslonn, employment percentage/stillingsprosent, start date/startdato, or employment/ansettelse)
- create_product
- create_department
- create_project
- create_invoice
- register_payment (existing customer and invoice, register that payment was received)
- create_credit_note (create credit note on existing invoice)
- create_travel_expense
- delete_employee
- delete_travel_expense
- update_customer
- update_employee
- create_contact (kontaktperson for a customer)
- enable_module (enable accounting module for a department)
- unknown (if none of the above match)

## Data format rules:
- Convert dates from DD.MM.YYYY to YYYY-MM-DD
- Convert numbers from "1.000,50" to 1000.50
- Phone: if 8 digits starting with 4 or 9, it's mobile. Otherwise landline.
- Keep names exactly as written in the prompt
- Organization numbers: 9 digits
- If a field is not mentioned, omit it from the JSON

## Response format:
{
  "task_type": "<one of the types above>",
  "fields": {
    <all extracted field values as key-value pairs>
  }
}

## Field names to use:
- name, firstName, lastName, email, phone, mobile, orgNumber
- dateOfBirth, startDate, endDate, address, postalCode, city
- productName, productNumber, price, vatRate (25, 15, 12, or 0)
- departmentName, departmentNumber
- projectName, projectNumber
- invoiceDate, dueDate, customerName, customerOrgNumber
- items (array of {description, quantity, unitPrice, vatRate})
- amount, paymentDate, reason
- title, costs (array of {description, amount, date})
- salary, employmentPercentage
- userType (if admin/kontoadministrator mentioned: "STANDARD", otherwise omit)
- targetEntity (for updates: which entity to find)
- updateFields (for updates: what to change)
"""

# ---------------------------------------------------------------------------
# Common vatType IDs (verified against live API)
# ---------------------------------------------------------------------------
VAT_MAP = {25: 3, 15: 31, 12: 32, 0: 5}


def vat_id(rate: int | float | None) -> int:
    """Map a VAT percentage to Tripletex vatType id."""
    if rate is None:
        return 3  # Default 25%
    return VAT_MAP.get(int(rate), 3)


# ---------------------------------------------------------------------------
# Tripletex API caller (reused from v3, proven reliable)
# ---------------------------------------------------------------------------
async def tx(
    client: httpx.AsyncClient,
    base_url: str,
    token: str,
    method: str,
    path: str,
    body: dict | None = None,
    params: dict | None = None,
) -> dict[str, Any]:
    """Execute a Tripletex API call. Returns parsed response."""
    url = f"{base_url}{path}"
    auth = httpx.BasicAuth(username="0", password=token)

    try:
        response = await client.request(
            method=method,
            url=url,
            json=body,
            params=params,
            auth=auth,
            headers={"Content-Type": "application/json; charset=utf-8"} if body else {},
            timeout=30.0,
        )

        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError):
            data = {"raw": response.text[:2000]}

        success = 200 <= response.status_code < 300
        result = {"status_code": response.status_code, "success": success}

        if success:
            if isinstance(data, dict) and "value" in data:
                result["data"] = data["value"]
            elif isinstance(data, dict) and "values" in data:
                result["data"] = data["values"]
            else:
                result["data"] = data
        else:
            result["error"] = data
            log.warning("API %s %s -> %d: %s", method, path, response.status_code, str(data)[:300])

        return result

    except httpx.TimeoutException:
        return {"error": "Timeout 30s", "status_code": 408, "success": False}
    except Exception as e:
        log.error("API error %s %s: %s", method, path, e)
        return {"error": str(e), "status_code": 500, "success": False}


# ---------------------------------------------------------------------------
# Field extraction via Gemini (ONE call, no function calling)
# ---------------------------------------------------------------------------
async def extract_fields(prompt: str, file_texts: list[str]) -> dict:
    """Use Gemini to extract task_type and fields from the prompt."""
    user_content = f"Task prompt:\n{prompt}"
    if file_texts:
        user_content += "\n\nAttached file content:\n" + "\n---\n".join(file_texts)

    try:
        response = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model=GEMINI_MODEL,
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=EXTRACTION_PROMPT,
                temperature=0.0,
                max_output_tokens=4096,
            ),
        )

        text = response.text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)

        result = json.loads(text)
        log.info("Extracted: task_type=%s, fields=%s",
                 result.get("task_type"), json.dumps(result.get("fields", {}), ensure_ascii=False)[:200])
        return result

    except json.JSONDecodeError as e:
        log.error("JSON parse error from Gemini: %s. Raw: %s", e, text[:500] if 'text' in dir() else "N/A")
        return {"task_type": "unknown", "fields": {}, "error": str(e)}
    except Exception as e:
        log.error("Gemini extraction error: %s", e)
        return {"task_type": "unknown", "fields": {}, "error": str(e)}


# ---------------------------------------------------------------------------
# Task executors: each is a deterministic API sequence
# ---------------------------------------------------------------------------

async def exec_create_customer(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    body = {"name": f.get("name", ""), "isCustomer": True}
    if f.get("email"): body["email"] = f["email"]
    if f.get("orgNumber"): body["organizationNumber"] = f["orgNumber"]
    if f.get("phone"): body["phoneNumber"] = f["phone"]
    if f.get("mobile"): body["phoneNumberMobile"] = f["mobile"]
    if f.get("invoiceEmail"): body["invoiceEmail"] = f["invoiceEmail"]
    if f.get("address"):
        body["postalAddress"] = {
            "addressLine1": f.get("address", ""),
            "postalCode": f.get("postalCode", ""),
            "city": f.get("city", ""),
        }
    return await tx(c, base, tok, "POST", "/customer", body)


async def exec_create_employee(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    # Ensure department exists
    dept_id = None
    dept_r = await tx(c, base, tok, "GET", "/department", params={"count": 1})
    if dept_r.get("success") and dept_r.get("data"):
        depts = dept_r["data"] if isinstance(dept_r["data"], list) else [dept_r["data"]]
        if depts:
            dept_id = depts[0]["id"]

    if not dept_id:
        dept_r = await tx(c, base, tok, "POST", "/department", {"name": "Avdeling", "departmentNumber": 1})
        if dept_r.get("success"):
            dept_id = dept_r["data"]["id"]

    user_type = f.get("userType", "NO_ACCESS")
    body = {
        "firstName": f.get("firstName", ""),
        "lastName": f.get("lastName", ""),
        "department": {"id": dept_id},
        "userType": user_type,
    }
    if f.get("email"): body["email"] = f["email"]
    elif user_type in ("STANDARD", "EXTENDED"):
        body["email"] = f"{f.get('firstName', 'emp').lower()}@company.no"
    if f.get("mobile"): body["phoneNumberMobile"] = f["mobile"]
    if f.get("phone"): body["phoneNumber"] = f["phone"]
    if f.get("dateOfBirth"): body["dateOfBirth"] = f["dateOfBirth"]
    if f.get("bankAccountNumber"): body["bankAccountNumber"] = f["bankAccountNumber"]

    return await tx(c, base, tok, "POST", "/employee", body)


async def exec_create_employee_with_employment(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    # Step 1: department
    dept_id = None
    dept_r = await tx(c, base, tok, "GET", "/department", params={"count": 1})
    if dept_r.get("success") and dept_r.get("data"):
        depts = dept_r["data"] if isinstance(dept_r["data"], list) else [dept_r["data"]]
        if depts:
            dept_id = depts[0]["id"]
    if not dept_id:
        dept_r = await tx(c, base, tok, "POST", "/department", {"name": "Avdeling", "departmentNumber": 1})
        if dept_r.get("success"):
            dept_id = dept_r["data"]["id"]

    # Step 2: employee with dateOfBirth (REQUIRED for employment)
    user_type = f.get("userType", "STANDARD")
    email = f.get("email") or f"{f.get('firstName', 'emp').lower()}@company.no"
    emp_body = {
        "firstName": f.get("firstName", ""),
        "lastName": f.get("lastName", ""),
        "department": {"id": dept_id},
        "userType": user_type,
        "email": email,
        "dateOfBirth": f.get("dateOfBirth", "1990-01-15"),
    }
    if f.get("mobile"): emp_body["phoneNumberMobile"] = f["mobile"]

    emp_r = await tx(c, base, tok, "POST", "/employee", emp_body)
    if not emp_r.get("success"):
        return emp_r
    emp_id = emp_r["data"]["id"]

    # Step 3: employment (division NOT required)
    start_date = f.get("startDate", time.strftime("%Y-%m-%d"))
    employment_body = {
        "employee": {"id": emp_id},
        "startDate": start_date,
        "isMainEmployer": True,
    }
    empl_r = await tx(c, base, tok, "POST", "/employee/employment", employment_body)
    if not empl_r.get("success"):
        return empl_r
    employment_id = empl_r["data"]["id"]

    # Step 4: employment details
    details_body = {
        "employment": {"id": employment_id},
        "date": start_date,
        "employmentType": "ORDINARY",
    }
    pct = f.get("employmentPercentage")
    if pct is not None:
        details_body["percentageOfFullTimeEquivalent"] = float(pct)
    else:
        details_body["percentageOfFullTimeEquivalent"] = 100.0

    salary = f.get("salary")
    if salary is not None:
        details_body["annualSalary"] = float(salary)

    return await tx(c, base, tok, "POST", "/employee/employment/details", details_body)


async def exec_create_product(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    body = {"name": f.get("productName") or f.get("name", "")}
    if f.get("productNumber"): body["number"] = f["productNumber"]
    if f.get("price") is not None:
        body["priceExcludingVatCurrency"] = float(f["price"])
    body["vatType"] = {"id": vat_id(f.get("vatRate"))}
    return await tx(c, base, tok, "POST", "/product", body)


async def exec_create_department(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    body = {"name": f.get("departmentName") or f.get("name", "")}
    if f.get("departmentNumber") is not None:
        body["departmentNumber"] = int(f["departmentNumber"])
    return await tx(c, base, tok, "POST", "/department", body)


async def exec_create_project(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    # Get admin employee for projectManager
    whoami = await tx(c, base, tok, "GET", "/token/session/>whoAmI")
    pm_id = whoami.get("data", {}).get("employee", {}).get("id")

    body = {
        "name": f.get("projectName") or f.get("name", ""),
        "projectManager": {"id": pm_id},
        "isInternal": True,
        "startDate": f.get("startDate", time.strftime("%Y-%m-%d")),
    }
    if f.get("projectNumber"): body["number"] = f["projectNumber"]
    if f.get("customerName"):
        # Link to customer: create customer first
        cust_r = await exec_create_customer(c, base, tok, {"name": f["customerName"], "orgNumber": f.get("customerOrgNumber")})
        if cust_r.get("success"):
            body["customer"] = {"id": cust_r["data"]["id"]}
            body["isInternal"] = False

    return await tx(c, base, tok, "POST", "/project", body)


async def exec_create_invoice(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    # Step 1: Create customer
    cust_body = {"name": f.get("customerName", ""), "isCustomer": True}
    if f.get("customerOrgNumber"): cust_body["organizationNumber"] = f["customerOrgNumber"]
    cust_r = await tx(c, base, tok, "POST", "/customer", cust_body)
    if not cust_r.get("success"):
        return cust_r
    cust_id = cust_r["data"]["id"]

    # Step 2: Register bank account on account 1920
    acct_r = await tx(c, base, tok, "GET", "/ledger/account", params={"number": 1920})
    if acct_r.get("success") and acct_r.get("data"):
        accts = acct_r["data"] if isinstance(acct_r["data"], list) else [acct_r["data"]]
        if accts:
            acct_id = accts[0]["id"]
            await tx(c, base, tok, "PUT", f"/ledger/account/{acct_id}", {
                "bankAccountNumber": "19201234568",
                "bankAccountCountry": {"id": 161},
                "currency": {"id": 1},
            })

    # Step 3: Build order lines
    today = f.get("invoiceDate", time.strftime("%Y-%m-%d"))
    due = f.get("dueDate", today)
    items = f.get("items", [])
    if not items:
        # Single line item from flat fields
        items = [{
            "description": f.get("description", "Tjenester"),
            "quantity": 1,
            "unitPrice": float(f.get("amount") or f.get("price", 0)),
            "vatRate": f.get("vatRate", 25),
        }]

    order_lines = []
    for item in items:
        line = {
            "description": item.get("description", ""),
            "count": float(item.get("quantity", 1)),
            "unitPriceExcludingVatCurrency": float(item.get("unitPrice", 0)),
            "vatType": {"id": vat_id(item.get("vatRate"))},
        }
        order_lines.append(line)

    # Step 4: Create invoice with inline order
    invoice_body = {
        "invoiceDate": today,
        "invoiceDueDate": due,
        "customer": {"id": cust_id},
        "orders": [{
            "customer": {"id": cust_id},
            "orderDate": today,
            "deliveryDate": today,
            "orderLines": order_lines,
        }],
    }
    return await tx(c, base, tok, "POST", "/invoice", invoice_body)


async def exec_register_payment(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    # Step 1: Find customer
    cust_name = f.get("customerName", "")
    cust_r = await tx(c, base, tok, "GET", "/customer", params={"name": cust_name, "count": 5})
    if not cust_r.get("success") or not cust_r.get("data"):
        return {"success": False, "error": f"Customer '{cust_name}' not found"}
    customers = cust_r["data"] if isinstance(cust_r["data"], list) else [cust_r["data"]]
    cust_id = customers[0]["id"]

    # Step 2: Find invoice
    inv_r = await tx(c, base, tok, "GET", "/invoice", params={
        "customerId": cust_id,
        "invoiceDateFrom": "2020-01-01",
        "invoiceDateTo": "2030-12-31",
        "count": 5,
    })
    if not inv_r.get("success") or not inv_r.get("data"):
        return {"success": False, "error": f"No invoice for customer {cust_id}"}
    invoices = inv_r["data"] if isinstance(inv_r["data"], list) else [inv_r["data"]]
    inv = invoices[0]
    inv_id = inv["id"]
    amount = f.get("amount") or inv.get("amount", 0)

    # Step 3: Get payment type
    pt_r = await tx(c, base, tok, "GET", "/invoice/paymentType")
    pt_id = 1
    if pt_r.get("success") and pt_r.get("data"):
        pts = pt_r["data"] if isinstance(pt_r["data"], list) else [pt_r["data"]]
        if pts:
            pt_id = pts[0]["id"]

    # Step 4: Register payment
    pay_date = f.get("paymentDate", time.strftime("%Y-%m-%d"))
    return await tx(c, base, tok, "PUT", f"/invoice/{inv_id}/:payment", params={
        "paymentDate": pay_date,
        "paidAmount": str(amount),
        "paidAmountCurrency": str(amount),
        "paymentTypeId": str(pt_id),
    })


async def exec_create_credit_note(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    # Step 1: Find customer
    cust_name = f.get("customerName", "")
    cust_r = await tx(c, base, tok, "GET", "/customer", params={"name": cust_name, "count": 5})
    if not cust_r.get("success") or not cust_r.get("data"):
        return {"success": False, "error": f"Customer '{cust_name}' not found"}
    customers = cust_r["data"] if isinstance(cust_r["data"], list) else [cust_r["data"]]
    cust_id = customers[0]["id"]

    # Step 2: Find invoice
    inv_r = await tx(c, base, tok, "GET", "/invoice", params={
        "customerId": cust_id,
        "invoiceDateFrom": "2020-01-01",
        "invoiceDateTo": "2030-12-31",
        "count": 5,
    })
    if not inv_r.get("success") or not inv_r.get("data"):
        return {"success": False, "error": f"No invoice for customer {cust_id}"}
    invoices = inv_r["data"] if isinstance(inv_r["data"], list) else [inv_r["data"]]
    inv_id = invoices[0]["id"]

    # Step 3: Create credit note
    date = f.get("date", time.strftime("%Y-%m-%d"))
    reason = f.get("reason", "Kreditering")
    return await tx(c, base, tok, "PUT", f"/invoice/{inv_id}/:createCreditNote", params={
        "date": date,
        "comment": reason,
    })


async def exec_create_travel_expense(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    # Step 1: Create employee
    emp_r = await exec_create_employee(c, base, tok, {
        "firstName": f.get("firstName", ""),
        "lastName": f.get("lastName", ""),
        "email": f.get("email"),
        "mobile": f.get("mobile"),
    })
    if not emp_r.get("success"):
        return emp_r
    emp_id = emp_r["data"]["id"]

    # Step 2: Get payment types
    pt_r = await tx(c, base, tok, "GET", "/travelExpense/paymentType")
    pt_id = 1
    if pt_r.get("success") and pt_r.get("data"):
        pts = pt_r["data"] if isinstance(pt_r["data"], list) else [pt_r["data"]]
        if pts:
            pt_id = pts[0]["id"]

    # Step 3: Create travel expense (no costs inline)
    te_body = {
        "employee": {"id": emp_id},
        "title": f.get("title", "Reiseregning"),
    }
    te_r = await tx(c, base, tok, "POST", "/travelExpense", te_body)
    if not te_r.get("success"):
        return te_r
    te_id = te_r["data"]["id"]

    # Step 4: Add each cost separately
    costs = f.get("costs", [])
    last_result = te_r
    for cost in costs:
        cost_body = {
            "travelExpense": {"id": te_id},
            "paymentType": {"id": pt_id},
            "currency": {"id": 1},
            "amountCurrencyIncVat": float(cost.get("amount", 0)),
            "date": cost.get("date", time.strftime("%Y-%m-%d")),
            "comments": cost.get("description", ""),
        }
        last_result = await tx(c, base, tok, "POST", "/travelExpense/cost", cost_body)

    return last_result


async def exec_delete_employee(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    # Find employee
    params = {}
    if f.get("firstName"): params["firstName"] = f["firstName"]
    if f.get("lastName"): params["lastName"] = f["lastName"]
    params["count"] = 5
    emp_r = await tx(c, base, tok, "GET", "/employee", params=params)
    if not emp_r.get("success") or not emp_r.get("data"):
        return {"success": False, "error": "Employee not found"}
    emps = emp_r["data"] if isinstance(emp_r["data"], list) else [emp_r["data"]]
    emp_id = emps[0]["id"]
    return await tx(c, base, tok, "DELETE", f"/employee/{emp_id}")


async def exec_delete_travel_expense(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    # Find travel expense (might need to find employee first)
    if f.get("firstName"):
        emp_r = await tx(c, base, tok, "GET", "/employee", params={
            "firstName": f["firstName"], "lastName": f.get("lastName", ""), "count": 5
        })
        if emp_r.get("success") and emp_r.get("data"):
            emps = emp_r["data"] if isinstance(emp_r["data"], list) else [emp_r["data"]]
            te_r = await tx(c, base, tok, "GET", "/travelExpense", params={"employeeId": emps[0]["id"]})
            if te_r.get("success") and te_r.get("data"):
                tes = te_r["data"] if isinstance(te_r["data"], list) else [te_r["data"]]
                return await tx(c, base, tok, "DELETE", f"/travelExpense/{tes[0]['id']}")
    return {"success": False, "error": "Travel expense not found"}


async def exec_update_customer(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    target = f.get("targetEntity") or f.get("name", "")
    cust_r = await tx(c, base, tok, "GET", "/customer", params={"name": target, "count": 5})
    if not cust_r.get("success") or not cust_r.get("data"):
        return {"success": False, "error": f"Customer '{target}' not found"}
    customers = cust_r["data"] if isinstance(cust_r["data"], list) else [cust_r["data"]]
    cust_id = customers[0]["id"]

    updates = f.get("updateFields", {})
    body = {}
    if updates.get("email"): body["email"] = updates["email"]
    if updates.get("phone"): body["phoneNumber"] = updates["phone"]
    if updates.get("mobile"): body["phoneNumberMobile"] = updates["mobile"]
    if updates.get("name"): body["name"] = updates["name"]
    if updates.get("address"):
        body["postalAddress"] = {"addressLine1": updates["address"]}

    if not body:
        return {"success": True, "data": {"message": "No fields to update"}}
    return await tx(c, base, tok, "PUT", f"/customer/{cust_id}", body)


async def exec_update_employee(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    target_first = f.get("firstName", "")
    target_last = f.get("lastName", "")
    emp_r = await tx(c, base, tok, "GET", "/employee", params={
        "firstName": target_first, "lastName": target_last, "count": 5
    })
    if not emp_r.get("success") or not emp_r.get("data"):
        return {"success": False, "error": f"Employee '{target_first} {target_last}' not found"}
    emps = emp_r["data"] if isinstance(emp_r["data"], list) else [emp_r["data"]]
    emp_id = emps[0]["id"]

    updates = f.get("updateFields", {})
    body = {}
    if updates.get("email"): body["email"] = updates["email"]
    if updates.get("phone"): body["phoneNumber"] = updates["phone"]
    if updates.get("mobile"): body["phoneNumberMobile"] = updates["mobile"]

    if not body:
        return {"success": True, "data": {"message": "No fields to update"}}
    return await tx(c, base, tok, "PUT", f"/employee/{emp_id}", body)


async def exec_create_contact(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    # Find or create customer
    cust_name = f.get("customerName", "")
    cust_r = await tx(c, base, tok, "GET", "/customer", params={"name": cust_name, "count": 5})
    if cust_r.get("success") and cust_r.get("data"):
        customers = cust_r["data"] if isinstance(cust_r["data"], list) else [cust_r["data"]]
        cust_id = customers[0]["id"]
    else:
        cust_r = await tx(c, base, tok, "POST", "/customer", {"name": cust_name, "isCustomer": True})
        if not cust_r.get("success"):
            return cust_r
        cust_id = cust_r["data"]["id"]

    body = {
        "firstName": f.get("contactFirstName") or f.get("firstName", ""),
        "lastName": f.get("contactLastName") or f.get("lastName", ""),
        "customer": {"id": cust_id},
    }
    if f.get("contactEmail") or f.get("email"):
        body["email"] = f.get("contactEmail") or f["email"]
    if f.get("contactMobile") or f.get("mobile"):
        body["phoneNumberMobile"] = f.get("contactMobile") or f["mobile"]

    return await tx(c, base, tok, "POST", "/contact", body)


# ---------------------------------------------------------------------------
# Task router
# ---------------------------------------------------------------------------
TASK_EXECUTORS = {
    "create_customer": exec_create_customer,
    "create_employee": exec_create_employee,
    "create_employee_with_employment": exec_create_employee_with_employment,
    "create_product": exec_create_product,
    "create_department": exec_create_department,
    "create_project": exec_create_project,
    "create_invoice": exec_create_invoice,
    "register_payment": exec_register_payment,
    "create_credit_note": exec_create_credit_note,
    "create_travel_expense": exec_create_travel_expense,
    "delete_employee": exec_delete_employee,
    "delete_travel_expense": exec_delete_travel_expense,
    "update_customer": exec_update_customer,
    "update_employee": exec_update_employee,
    "create_contact": exec_create_contact,
}


async def run_structured(
    prompt: str,
    files: list[dict] | None,
    base_url: str,
    session_token: str,
) -> dict[str, Any]:
    """Run the structured workflow: extract fields then execute deterministic API sequence."""
    t0 = time.time()

    # Decode files for text extraction
    file_texts = []
    file_parts = []
    if files:
        for f in files:
            content_b64 = f.get("content_base64", "")
            mime = f.get("mime_type", "")
            fname = f.get("filename", "")
            if content_b64:
                try:
                    raw = base64.b64decode(content_b64)
                    file_texts.append(f"[File: {fname}, {mime}, {len(raw)} bytes]")
                    file_parts.append({"raw": raw, "mime": mime, "name": fname})
                except Exception as e:
                    file_texts.append(f"[File {fname}: decode error: {e}]")

    # Step 1: Extract task type and fields
    extraction = await extract_fields(prompt, file_texts)
    task_type = extraction.get("task_type", "unknown")
    fields = extraction.get("fields", {})

    elapsed_extract = time.time() - t0
    log.info("Task type: %s (extraction took %.1fs)", task_type, elapsed_extract)

    # Step 2: Route to executor
    executor = TASK_EXECUTORS.get(task_type)
    if not executor:
        log.warning("Unknown task type '%s'. Fields: %s", task_type, json.dumps(fields, ensure_ascii=False)[:300])
        return {
            "status": "completed",
            "task_type": task_type,
            "note": "unknown task type, no executor",
            "elapsed_seconds": time.time() - t0,
        }

    # Step 3: Execute
    async with httpx.AsyncClient() as client:
        try:
            result = await executor(client, base_url, session_token, fields)
            elapsed = time.time() - t0
            log.info("Executor %s: success=%s, elapsed=%.1fs",
                     task_type, result.get("success"), elapsed)
            return {
                "status": "completed",
                "task_type": task_type,
                "success": result.get("success", False),
                "elapsed_seconds": elapsed,
            }
        except Exception as e:
            log.error("Executor %s crashed: %s\n%s", task_type, e, traceback.format_exc())
            return {
                "status": "completed",
                "task_type": task_type,
                "error": str(e),
                "elapsed_seconds": time.time() - t0,
            }


# ---------------------------------------------------------------------------
# FastAPI endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "version": "v4", "model": GEMINI_MODEL}


@app.post("/solve")
async def solve(request: Request):
    try:
        body = await request.json()
    except Exception as e:
        log.error("Invalid request body: %s", e)
        return JSONResponse({"status": "completed"})

    prompt = body.get("prompt", "")
    files = body.get("files", [])
    creds = body.get("tripletex_credentials", {})
    base_url = creds.get("base_url", "")
    session_token = creds.get("session_token", "")

    if not prompt or not base_url or not session_token:
        log.error("Missing fields: prompt=%d, base_url=%d, token=%d",
                  len(prompt), len(base_url), len(session_token))
        return JSONResponse({"status": "completed"})

    log.info("=== SOLVE v4: prompt_len=%d, files=%d ===", len(prompt), len(files))
    log.info("Prompt: %s", prompt[:300])

    try:
        result = await run_structured(
            prompt=prompt, files=files,
            base_url=base_url, session_token=session_token,
        )
        log.info("Result: task=%s, success=%s, elapsed=%.1fs",
                 result.get("task_type"), result.get("success"), result.get("elapsed_seconds", 0))
        return JSONResponse({"status": "completed"})
    except Exception as e:
        log.error("CRASH: %s\n%s", e, traceback.format_exc())
        return JSONResponse({"status": "completed"})


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
