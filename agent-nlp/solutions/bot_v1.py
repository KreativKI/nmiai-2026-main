"""
NM i AI 2026 - Tripletex AI Accounting Agent (bot_v1)

FastAPI endpoint that receives accounting task prompts and executes them
via Tripletex API using Gemini 2.5 Flash as the reasoning engine.

Architecture: POST /solve -> Gemini (function-calling) -> Tripletex API
"""

import base64
import json
import logging
import os
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
log = logging.getLogger("bot_v1")

app = FastAPI(title="Tripletex AI Agent", version="1.0")

# --- Gemini client ---
GCP_PROJECT = os.getenv("GCP_PROJECT", "ai-nm26osl-1779")
GCP_LOCATION = os.getenv("GCP_LOCATION", "europe-west4")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
MAX_AGENT_TURNS = 15

gemini_client = genai.Client(
    vertexai=True,
    project=GCP_PROJECT,
    location=GCP_LOCATION,
)

# ---------------------------------------------------------------------------
# Tripletex API reference for the LLM system prompt
# ---------------------------------------------------------------------------

TRIPLETEX_API_REFERENCE = """
## Tripletex REST API - Key Endpoints

Authentication: Basic Auth on every call. Username: "0", Password: session_token.
Content-Type: application/json
Base URL: provided per request (e.g. https://xxx.tripletex.dev/v2)

All dates in API payloads use ISO format: YYYY-MM-DD (even though prompts use DD.MM.YYYY).
All monetary amounts are numbers (floats), not strings. Norwegian "1.000,50" = 1000.50.
When creating entities that reference other entities (like Department on Employee), use {"id": <id>} format.

### POST /employee
Create employee. REQUIRED: firstName, lastName, department {id}, userType.
Key fields: firstName, lastName, email, dateOfBirth (YYYY-MM-DD),
phoneNumberMobile, nationalIdentityNumber, employeeNumber, bankAccountNumber,
address {addressLine1, postalCode, city, country {id}},
userType (STANDARD/EXTENDED/NO_ACCESS) - MUST be set, default to "NO_ACCESS" if not specified,
department {id} - MUST be set. If no department exists, create one first with POST /department,
comments. Returns created employee with id.

### POST /employee/employment
Create employment for an employee. Fields: employee {id}, startDate (YYYY-MM-DD),
division {id}, taxDeductionCode, isMainEmployer (bool),
employmentDetails [{date, employmentType (ORDINARY/MARITIME/FREELANCE),
percentageOfFullTimeEquivalent, annualSalary, occupationCode {id}}].

### POST /employee/employment/details
Create employment details. Fields: employment {id}, date (YYYY-MM-DD),
employmentType (ORDINARY/MARITIME/FREELANCE/NOT_CHOSEN),
employmentForm (PERMANENT/TEMPORARY/NOT_CHOSEN),
remunerationType (MONTHLY_WAGE/HOURLY_WAGE/FEE/NOT_CHOSEN),
percentageOfFullTimeEquivalent, annualSalary, hourlyWage,
occupationCode {id}, payrollTaxMunicipalityId {id}.

### POST /customer
Create customer. Key fields: name, organizationNumber, email, phoneNumber,
phoneNumberMobile, isPrivateIndividual (bool), language (NO/EN),
postalAddress {addressLine1, postalCode, city, country {id}},
physicalAddress {addressLine1, postalCode, city, country {id}},
invoiceEmail, invoiceSendMethod (EMAIL/EHF/PAPER), invoicesDueIn (int),
invoicesDueInType (DAYS/MONTHS).

### POST /product
Create product. Key fields: name, number, description, ean,
priceExcludingVatCurrency (number), priceIncludingVatCurrency (number),
costExcludingVatCurrency (number), vatType {id}, productUnit {id},
isStockItem (bool), currency {id}, account {id}, department {id}.
Common vatType IDs: check with GET /ledger/vatType.

### POST /department
Create department. Fields: name, departmentNumber, departmentManager {id}.

### POST /contact
Create contact. Fields: firstName, lastName, email,
phoneNumberMobile, customer {id}, department {id}.

### POST /invoice
Create invoice. Can include orders inline. Fields: invoiceDate (YYYY-MM-DD),
invoiceDueDate (YYYY-MM-DD), customer {id}, comment,
orders [{customer {id}, orderDate, orderLines [{description, count, unitPriceExcludingVatCurrency, vatType {id}, product {id}}]}].
After creation, you may need to send the invoice.

### POST /order
Create order. Fields: customer {id}, orderDate (YYYY-MM-DD), department {id},
project {id}, deliveryDate, invoiceComment, ourContactEmployee {id},
orderLines [{product {id}, description, count (number),
unitPriceExcludingVatCurrency (number), vatType {id}, discount}].

### POST /order/orderline
Create order line. Fields: order {id}, product {id}, description,
count (number), unitPriceExcludingVatCurrency (number), vatType {id}.

### POST /project
Create project. Fields: name, number, description, projectManager {id},
department {id}, startDate, endDate, customer {id},
isInternal (bool), isFixedPrice (bool), projectCategory {id}.

### POST /travelExpense
Create travel expense. Fields: employee {id}, project {id},
department {id}, title, isChargeable, travelAdvance,
perDiemCompensations [...], costs [...].

### POST /travelExpense/cost
Create travel expense cost. Fields: travelExpense {id}, vatType {id},
currency {id}, costCategory {id}, paymentType, date, count, rate,
amountCurrencyIncVat, amountNOKInclVAT, description, isChargeable.

### PUT /invoice/{id}/:payment
Register payment on invoice. Parameters: id (invoice id),
paymentDate (query), paymentTypeId (query), paidAmount (query),
paidAmountCurrency (query).

### PUT /invoice/{id}/:createCreditNote
Create credit note for invoice. Parameter: id (invoice id),
date (YYYY-MM-DD), comment.

### DELETE /employee/{id}
Delete employee. Parameter: id.

### DELETE /travelExpense/{id}
Delete travel expense. Parameter: id.

### DELETE /project/{id}
Delete project. Parameter: id.

### GET /ledger/vatType
List available VAT types. Use to find correct vatType IDs.
Common Norwegian VAT: 25% (standard/output), 15% (food), 12% (transport), 0% (exempt).

### GET /currency
List available currencies. NOK is typically id=1.

### GET /country
List countries. Norway is typically id=161.

### GET /employee
Search employees. Query params: firstName, lastName, employeeNumber, email.

### GET /customer
Search customers. Query params: name, email, organizationNumber, customerNumber.

### GET /product
Search products. Query params: name, number.

### GET /department
Search departments. Query params: name, departmentNumber.

### GET /project
Search projects. Query params: name, number.

### GET /travelExpense
Search travel expenses.

### GET /travelExpense/costCategory
List cost categories for travel expenses.

### GET /product/unit
List product units (stk, kg, liter, etc).

### GET /employee/employment
Get employments. Query param: employeeId.

### GET /company/modules
Get company modules status.

### PUT /company/modules
Enable/disable company modules.

### GET /invoice
Search invoices. Query params: invoiceNumber, customerId.

### GET /order
Search orders.

### GET /division
List divisions. Needed for employment creation.

### GET /salary/type
List salary types.

### GET /ledger/account
List chart of accounts. Query params: number, isApplicableForSupplierInvoice.

### PUT /employee/{id}
Update employee. Send full or partial employee object.

### PUT /customer/{id}
Update customer.

### PUT /product/{id}
Update product.

### PUT /department/{id}
Update department.

### PUT /contact/{id}
Update contact.

### PUT /project/{id}
Update project.
"""

