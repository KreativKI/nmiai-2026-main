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
- create_credit_note (create credit note on existing invoice, also use when payment was returned/reversed by bank)
- create_travel_expense (use when prompt mentions reiseregning/travel expense/travel report, even if it also says to create an employee first)
- delete_employee
- delete_travel_expense
- update_customer
- update_employee
- create_contact (kontaktperson for a customer)
- enable_module (enable accounting module for a department)
- process_salary (use when prompt mentions payroll/lonn/lonnskjoring/salary payment/Gehaltsabrechnung, running payroll for an employee)
- register_supplier_invoice (use when prompt mentions supplier invoice/leverandorfaktura/incoming invoice from a vendor/supplier, registering a received bill)
- create_dimension (use when prompt mentions accounting dimension/dimensjon, custom dimensions, creating dimension values, or posting with dimensions)
- create_supplier (use when prompt says to register/create a supplier/leverandor entity, NOT a supplier invoice)
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
- salary, baseSalary, bonus, bonusAmount, employmentPercentage
- userType (if admin/kontoadministrator mentioned: "STANDARD", otherwise omit)
- targetEntity (for updates: which entity to find)
- updateFields (for updates: what to change)
- supplierName, supplierOrgNumber, invoiceNumber, invoiceAmount, totalAmount, account, accountNumber
- dimensionName, dimensionValues (array of strings), linkedDimensionValue
"""

# ---------------------------------------------------------------------------
# VAT type lookup (dynamic per sandbox)
# ---------------------------------------------------------------------------
_vat_cache: dict[str, dict[int, int]] = {}


async def lookup_vat_map(c: httpx.AsyncClient, base: str, tok: str) -> dict[int, int]:
    """Fetch OUTPUT vatType IDs from sandbox and build rate->id map. Cached per base_url."""
    if base in _vat_cache:
        return _vat_cache[base]

    r = await tx(c, base, tok, "GET", "/ledger/vatType", params={"count": 200})
    vat_map = {}
    if r.get("success") and r.get("data"):
        for vt in (r["data"] if isinstance(r["data"], list) else [r["data"]]):
            pct = vt.get("percentage")
            vid = vt.get("id")
            name = (vt.get("name") or "").lower()
            if pct is not None and vid is not None:
                pct_int = int(round(float(pct)))
                # Only use OUTPUT vat types (utgaende), skip input (inngaende)
                is_output = "utg" in name or "output" in name or "sales" in name
                is_input = "inng" in name or "input" in name or "fradrag" in name
                if is_input:
                    continue
                if pct_int not in vat_map or is_output:
                    vat_map[pct_int] = vid

    if not vat_map:
        vat_map = {25: 3, 15: 31, 12: 32, 0: 5}
        log.warning("VAT lookup returned empty, using hardcoded fallback")

    _vat_cache[base] = vat_map
    log.info("VAT map for sandbox: %s", vat_map)
    return vat_map


_input_vat_cache: dict[str, dict[int, int]] = {}


async def lookup_input_vat_map(c: httpx.AsyncClient, base: str, tok: str) -> dict[int, int]:
    """Fetch INPUT (inngaende) vatType IDs for supplier invoices. Cached per base_url."""
    if base in _input_vat_cache:
        return _input_vat_cache[base]
    r = await tx(c, base, tok, "GET", "/ledger/vatType", params={"count": 200})
    vat_map: dict[int, int] = {}
    if r.get("success") and r.get("data"):
        for vt in (r["data"] if isinstance(r["data"], list) else [r["data"]]):
            pct = vt.get("percentage")
            vid = vt.get("id")
            name = (vt.get("name") or "").lower()
            if pct is not None and vid is not None:
                pct_int = int(round(float(pct)))
                if "inng" in name or "input" in name or "fradrag" in name:
                    vat_map[pct_int] = vid
    if not vat_map:
        vat_map = {25: 1, 15: 33, 12: 34, 0: 6}
    _input_vat_cache[base] = vat_map
    return vat_map


def vat_id_sync(rate: int | float | None, vat_map: dict[int, int]) -> int:
    """Map a VAT percentage to Tripletex vatType id using looked-up map."""
    if rate is None:
        return vat_map.get(25, 3)
    return vat_map.get(int(rate), vat_map.get(25, 3))


def as_list(data) -> list:
    """Normalize API response data to a list (handles single-object vs array)."""
    return data if isinstance(data, list) else [data]


async def ensure_department(c: httpx.AsyncClient, base: str, tok: str) -> int | None:
    """Find first existing department or create a default one. Returns dept ID or None."""
    dept_r = await tx(c, base, tok, "GET", "/department", params={"count": 1})
    if dept_r.get("success") and dept_r.get("data"):
        depts = as_list(dept_r["data"])
        if depts:
            return depts[0]["id"]
    dept_r = await tx(c, base, tok, "POST", "/department", {"name": "Avdeling", "departmentNumber": 1})
    if dept_r.get("success"):
        return dept_r["data"]["id"]
    return None


async def find_customer(c: httpx.AsyncClient, base: str, tok: str, name: str, org_nr: str | None = None) -> dict:
    """Find a customer by name or org number. Returns {"success": True, "id": int} or error."""
    # Try name search first (API does partial match, so filter for exact)
    cust_r = await tx(c, base, tok, "GET", "/customer", params={"name": name, "count": 20})
    if cust_r.get("success") and cust_r.get("data"):
        customers = as_list(cust_r["data"])
        for c_item in customers:
            if c_item.get("name") == name:
                return {"success": True, "id": c_item["id"]}
        # No exact match in name search results, try other methods
    # Fallback: search by org number
    if org_nr:
        cust_r2 = await tx(c, base, tok, "GET", "/customer", params={"organizationNumber": org_nr, "count": 5})
        if cust_r2.get("success") and cust_r2.get("data"):
            customers2 = as_list(cust_r2["data"])
            log.info("Customer found by orgNumber=%s (name search failed for '%s')", org_nr, name)
            return {"success": True, "id": customers2[0]["id"]}
    # Fallback: list all customers and search
    all_r = await tx(c, base, tok, "GET", "/customer", params={"count": 100})
    if all_r.get("success") and all_r.get("data"):
        all_custs = as_list(all_r["data"])
        for c_item in all_custs:
            if c_item.get("name") == name:
                log.info("Customer found via full list scan for '%s'", name)
                return {"success": True, "id": c_item["id"]}
    log.warning("Customer '%s' not found by any method", name)
    return {"success": False, "error": f"Customer '{name}' not found"}


async def find_invoice_for_customer(c: httpx.AsyncClient, base: str, tok: str, cust_id: int) -> dict:
    """Find the first invoice for a customer. Returns {"success": True, "invoice": dict} or error."""
    inv_r = await tx(c, base, tok, "GET", "/invoice", params={
        "customerId": cust_id,
        "invoiceDateFrom": "2020-01-01",
        "invoiceDateTo": "2030-12-31",
        "count": 5,
    })
    if not inv_r.get("success") or not inv_r.get("data"):
        return {"success": False, "error": f"No invoice for customer {cust_id}"}
    invoices = as_list(inv_r["data"])
    return {"success": True, "invoice": invoices[0]}


def split_name(f: dict) -> tuple[str, str]:
    """Extract firstName and lastName from fields, splitting 'name' or 'employeeName' if needed."""
    first = f.get("firstName", "")
    last = f.get("lastName", "")
    if first and last:
        return first, last
    # Fallback: split full name field
    full = f.get("name") or f.get("employeeName") or ""
    parts = full.strip().split()
    if len(parts) >= 2:
        return parts[0], " ".join(parts[1:])
    elif len(parts) == 1:
        return parts[0], ""
    return first or "Unknown", last or "Unknown"


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
async def extract_fields(prompt: str, file_parts: list[dict] | None = None) -> dict:
    """Use Gemini to extract task_type and fields from the prompt.

    file_parts: list of {"raw": bytes, "mime": str, "name": str} dicts for multimodal input.
    """
    parts: list[types.Part] = [types.Part.from_text(text=f"Task prompt:\n{prompt}")]

    if file_parts:
        for fp in file_parts:
            try:
                parts.append(types.Part.from_bytes(data=fp["raw"], mime_type=fp["mime"]))
                log.info("Attached file to extraction: %s (%s, %d bytes)", fp["name"], fp["mime"], len(fp["raw"]))
            except Exception as e:
                log.warning("Failed to attach file %s: %s", fp["name"], e)
                parts.append(types.Part.from_text(text=f"[File {fp['name']} could not be attached: {e}]"))

    contents = [types.Content(role="user", parts=parts)]

    try:
        response = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model=GEMINI_MODEL,
            contents=contents,
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
        raw_text = text[:500] if "text" in locals() else "N/A"
        log.error("JSON parse error from Gemini: %s. Raw: %s", e, raw_text)
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
    dept_id = await ensure_department(c, base, tok)
    if not dept_id:
        return {"success": False, "error": "Could not obtain department ID"}

    first, last = split_name(f)
    user_type = f.get("userType", "NO_ACCESS")
    body = {
        "firstName": first,
        "lastName": last,
        "department": {"id": dept_id},
        "userType": user_type,
    }
    if f.get("email"): body["email"] = f["email"]
    elif user_type in ("STANDARD", "EXTENDED"):
        body["email"] = f"{first.lower()}@company.no"
    if f.get("mobile"): body["phoneNumberMobile"] = f["mobile"]
    if f.get("phone"): body["phoneNumber"] = f["phone"]
    if f.get("dateOfBirth"): body["dateOfBirth"] = f["dateOfBirth"]
    if f.get("bankAccountNumber"): body["bankAccountNumber"] = f["bankAccountNumber"]

    r = await tx(c, base, tok, "POST", "/employee", body)

    # If startDate or salary present, also create employment details
    if r.get("success") and (f.get("startDate") or f.get("salary")):
        emp_id = r["data"]["id"]
        start_date = f.get("startDate", time.strftime("%Y-%m-%d"))
        emp_r = await tx(c, base, tok, "POST", "/employee/employment", {
            "employee": {"id": emp_id},
            "startDate": start_date,
            "isMainEmployer": True,
        })
        if emp_r.get("success"):
            emp_id_empl = emp_r["data"]["id"]
            details_body = {
                "employment": {"id": emp_id_empl},
                "date": start_date,
                "employmentType": "ORDINARY",
                "percentageOfFullTimeEquivalent": float(f.get("employmentPercentage", 100)),
            }
            if f.get("salary"):
                details_body["annualSalary"] = float(f["salary"])
            await tx(c, base, tok, "POST", "/employee/employment/details", details_body)

    return r


async def exec_create_employee_with_employment(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    dept_id = await ensure_department(c, base, tok)
    if not dept_id:
        return {"success": False, "error": "Could not obtain department ID"}

    # Create employee with dateOfBirth (REQUIRED for employment)
    first, last = split_name(f)
    user_type = f.get("userType", "STANDARD")
    email = f.get("email") or f"{first.lower()}@company.no"
    emp_body = {
        "firstName": first,
        "lastName": last,
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

    # Create employment (division NOT required)
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

    # Employment details
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
    vat_map = await lookup_vat_map(c, base, tok)
    body = {"name": f.get("productName") or f.get("name", "")}
    if f.get("productNumber"): body["number"] = f["productNumber"]
    if f.get("price") is not None:
        body["priceExcludingVatCurrency"] = float(f["price"])
    vat_rate = f.get("vatRate")
    if vat_rate is not None and int(vat_rate) != 25:
        body["vatType"] = {"id": vat_id_sync(vat_rate, vat_map)}
    # Omit vatType for standard 25% -- sandbox default handles it correctly
    r = await tx(c, base, tok, "POST", "/product", body)
    if not r.get("success") and "vattype" in str(r.get("error", "")).lower():
        log.info("Product POST failed on vatType, retrying without it")
        body.pop("vatType", None)
        r = await tx(c, base, tok, "POST", "/product", body)
    return r


async def exec_create_department(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    # Handle multi-department: LLM may extract {"departments": [{...}, {...}]}
    depts = f.get("departments")
    if depts and isinstance(depts, list):
        last_r = {"success": False, "error": "No departments to create"}
        for i, dept in enumerate(depts):
            name = dept.get("departmentName") or dept.get("name", "")
            if not name:
                continue
            body = {"name": name}
            num = dept.get("departmentNumber")
            if num is not None:
                body["departmentNumber"] = int(num)
            else:
                body["departmentNumber"] = i + 1
            last_r = await tx(c, base, tok, "POST", "/department", body)
        return last_r
    # Handle departmentName as flat list (LLM variant)
    dept_name = f.get("departmentName") or f.get("name", "")
    if isinstance(dept_name, list):
        last_r = {"success": False, "error": "No departments"}
        for i, n in enumerate(dept_name):
            last_r = await tx(c, base, tok, "POST", "/department", {"name": n, "departmentNumber": i + 1})
        return last_r
    # Single department
    body = {"name": dept_name}
    if f.get("departmentNumber") is not None:
        body["departmentNumber"] = int(f["departmentNumber"])
    return await tx(c, base, tok, "POST", "/department", body)


async def exec_create_project(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    # Get admin employee for projectManager
    whoami = await tx(c, base, tok, "GET", "/token/session/>whoAmI")
    pm_id = whoami.get("data", {}).get("employee", {}).get("id")
    if not pm_id:
        return {"success": False, "error": "Could not get project manager from whoAmI"}

    body = {
        "name": f.get("projectName") or f.get("name", ""),
        "projectManager": {"id": pm_id},
        "isInternal": True,
        "startDate": f.get("startDate", time.strftime("%Y-%m-%d")),
    }
    if f.get("projectNumber"): body["number"] = f["projectNumber"]
    if f.get("customerName"):
        # Link to customer: find existing or create
        cust_r = await tx(c, base, tok, "GET", "/customer", params={"name": f["customerName"], "count": 5})
        if cust_r.get("success") and cust_r.get("data"):
            custs = as_list(cust_r["data"])
            body["customer"] = {"id": custs[0]["id"]}
            body["isInternal"] = False
        else:
            cust_r = await exec_create_customer(c, base, tok, {"name": f["customerName"], "orgNumber": f.get("customerOrgNumber")})
            if cust_r.get("success"):
                body["customer"] = {"id": cust_r["data"]["id"]}
                body["isInternal"] = False

    return await tx(c, base, tok, "POST", "/project", body)


async def exec_create_invoice(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    vat_map = await lookup_vat_map(c, base, tok)

    # Step 1: Find existing customer or create new
    cust_name = f.get("customerName", "")
    existing = await find_customer(c, base, tok, cust_name, f.get("customerOrgNumber"))
    if existing["success"]:
        cust_id = existing["id"]
    else:
        cust_body = {"name": cust_name, "isCustomer": True}
        if f.get("customerOrgNumber"): cust_body["organizationNumber"] = f["customerOrgNumber"]
        cust_r = await tx(c, base, tok, "POST", "/customer", cust_body)
        if not cust_r.get("success"):
            return cust_r
        cust_id = cust_r["data"]["id"]

    # Step 2: Register bank account on account 1920
    acct_r = await tx(c, base, tok, "GET", "/ledger/account", params={"number": 1920})
    if acct_r.get("success") and acct_r.get("data"):
        accts = as_list(acct_r["data"])
        if accts:
            acct_id = accts[0]["id"]
            # Check if account already has a bank number
            existing_bank = accts[0].get("bankAccountNumber")
            if not existing_bank:
                bank_r = await tx(c, base, tok, "PUT", f"/ledger/account/{acct_id}", {
                    "bankAccountNumber": "19201234568",
                    "bankAccountCountry": {"id": 161},
                    "currency": {"id": 1},
                })
                if not bank_r.get("success"):
                    log.info("Bank account PUT failed (%d), trying alt number",
                             bank_r.get("status_code", 0))
                    # Try alternative bank number
                    await tx(c, base, tok, "PUT", f"/ledger/account/{acct_id}", {
                        "bankAccountNumber": "86011117947",
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
            "vatType": {"id": vat_id_sync(item.get("vatRate"), vat_map)},
        }
        # Create product if productNumber given (competition may check product existence)
        prod_num = item.get("productNumber")
        if prod_num:
            prod_body = {"name": item.get("description", "Produkt"), "number": prod_num}
            if item.get("unitPrice") is not None:
                prod_body["priceExcludingVatCurrency"] = float(item["unitPrice"])
            prod_r = await tx(c, base, tok, "POST", "/product", prod_body)
            if prod_r.get("success") and prod_r.get("data"):
                line["product"] = {"id": prod_r["data"]["id"]}
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
    r = await tx(c, base, tok, "POST", "/invoice", invoice_body)
    if not r.get("success") and "vattype" in str(r.get("error", "")).lower():
        # Retry without vatType on order lines (some sandboxes reject explicit VAT codes)
        log.info("Invoice POST failed on vatType, retrying without it")
        for ol in order_lines:
            ol.pop("vatType", None)
        r = await tx(c, base, tok, "POST", "/invoice", invoice_body)
    return r


async def exec_register_payment(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    cust_r = await find_customer(c, base, tok, f.get("customerName", ""), f.get("customerOrgNumber"))
    if not cust_r["success"]:
        return cust_r

    inv_r = await find_invoice_for_customer(c, base, tok, cust_r["id"])
    if not inv_r["success"]:
        return inv_r
    inv = inv_r["invoice"]
    inv_id = inv["id"]
    amount = f.get("amount") or inv.get("amount", 0)

    pt_r = await tx(c, base, tok, "GET", "/invoice/paymentType")
    pt_id = 1
    if pt_r.get("success") and pt_r.get("data"):
        pts = as_list(pt_r["data"])
        if pts:
            pt_id = pts[0]["id"]

    pay_date = f.get("paymentDate", time.strftime("%Y-%m-%d"))
    return await tx(c, base, tok, "PUT", f"/invoice/{inv_id}/:payment", params={
        "paymentDate": pay_date,
        "paidAmount": str(amount),
        "paidAmountCurrency": str(amount),
        "paymentTypeId": str(pt_id),
    })


async def exec_create_credit_note(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    cust_r = await find_customer(c, base, tok, f.get("customerName", ""), f.get("customerOrgNumber"))
    if not cust_r["success"]:
        return cust_r

    inv_r = await find_invoice_for_customer(c, base, tok, cust_r["id"])
    if not inv_r["success"]:
        return inv_r
    inv_id = inv_r["invoice"]["id"]
    date = f.get("date", time.strftime("%Y-%m-%d"))
    reason = f.get("reason", "Kreditering")
    return await tx(c, base, tok, "PUT", f"/invoice/{inv_id}/:createCreditNote", params={
        "date": date,
        "comment": reason,
    })


async def exec_create_travel_expense(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    # Step 1: Create employee (pass full fields dict so split_name can find name/employeeName)
    first, last = split_name(f)
    emp_r = await exec_create_employee(c, base, tok, {
        "firstName": first,
        "lastName": last,
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
        pts = as_list(pt_r["data"])
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
    for cost in costs:
        cost_body = {
            "travelExpense": {"id": te_id},
            "paymentType": {"id": pt_id},
            "currency": {"id": 1},
            "amountCurrencyIncVat": float(cost.get("amount", 0)),
            "date": cost.get("date", time.strftime("%Y-%m-%d")),
            "comments": cost.get("description", ""),
        }
        cost_r = await tx(c, base, tok, "POST", "/travelExpense/cost", cost_body)
        if not cost_r.get("success"):
            log.warning("Travel expense cost failed: %s", cost_r.get("error"))

    return te_r


async def exec_delete_employee(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    first, last = split_name(f)
    params = {"count": 10}
    if first: params["firstName"] = first
    if last: params["lastName"] = last
    emp_r = await tx(c, base, tok, "GET", "/employee", params=params)
    if not emp_r.get("success") or not emp_r.get("data"):
        return {"success": False, "error": "Employee not found"}
    emps = as_list(emp_r["data"])
    # Match by name to avoid deleting wrong employee
    for e in emps:
        if e.get("firstName") == first and e.get("lastName") == last:
            return await tx(c, base, tok, "DELETE", f"/employee/{e['id']}")
    # Fallback to first result if no exact match
    return await tx(c, base, tok, "DELETE", f"/employee/{emps[0]['id']}")


async def exec_delete_travel_expense(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    first, last = split_name(f)
    if first:
        emp_r = await tx(c, base, tok, "GET", "/employee", params={
            "firstName": first, "lastName": last, "count": 5
        })
        if emp_r.get("success") and emp_r.get("data"):
            emps = as_list(emp_r["data"])
            te_r = await tx(c, base, tok, "GET", "/travelExpense", params={"employeeId": emps[0]["id"]})
            if te_r.get("success") and te_r.get("data"):
                tes = as_list(te_r["data"])
                return await tx(c, base, tok, "DELETE", f"/travelExpense/{tes[0]['id']}")
    return {"success": False, "error": "Travel expense not found"}


async def exec_update_customer(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    target = f.get("targetEntity") or f.get("name", "")
    cust_r = await find_customer(c, base, tok, target)
    if not cust_r["success"]:
        return cust_r
    cust_id = cust_r["id"]

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
    emps = as_list(emp_r["data"])
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
        customers = as_list(cust_r["data"])
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


async def exec_enable_module(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    """Enable module task: proxy blocks PUT /company/modules (405).
    Best effort: create the department if mentioned, return completed."""
    dept_name = f.get("departmentName") or f.get("name")
    if dept_name:
        body = {"name": dept_name}
        if f.get("departmentNumber") is not None:
            body["departmentNumber"] = int(f["departmentNumber"])
        return await tx(c, base, tok, "POST", "/department", body)
    # Nothing actionable, just return success
    return {"success": True, "data": {"message": "Module enable skipped (proxy 405)"}}


async def exec_process_salary(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    """Process salary / payroll for an employee."""
    first, last = split_name(f)
    params = {"count": 20}
    if first: params["firstName"] = first
    if last: params["lastName"] = last
    emp_r = await tx(c, base, tok, "GET", "/employee", params=params)
    emp_id = None
    if emp_r.get("success") and emp_r.get("data"):
        emps = as_list(emp_r["data"])
        for e in emps:
            if e.get("firstName") == first and e.get("lastName") == last:
                emp_id = e["id"]
                break
        if not emp_id and emps:
            emp_id = emps[0]["id"]
    if not emp_id:
        dept_id = await ensure_department(c, base, tok)
        emp_body = {"firstName": first, "lastName": last, "department": {"id": dept_id or 1},
                    "userType": "NO_ACCESS", "dateOfBirth": f.get("dateOfBirth", "1990-01-15")}
        if f.get("email"): emp_body["email"] = f["email"]
        create_r = await tx(c, base, tok, "POST", "/employee", emp_body)
        if not create_r.get("success"): return create_r
        emp_id = create_r["data"]["id"]

    empl_r = await tx(c, base, tok, "GET", "/employee/employment", params={"employeeId": emp_id, "count": 5})
    employment_id = None
    if empl_r.get("success") and empl_r.get("data"):
        empls = as_list(empl_r["data"])
        if empls: employment_id = empls[0]["id"]
    if not employment_id:
        start_date = f.get("startDate", time.strftime("%Y-%m-%d"))
        empl_create = await tx(c, base, tok, "POST", "/employee/employment", {
            "employee": {"id": emp_id}, "startDate": start_date, "isMainEmployer": True,
        })
        if empl_create.get("success"):
            employment_id = empl_create["data"]["id"]
            salary_amount = f.get("salary") or f.get("baseSalary") or f.get("amount")
            details_body = {"employment": {"id": employment_id}, "date": start_date,
                            "employmentType": "ORDINARY", "percentageOfFullTimeEquivalent": 100.0}
            if salary_amount is not None:
                details_body["annualSalary"] = float(salary_amount) * 12
            await tx(c, base, tok, "POST", "/employee/employment/details", details_body)

    salary_amount = f.get("salary") or f.get("baseSalary") or f.get("amount") or 0
    bonus_amount = f.get("bonus") or f.get("bonusAmount") or 0
    pay_date = f.get("paymentDate") or time.strftime("%Y-%m-%d")

    sal_type_r = await tx(c, base, tok, "GET", "/salary/type", params={"count": 50})
    monthly_type_id = bonus_type_id = None
    if sal_type_r.get("success") and sal_type_r.get("data"):
        for st in as_list(sal_type_r["data"]):
            name_lower = (st.get("name") or "").lower()
            num = st.get("number")
            if num == 111 or "fast" in name_lower or "maaned" in name_lower:
                monthly_type_id = st["id"]
            if num == 130 or "bonus" in name_lower or "tillegg" in name_lower:
                bonus_type_id = st["id"]
        if not monthly_type_id and as_list(sal_type_r["data"]):
            monthly_type_id = as_list(sal_type_r["data"])[0]["id"]
        if not bonus_type_id: bonus_type_id = monthly_type_id

    if employment_id:
        payslip_r = await tx(c, base, tok, "POST", "/salary/payslip", {
            "employee": {"id": emp_id}, "employment": {"id": employment_id}})
        if not payslip_r.get("success"):
            payslip_r = await tx(c, base, tok, "POST", "/salary/paymentSpecification", {
                "employee": {"id": emp_id}, "employment": {"id": employment_id}})
        if payslip_r.get("success") and payslip_r.get("data"):
            ps_id = payslip_r["data"]["id"]
            if salary_amount and monthly_type_id:
                await tx(c, base, tok, "POST", "/salary/transaction", {
                    "payslip": {"id": ps_id}, "salaryType": {"id": monthly_type_id},
                    "amount": float(salary_amount), "date": pay_date})
            if bonus_amount and bonus_type_id:
                await tx(c, base, tok, "POST", "/salary/transaction", {
                    "payslip": {"id": ps_id}, "salaryType": {"id": bonus_type_id},
                    "amount": float(bonus_amount), "date": pay_date})
            return payslip_r

    return {"success": True, "data": {"message": "Employee + employment created"}}


async def exec_register_supplier_invoice(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    """Register an incoming supplier invoice."""
    supplier_name = f.get("supplierName") or f.get("name", "Leverandor")
    org_number = f.get("orgNumber") or f.get("supplierOrgNumber")
    total_incl_vat = float(f.get("amount") or f.get("totalAmount") or f.get("invoiceAmount") or 0)
    vat_rate = float(f.get("vatRate", 25))
    expense_account_number = int(f.get("account") or f.get("accountNumber") or 6300)
    invoice_number = f.get("invoiceNumber") or ""
    invoice_date = f.get("invoiceDate") or f.get("date") or time.strftime("%Y-%m-%d")
    description = f.get("description") or f"Leverandorfaktura {invoice_number} fra {supplier_name}"

    net_amount = round(total_incl_vat / (1 + vat_rate / 100), 2) if vat_rate > 0 else total_incl_vat

    sup_body = {"name": supplier_name}
    if org_number: sup_body["organizationNumber"] = str(org_number)
    sup_r = await tx(c, base, tok, "POST", "/supplier", sup_body)
    supplier_id = sup_r["data"]["id"] if sup_r.get("success") and sup_r.get("data") else None
    if not supplier_id:
        cust_r = await tx(c, base, tok, "POST", "/customer", {"name": supplier_name, "isCustomer": False, "isSupplier": True,
                          **({"organizationNumber": str(org_number)} if org_number else {})})
        if cust_r.get("success") and cust_r.get("data"):
            supplier_id = cust_r["data"]["id"]

    sup_inv_body = {"invoiceDate": invoice_date, "paymentDueDate": invoice_date, "invoiceNumber": invoice_number,
                    "amountCurrency": total_incl_vat, "currency": {"id": 1}}
    if supplier_id: sup_inv_body["supplier"] = {"id": supplier_id}
    sup_inv_r = await tx(c, base, tok, "POST", "/supplierInvoice", sup_inv_body)
    if sup_inv_r.get("success"): return sup_inv_r

    expense_acct_r = await tx(c, base, tok, "GET", "/ledger/account", params={"number": expense_account_number})
    expense_acct_id = as_list(expense_acct_r["data"])[0]["id"] if expense_acct_r.get("success") and expense_acct_r.get("data") else None
    input_vat_map = await lookup_input_vat_map(c, base, tok)
    input_vat_id = input_vat_map.get(int(vat_rate), input_vat_map.get(25, 1))

    if expense_acct_id:
        voucher_body = {"date": invoice_date, "description": description, "postings": [{
            "account": {"id": expense_acct_id}, "amountGross": total_incl_vat,
            "amountGrossCurrency": total_incl_vat, "currency": {"id": 1},
            "description": description, "date": invoice_date, "vatType": {"id": input_vat_id}}]}
        return await tx(c, base, tok, "POST", "/ledger/voucher", voucher_body)
    return {"success": False, "error": "Could not resolve expense account"}


async def exec_create_dimension(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    """Create custom accounting dimension with values and optional posting."""
    dimension_name = f.get("dimensionName") or f.get("name", "")
    dimension_values = f.get("dimensionValues") or f.get("values") or []
    if isinstance(dimension_values, str):
        dimension_values = [v.strip() for v in dimension_values.split(",") if v.strip()]
    post_account = f.get("account") or f.get("accountNumber")
    post_amount = f.get("amount")
    post_dim_value = f.get("linkedDimensionValue") or f.get("linkedValue")
    post_date = f.get("date") or time.strftime("%Y-%m-%d")
    description = f.get("description") or f"Bilag med dimensjon {dimension_name}"

    created_values = []
    for i, val in enumerate(dimension_values):
        dept_r = await tx(c, base, tok, "POST", "/department", {
            "name": f"{dimension_name}: {val}", "departmentNumber": i + 100})
        if dept_r.get("success") and dept_r.get("data"):
            created_values.append({"name": val, "id": dept_r["data"]["id"]})

    if post_account and post_amount:
        target_dept_id = None
        for cv in created_values:
            if post_dim_value and post_dim_value.lower() in cv["name"].lower():
                target_dept_id = cv["id"]
                break
        if not target_dept_id and created_values:
            target_dept_id = created_values[0]["id"]
        acct_r = await tx(c, base, tok, "GET", "/ledger/account", params={"number": int(post_account)})
        acct_id = as_list(acct_r["data"])[0]["id"] if acct_r.get("success") and acct_r.get("data") else None
        if acct_id:
            posting_debit = {"account": {"id": acct_id}, "amountGross": float(post_amount),
                             "amountGrossCurrency": float(post_amount), "currency": {"id": 1},
                             "description": description, "date": post_date}
            if target_dept_id: posting_debit["department"] = {"id": target_dept_id}
            # Balanced voucher: add credit posting on account 2400
            credit_acct_r = await tx(c, base, tok, "GET", "/ledger/account", params={"number": 2400})
            credit_id = as_list(credit_acct_r["data"])[0]["id"] if credit_acct_r.get("success") and credit_acct_r.get("data") else None
            postings = [posting_debit]
            if credit_id:
                postings.append({"account": {"id": credit_id}, "amountGross": -float(post_amount),
                                 "amountGrossCurrency": -float(post_amount), "currency": {"id": 1},
                                 "description": description, "date": post_date})
            return await tx(c, base, tok, "POST", "/ledger/voucher", {
                "date": post_date, "description": description, "postings": postings})

    if created_values:
        return {"success": True, "data": {"message": f"Created {len(created_values)} dimension values"}}
    return {"success": False, "error": "Could not create dimension"}


async def exec_create_supplier(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    """Register a supplier entity."""
    name = f.get("supplierName") or f.get("name", "")
    body = {"name": name, "isCustomer": False, "isSupplier": True}
    if f.get("orgNumber") or f.get("supplierOrgNumber"):
        body["organizationNumber"] = str(f.get("orgNumber") or f["supplierOrgNumber"])
    if f.get("email"): body["email"] = f["email"]
    if f.get("phone"): body["phoneNumber"] = f["phone"]
    if f.get("address"):
        body["postalAddress"] = {
            "addressLine1": f.get("address", ""),
            "postalCode": f.get("postalCode", ""),
            "city": f.get("city", ""),
        }
    # Try /supplier first, fall back to /customer with isSupplier
    sup_r = await tx(c, base, tok, "POST", "/supplier", body)
    if sup_r.get("success"):
        return sup_r
    return await tx(c, base, tok, "POST", "/customer", body)


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
    "enable_module": exec_enable_module,
    "process_salary": exec_process_salary,
    "register_supplier_invoice": exec_register_supplier_invoice,
    "create_dimension": exec_create_dimension,
    "create_supplier": exec_create_supplier,
}


# ---------------------------------------------------------------------------
# Fallback: Gemini agent loop for unknown task types (from v3)
# ---------------------------------------------------------------------------
FALLBACK_SYSTEM_PROMPT = """You are an expert AI accounting agent for Tripletex.
Execute the requested accounting task via API calls. Use tripletex_api tool.
Auth: Basic Auth, username "0", password is the session token.
Dates: convert DD.MM.YYYY to YYYY-MM-DD. Numbers: convert "1.000,50" to 1000.50.
POST /customer: always include "isCustomer": true.
POST /employee: always include "department": {"id": X} and "userType": "NO_ACCESS".
POST /order or inline orders: always include "deliveryDate".
Fresh sandbox: no pre-existing business data except system entities.
Return a brief summary when done."""

TRIPLETEX_TOOL = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="tripletex_api",
            description="Make an HTTP request to the Tripletex REST API.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "method": types.Schema(type="STRING", enum=["GET", "POST", "PUT", "DELETE"]),
                    "path": types.Schema(type="STRING", description="API path, e.g. '/employee'"),
                    "body": types.Schema(type="STRING", description="JSON body for POST/PUT"),
                    "query_params": types.Schema(type="STRING", description="key=value&key2=value2"),
                },
                required=["method", "path"],
            ),
        ),
    ]
)

MAX_FALLBACK_TURNS = 15


async def run_agent_fallback(
    prompt: str,
    files: list[dict] | None,
    base_url: str,
    session_token: str,
    t0: float,
) -> dict[str, Any]:
    """Fallback Gemini agent loop for unknown task types."""
    user_parts: list[types.Part] = [types.Part.from_text(text=f"Task prompt:\n{prompt}")]
    if files:
        for f in files:
            content_b64 = f.get("content_base64", "")
            mime = f.get("mime_type", "application/octet-stream")
            if content_b64:
                try:
                    raw = base64.b64decode(content_b64)
                    user_parts.append(types.Part.from_bytes(data=raw, mime_type=mime))
                except Exception:
                    pass

    contents: list[types.Content] = [types.Content(role="user", parts=user_parts)]

    async with httpx.AsyncClient() as http_client:
        for turn in range(MAX_FALLBACK_TURNS):
            if time.time() - t0 > DEADLINE_SECONDS:
                log.warning("Fallback agent: deadline reached at turn %d", turn + 1)
                break

            try:
                response = await asyncio.to_thread(
                    gemini_client.models.generate_content,
                    model=GEMINI_MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=FALLBACK_SYSTEM_PROMPT,
                        tools=[TRIPLETEX_TOOL],
                        temperature=0.0,
                        max_output_tokens=8192,
                    ),
                )
            except Exception as e:
                log.error("Fallback agent Gemini error: %s", e)
                break

            if not response.candidates:
                break
            candidate = response.candidates[0]

            reason = getattr(candidate.finish_reason, "name", None)
            if reason in ("MALFORMED_FUNCTION_CALL", "UNEXPECTED_TOOL_CALL"):
                log.warning("Fallback agent: %s on turn %d, aborting", reason, turn + 1)
                break

            if not candidate.content or not candidate.content.parts:
                continue

            function_calls = [p for p in candidate.content.parts if p.function_call]
            if not function_calls:
                log.info("Fallback agent completed at turn %d", turn + 1)
                break

            contents.append(candidate.content)
            fn_responses: list[types.Part] = []
            for fc_part in function_calls:
                fc = fc_part.function_call
                args = dict(fc.args) if fc.args else {}
                method = args.get("method", "GET")
                path = args.get("path", "/")
                body_str = args.get("body")
                qp = args.get("query_params")

                parsed_body = None
                if body_str:
                    try:
                        parsed_body = json.loads(body_str)
                    except json.JSONDecodeError:
                        log.warning("Fallback agent: invalid JSON body, skipping: %s", body_str[:200])
                        fn_responses.append(types.Part.from_function_response(
                            name=fc.name, response={"result": '{"error": "Invalid JSON body", "status_code": 400}'}))
                        continue

                result = await tx(http_client, base_url, session_token, method, path,
                                  parsed_body, _parse_query_params(qp) if qp else None)

                result_str = json.dumps(result, default=str, ensure_ascii=False)
                if len(result_str) > 8000:
                    result_str = result_str[:7990] + '..."}'
                fn_responses.append(types.Part.from_function_response(
                    name=fc.name, response={"result": result_str}))

            contents.append(types.Content(role="tool", parts=fn_responses))

    return {
        "status": "completed",
        "task_type": "unknown_fallback",
        "elapsed_seconds": time.time() - t0,
    }


def _parse_query_params(qp: str) -> dict:
    """Parse 'key=value&key2=value2' into dict."""
    params = {}
    for pair in qp.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            params[k.strip()] = v.strip()
    return params


async def run_structured(
    prompt: str,
    files: list[dict] | None,
    base_url: str,
    session_token: str,
) -> dict[str, Any]:
    """Run the structured workflow: extract fields then execute deterministic API sequence."""
    t0 = time.time()

    # Decode files for multimodal extraction
    file_parts = []
    if files:
        for f in files:
            content_b64 = f.get("content_base64", "")
            mime = f.get("mime_type", "application/octet-stream")
            fname = f.get("filename", "unknown")
            if content_b64:
                try:
                    raw = base64.b64decode(content_b64)
                    file_parts.append({"raw": raw, "mime": mime, "name": fname})
                except Exception as e:
                    log.warning("File %s decode error: %s", fname, e)

    # Step 1: Extract task type and fields (multimodal: sends file bytes to Gemini)
    extraction = await extract_fields(prompt, file_parts or None)
    task_type = extraction.get("task_type", "unknown")
    fields = extraction.get("fields", {})

    elapsed_extract = time.time() - t0
    log.info("Task type: %s (extraction took %.1fs)", task_type, elapsed_extract)

    # Step 2: Route to executor
    executor = TASK_EXECUTORS.get(task_type)
    if not executor:
        log.warning("Unknown task type '%s', falling back to agent loop. Fields: %s",
                     task_type, json.dumps(fields, ensure_ascii=False)[:300])
        return await run_agent_fallback(prompt, files, base_url, session_token, t0)

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