SYSTEM_PROMPT = f"""You are an expert AI accounting agent for Tripletex, a Norwegian accounting system.
You receive accounting task prompts in 7 languages (Norwegian Bokmal, Nynorsk, English, Spanish, Portuguese, German, French) and must execute the correct API calls.

## Your Workflow
1. Read the task prompt carefully. Extract ALL field values mentioned.
2. Determine which Tripletex API calls are needed.
3. Execute them using the tripletex_api tool. Plan before calling to minimize API calls.
4. IMPORTANT: When you need to look up reference data (VAT types, currencies, countries, divisions), make ONE lookup call, then use the IDs in subsequent calls.

## Critical Rules
- NEVER guess IDs for referenced entities. Look them up first if needed.
- Convert date format: DD.MM.YYYY in prompt -> YYYY-MM-DD for API.
- Convert numbers: "1.000,50" in prompt -> 1000.50 for API.
- Fresh sandbox: no pre-existing data except system reference data (countries, currencies, vatTypes, divisions).
  You must create dependencies first (e.g., create department before employee, create customer before invoice).
- Every 4xx error hurts your efficiency score. Validate before sending.
- Do NOT make GET calls to verify entities you just created (wastes API calls).
- When creating invoices: create order with orderLines first, then create invoice referencing the order. Or include orders inline in the invoice POST.
- The API uses Basic Auth. This is handled automatically.
- IMPORTANT: Employee creation REQUIRES department {id} and userType. Always create department first if needed, and set userType to "NO_ACCESS" unless specified.
- IMPORTANT: For lookup of reference data (divisions, vatTypes, currencies), do ONE batch call at the start if you need these IDs.
- If the prompt mentions employment details (job title, salary, start date), create the employee first, then create employment and employment details as separate calls.
- IMPORTANT: When creating orders (standalone or inline with invoices), deliveryDate is REQUIRED. Use the order date or invoice date if no delivery date is specified.
- IMPORTANT: The sandbox is FRESH and EMPTY. Do NOT search for existing entities with GET calls. Just create what you need directly.
- For invoicing: create the customer first, then create the invoice with inline orders and orderLines. Each orderLine needs a vatType {id}. Look up vatType IDs with GET /ledger/vatType once if needed.
- For the company bank account: if invoicing fails because no bank account is registered, try GET /token/session/>whoAmI to find companyId, then check if there is a way to configure it.

## Norwegian Accounting Conventions
- VAT (MVA/moms): 25% standard, 15% food, 12% transport/hotels, 0% exempt
- Currency: NOK (Norwegian krone)
- Fiscal year: January 1 - December 31
- Organization numbers: 9 digits
- National identity numbers (personnummer): 11 digits (DDMMYY + 5 digits)
- Bank account numbers: 11 digits (XXXX.XX.XXXXX format)

## Language Handling
Extract field values regardless of language. Key vocabulary:
- Ansatt/tilsett = Employee | Kunde = Customer | Produkt/vare = Product
- Faktura = Invoice | Avdeling = Department | Prosjekt = Project
- Reiseregning = Travel expense | Betaling = Payment
- Kreditnota = Credit note | Slett/fjern = Delete
- Opprett/lag = Create | Oppdater/endre = Update
- Stillingsprosent = Employment percentage | Arslonn = Annual salary
- Organisasjonsnummer = Organization number | Personnummer = National ID

{TRIPLETEX_API_REFERENCE}

## Response Format
After completing all necessary API calls, respond with a brief summary of what was done.
If you encounter an error that you cannot resolve, explain what went wrong.
"""

# ---------------------------------------------------------------------------
# Gemini function-calling tool definition
# ---------------------------------------------------------------------------

TRIPLETEX_TOOL = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="tripletex_api",
            description=(
                "Make an HTTP request to the Tripletex REST API. "
                "Use this to create, read, update, or delete accounting entities. "
                "The base_url and authentication are handled automatically."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "method": types.Schema(
                        type="STRING",
                        description="HTTP method: GET, POST, PUT, or DELETE",
                        enum=["GET", "POST", "PUT", "DELETE"],
                    ),
                    "path": types.Schema(
                        type="STRING",
                        description=(
                            "API path relative to base URL, e.g. '/employee' or '/invoice/123/:payment'. "
                            "Do NOT include the base URL, just the path starting with /."
                        ),
                    ),
                    "body": types.Schema(
                        type="STRING",
                        description=(
                            "JSON string for POST/PUT request body. "
                            "Must be valid JSON. Leave empty for GET/DELETE."
                        ),
                    ),
                    "query_params": types.Schema(
                        type="STRING",
                        description=(
                            "Query parameters as key=value pairs separated by &. "
                            "E.g. 'firstName=Ola&lastName=Nordmann' or 'paymentDate=2026-03-20&paidAmount=1000'. "
                            "Leave empty if no query parameters needed."
                        ),
                    ),
                },
                required=["method", "path"],
            ),
        ),
    ]
)


# ---------------------------------------------------------------------------
# Tripletex API caller
# ---------------------------------------------------------------------------

async def call_tripletex(
    client: httpx.AsyncClient,
    base_url: str,
    session_token: str,
    method: str,
    path: str,
    body: str | None = None,
    query_params: str | None = None,
) -> dict[str, Any]:
    """Execute a Tripletex API call and return the result."""
    url = f"{base_url}{path}"

    params = {}
    if query_params:
        for pair in query_params.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                params[k.strip()] = v.strip()

    json_body = None
    if body:
        try:
            json_body = json.loads(body)
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON body: {e}", "status_code": 400}

    auth = httpx.BasicAuth(username="0", password=session_token)

    try:
        response = await client.request(
            method=method.upper(),
            url=url,
            json=json_body,
            params=params if params else None,
            auth=auth,
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=30.0,
        )

        # Try to parse JSON response
        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text[:2000]}

        result = {
            "status_code": response.status_code,
            "success": 200 <= response.status_code < 300,
        }

        # For successful responses, include key data
        if result["success"]:
            if isinstance(data, dict) and "value" in data:
                result["data"] = data["value"]
            else:
                result["data"] = data
        else:
            result["error"] = data
            log.warning("API %s %s -> %d: %s", method, path, response.status_code, str(data)[:300])

        return result

    except httpx.TimeoutException:
        return {"error": "Request timed out after 30s", "status_code": 408}
    except Exception as e:
        return {"error": str(e), "status_code": 500}


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

async def run_agent(
    task_prompt: str,
    task_type: str,
    attachments: list[dict] | None,
    base_url: str,
    session_token: str,
) -> dict[str, Any]:
    """Run the Gemini agent loop to solve an accounting task."""

    t0 = time.time()
    api_calls = 0
    errors_4xx = 0

    # Build user message content
    user_parts: list[types.Part] = []

    # Add task context
    task_text = (
        f"Task type: {task_type}\n\n"
        f"Task prompt:\n{task_prompt}\n\n"
        "Execute the required Tripletex API calls to complete this task. "
        "Minimize the number of API calls. Do NOT verify entities you just created."
    )
    user_parts.append(types.Part.from_text(text=task_text))

    # Process attachments (multimodal)
    if attachments:
        for att in attachments:
            filename = att.get("filename", "unknown")
            data_b64 = att.get("data", "")
            if data_b64:
                try:
                    raw_bytes = base64.b64decode(data_b64)
                    # Determine MIME type from filename
                    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
                    mime_map = {
                        "pdf": "application/pdf",
                        "png": "image/png",
                        "jpg": "image/jpeg",
                        "jpeg": "image/jpeg",
                        "gif": "image/gif",
                        "webp": "image/webp",
                    }
                    mime = mime_map.get(ext, "application/octet-stream")
                    user_parts.append(types.Part.from_bytes(data=raw_bytes, mime_type=mime))
                    log.info("Attached %s (%s, %d bytes)", filename, mime, len(raw_bytes))
                except Exception as e:
                    log.warning("Failed to decode attachment %s: %s", filename, e)
                    user_parts.append(types.Part.from_text(
                        text=f"[Attachment {filename} could not be decoded: {e}]"
                    ))

    # Initialize conversation
    contents: list[types.Content] = [
        types.Content(role="user", parts=user_parts),
    ]

    async with httpx.AsyncClient() as http_client:
        for turn in range(MAX_AGENT_TURNS):
            log.info("Agent turn %d (api_calls=%d, errors=%d)", turn + 1, api_calls, errors_4xx)

            try:
                response = gemini_client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        tools=[TRIPLETEX_TOOL],
                        temperature=0.1,
                        max_output_tokens=8192,
                    ),
                )
            except Exception as e:
                log.error("Gemini API error: %s", e)
                return {
                    "status": "error",
                    "error": f"LLM error: {e}",
                    "api_calls": api_calls,
                    "errors_4xx": errors_4xx,
                    "elapsed_seconds": time.time() - t0,
                }

            # Check for function calls in the response
            candidate = response.candidates[0] if response.candidates else None
            if not candidate or not candidate.content or not candidate.content.parts:
                log.warning("Empty response from Gemini")
                break

            function_calls = [p for p in candidate.content.parts if p.function_call]
            text_parts = [p for p in candidate.content.parts if p.text]

            if not function_calls:
                # No function calls = agent is done
                final_text = " ".join(p.text for p in text_parts if p.text)
                log.info("Agent completed: %s", final_text[:200])
                break

            # Add model's response to conversation
            contents.append(candidate.content)

            # Execute all function calls
            function_responses: list[types.Part] = []
            for fc_part in function_calls:
                fc = fc_part.function_call
                args = dict(fc.args) if fc.args else {}

                log.info("Calling: %s %s", args.get("method", "?"), args.get("path", "?"))

                result = await call_tripletex(
                    client=http_client,
                    base_url=base_url,
                    session_token=session_token,
                    method=args.get("method", "GET"),
                    path=args.get("path", "/"),
                    body=args.get("body"),
                    query_params=args.get("query_params"),
                )

                api_calls += 1
                status = result.get("status_code", 0)
                if 400 <= status < 500:
                    errors_4xx += 1

                # Truncate large responses to stay within context
                result_str = json.dumps(result, default=str, ensure_ascii=False)
                if len(result_str) > 4000:
                    # Keep first items if it's a list
                    if isinstance(result.get("data"), list) and len(result["data"]) > 10:
                        result["data"] = result["data"][:10]
                        result["_truncated"] = True
                        result_str = json.dumps(result, default=str, ensure_ascii=False)

                function_responses.append(
                    types.Part.from_function_response(
                        name=fc.name,
                        response={"result": result_str},
                    )
                )

            # Add function responses to conversation
            contents.append(types.Content(role="user", parts=function_responses))

    elapsed = time.time() - t0
    log.info("Done: %d API calls, %d 4xx errors, %.1fs elapsed", api_calls, errors_4xx, elapsed)

    return {
        "status": "completed",
        "api_calls": api_calls,
        "errors_4xx": errors_4xx,
        "elapsed_seconds": elapsed,
    }


# ---------------------------------------------------------------------------
# FastAPI endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "model": GEMINI_MODEL}


@app.post("/solve")
async def solve(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"status": "error", "error": "Invalid JSON"}, status_code=400)

    task_prompt = body.get("task_prompt", "")
    task_type = body.get("task_type", "unknown")
    attachments = body.get("attachments", [])
    base_url = body.get("base_url", "")
    session_token = body.get("session_token", "")

    if not task_prompt or not base_url or not session_token:
        return JSONResponse(
            {"status": "error", "error": "Missing required fields"},
            status_code=400,
        )

    log.info("=== SOLVE: task_type=%s, prompt_len=%d, attachments=%d ===",
             task_type, len(task_prompt), len(attachments))
    log.info("Prompt: %s", task_prompt[:300])

    try:
        result = await run_agent(
            task_prompt=task_prompt,
            task_type=task_type,
            attachments=attachments,
            base_url=base_url,
            session_token=session_token,
        )
        return JSONResponse({"status": "completed"})
    except Exception as e:
        log.error("Agent error: %s\n%s", e, traceback.format_exc())
        return JSONResponse({"status": "completed"})


# ---------------------------------------------------------------------------
# Local development
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
