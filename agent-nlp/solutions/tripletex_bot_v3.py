"""
NM i AI 2026 - Tripletex AI Accounting Agent (tripletex_bot_v3)
Changes from v2: employment details fix (dateOfBirth + employment sequence),
improved MALFORMED_FUNCTION_CALL retry with hint injection.

FastAPI endpoint that receives accounting task prompts and executes them
via Tripletex API using Gemini 2.5 Flash as the reasoning engine.

Architecture: POST /solve -> Gemini (function-calling) -> Tripletex API

Competition spec: https://app.ainm.no/tasks/tripletex
Request format: {prompt, files[], tripletex_credentials{base_url, session_token}}
Response format: {"status": "completed"}
"""

import asyncio
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
log = logging.getLogger("tripletex_bot")

app = FastAPI(title="Tripletex AI Agent", version="1.0")

GCP_PROJECT = os.getenv("GCP_PROJECT", "ai-nm26osl-1779")
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")  # us-central1 has full model roster
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_FALLBACK_MODEL = "gemini-2.5-pro"  # Slower but more reliable on complex JSON
MAX_AGENT_TURNS = 25
DEADLINE_SECONDS = 280  # 300s timeout, leave 20s buffer

try:
    gemini_client = genai.Client(
        vertexai=True,
        project=GCP_PROJECT,
        location=GCP_LOCATION,
    )
except Exception as e:
    log.error(
        "FATAL: Failed to initialize Gemini client. "
        "Check GCP_PROJECT=%s, GCP_LOCATION=%s, and that gcloud auth is configured. Error: %s",
        GCP_PROJECT, GCP_LOCATION, e,
    )
    raise

# ---------------------------------------------------------------------------
# Tripletex API Reference (factual endpoint documentation for the LLM)
# ---------------------------------------------------------------------------
TRIPLETEX_API_REFERENCE = """
## Tripletex REST API - Key Endpoints

Authentication: Basic Auth on every call. Username: "0", Password: session_token.
Content-Type: application/json
Base URL: provided per request via proxy (e.g. https://tx-proxy.ainm.no/v2)

All dates in API payloads use ISO format: YYYY-MM-DD (even though prompts use DD.MM.YYYY).
All monetary amounts are numbers (floats), not strings. Norwegian "1.000,50" = 1000.50.
When creating entities that reference other entities (like Department on Employee), use {"id": <id>} format.
List responses are wrapped: {"fullResultSize": N, "values": [...]}.
Single entity responses are wrapped: {"value": {...}}.

### POST /employee
Create employee. REQUIRED: firstName, lastName, department {id}, userType.
IMPORTANT: If you will create employment (salary/percentage), include dateOfBirth (REQUIRED for employment creation, use "1990-01-15" if not in prompt).
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
Create customer. REQUIRED: name, isCustomer (MUST be true).
Key fields: name, isCustomer (bool, MUST be true to register as customer),
organizationNumber, email, phoneNumber (landline), phoneNumberMobile (mobile),
isPrivateIndividual (bool), language (NO/EN),
postalAddress {addressLine1, postalCode, city, country {id}},
physicalAddress {addressLine1, postalCode, city, country {id}},
invoiceEmail, invoiceSendMethod (EMAIL/EHF/PAPER), invoicesDueIn (int),
invoicesDueInType (DAYS/MONTHS), isSupplier (bool).

### POST /product
Create product. Key fields: name, number, description, ean,
priceExcludingVatCurrency (number), priceIncludingVatCurrency (number),
costExcludingVatCurrency (number), vatType {id}, productUnit {id},
isStockItem (bool), currency {id}, account {id}, department {id}.
Common vatType IDs: check with GET /ledger/vatType.

### PUT /ledger/account/{id}
Update a ledger account. Use this to register the company bank account (required before invoicing).
Account 1920 "Bankinnskudd" already exists in every sandbox but has no bank number.
Steps: 1) GET /ledger/account?number=1920 to find its id. 2) PUT /ledger/account/{id} with:
bankAccountNumber (valid 11-digit, use "19201234568" as default), bankAccountCountry {id} (161),
currency {id} (1 for NOK). Do NOT try POST (account 1920 already exists, POST will 422).

### GET /token/session/>whoAmI
Get the logged-in user info. Response: {"value": {"employee": {"id": <int>}, "companyId": <int>}}.
Use value.employee.id as projectManager when creating projects (this user has full access).

### POST /department
Create department. Fields: name, departmentNumber, departmentManager {id}.

### POST /contact
Create contact. Fields: firstName, lastName, email,
phoneNumberMobile, customer {id}, department {id}.

### POST /invoice
Create invoice. Can include orders inline. Fields: invoiceDate (YYYY-MM-DD),
invoiceDueDate (YYYY-MM-DD), customer {id}, comment,
orders [{customer {id}, orderDate, deliveryDate (REQUIRED!), orderLines [{description, count, unitPriceExcludingVatCurrency, vatType {id}, product {id}}]}].
After creation, you may need to send the invoice.

### POST /order
Create order. Fields: customer {id}, orderDate (YYYY-MM-DD), deliveryDate (REQUIRED!),
department {id}, project {id}, invoiceComment, ourContactEmployee {id},
orderLines [{product {id}, description, count (number),
unitPriceExcludingVatCurrency (number), vatType {id}, discount}].

### POST /order/orderline
Create order line. Fields: order {id}, product {id}, description,
count (number), unitPriceExcludingVatCurrency (number), vatType {id}.

### POST /project
Create project. REQUIRED: name, projectManager {id}, isInternal (bool), startDate (YYYY-MM-DD).
The projectManager MUST be the sandbox admin employee. Get the id via GET /token/session/>whoAmI.
Do NOT create a new employee as projectManager (sandbox permissions will deny it).
Other fields: number, description, department {id}, endDate, customer {id},
isFixedPrice (bool), projectCategory {id}.

### POST /travelExpense
Create travel expense. REQUIRED: employee {id}.
Fields: employee {id}, project {id}, department {id}, title (string, short description),
isChargeable (bool), travelAdvance (number).
IMPORTANT: Do NOT include costs inline. Create the expense first with just employee and title,
then add costs separately with POST /travelExpense/cost. This avoids complex nested JSON.
NOTE: paymentType MUST be {id: <int>}. Look up valid IDs with GET /travelExpense/paymentType.
NOTE: Use "comments" for cost descriptions, NOT "description" (that field does not exist).

### POST /travelExpense/cost
Create travel expense cost. Fields: travelExpense {id}, vatType {id},
currency {id}, costCategory {id}, paymentType {id} (MUST be object with id, NOT a string),
date (YYYY-MM-DD), amountCurrencyIncVat (number, REQUIRED),
comments (string, NOT "description"), isChargeable (bool).

### GET /travelExpense/paymentType
List payment types for travel expenses. Returns [{id, description}]. Use the id in paymentType {id} fields.

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
WARNING: Returns 405 Method Not Allowed via competition proxy. Do NOT attempt this call.
If the task asks to enable a module, skip the module step and only create the department.

### GET /invoice
Search invoices. REQUIRED query params: invoiceDateFrom (YYYY-MM-DD), invoiceDateTo (YYYY-MM-DD).
Optional: invoiceNumber, customerId. Use a wide date range like invoiceDateFrom=2020-01-01&invoiceDateTo=2030-12-31 to find all invoices.

### GET /order
Search orders.

### GET /division
List divisions. Needed for employment creation.

### GET /salary/type
List salary types.

### GET /ledger/account
List chart of accounts. Query params: number, isApplicableForSupplierInvoice.

### GET /invoice/paymentType
List payment types for INCOMING invoice payments. Returns [{id, description}].
Use the id as paymentTypeId when registering payments on invoices via PUT /invoice/{id}/:payment.
Common types: "Kontant" (cash), "Betalt til bank" (bank payment).
WARNING: Do NOT use GET /ledger/paymentTypeOut for invoice payments (those are outgoing/expense types).

### GET /ledger/paymentTypeOut
List payment types for OUTGOING payments (paying bills/expenses). Do NOT use for invoice payments.

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

# ---------------------------------------------------------------------------
# System Prompt (behavioral instructions for the LLM)
#
# The API reference above covers what fields exist and what's required.
# This prompt covers HOW the agent should behave: workflow, defaults,
# data conversion, and task-specific sequences.
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = f"""You are an expert AI accounting agent for Tripletex, a Norwegian accounting system.
You receive accounting task prompts in 7 languages (Norwegian Bokmal, Nynorsk, English, Spanish, Portuguese, German, French) and must execute the correct API calls.

## Your Workflow
1. Read the task prompt carefully. Extract ALL field values mentioned.
2. Determine which Tripletex API calls are needed.
3. Execute them using the tripletex_api tool. Plan before calling to minimize API calls.
4. When you need reference data (VAT types, currencies, countries, divisions, payment types), make ONE lookup call, then reuse the IDs.

## Function Call JSON Rules (CRITICAL)
When generating function call arguments:
- All string values must be properly JSON-escaped (replace newlines with \\n, quotes with \\")
- Ensure all JSON braces and quotes are balanced
- Do NOT nest objects in the body string unnecessarily. Keep JSON flat and simple.
- Output the exact function name "tripletex_api" as defined.

## Sandbox Rules
The sandbox is mostly fresh and empty, but some tasks have pre-populated data.
- For CREATE tasks (create employee, customer, product, department, project): do NOT search first. Create directly.
- For PAYMENT and CREDIT NOTE tasks: the customer and invoice ALREADY EXIST in the sandbox. Find them with GET, then act on them. Do NOT create new invoices. Always use count=5 on search queries to limit response size.
- For DELETE tasks: the prompt tells you to delete something. If the entity should already exist (e.g., "delete the employee"), use GET to find it. If not found, create it first then delete it.
- System entities that always exist: account 1920, admin employee (via whoAmI), countries, currencies, vatTypes, divisions, payment types.
- Do NOT make GET calls to verify entities you just created (wastes API calls).
- Every 4xx error hurts your efficiency score. Validate inputs before sending.

## Mandatory Defaults
These fields are required but easy to forget:
- POST /customer: include "isCustomer": true (without this, the entity is NOT a customer).
- POST /employee: include "department": {{"id": X}} and "userType": "NO_ACCESS" (unless prompt specifies a role). If userType is "STANDARD" or "EXTENDED", "email" is REQUIRED (use "employee@company.no" if none given). If the prompt says administrator/kontoadministrator, use "STANDARD" or "EXTENDED".
- POST /order (standalone or inline): include "deliveryDate" in YYYY-MM-DD format. If not in the prompt, use the same date as orderDate or invoiceDate (already converted to YYYY-MM-DD).
- POST /project: include "projectManager": {{"id": X}}, "isInternal": true (unless external), "startDate" (today if not specified). For the projectManager, use the sandbox admin employee: call GET /token/session/>whoAmI to get the employee id. Do NOT create a new employee as project manager (they won't have the right access).
- POST /travelExpense costs: paymentType MUST be {{"id": X}} (integer, not string). Look up IDs with GET /travelExpense/paymentType first. Use "comments" for descriptions, NOT "description".

## Data Format Conversion
- Dates: DD.MM.YYYY in prompt -> YYYY-MM-DD for API.
- Numbers: "1.000,50" in prompt -> 1000.50 for API.
- Phone numbers: "phoneNumberMobile" for 8-digit numbers starting with 4 or 9 (or if prompt says "mobil"); "phoneNumber" for all other numbers (or if prompt says "telefon").

## Invoicing Sequence (follow exactly)
1. Create customer (POST /customer with isCustomer: true)
2. Register bank account: GET /ledger/account?number=1920 to find the account id, then PUT /ledger/account/{{id}} with bankAccountNumber "19201234568" (or prompt value if given), bankAccountCountry {{"id": 161}}, currency {{"id": 1}}. Do NOT use POST (account 1920 already exists).
3. Use these common vatType IDs (no lookup needed): 25% standard = id 3, 15% food = id 31, 12% transport = id 32, 0% exempt = id 5. Only call GET /ledger/vatType if you need an unusual rate.
4. Create invoice with inline orders and orderLines (POST /invoice)
Skipping step 2 causes a 422 error.

## Payment Registration Sequence
For tasks that say "register payment" or "registrer betaling" on an existing invoice:
1. The customer and invoice ALREADY EXIST. First find the customer: GET /customer?name=<name>&count=5. Then find their invoice: GET /invoice?customerId=<id>&invoiceDateFrom=2020-01-01&invoiceDateTo=2030-12-31&count=5.
2. Look up INCOMING payment types: GET /invoice/paymentType. Use "Betalt til bank" (bank payment). Do NOT use /ledger/paymentTypeOut (that is for outgoing payments, wrong direction).
3. Register payment: PUT /invoice/{{id}}/:payment with query params: paymentDate=YYYY-MM-DD, paidAmount=<amount>, paidAmountCurrency=<amount>, paymentTypeId=<id>.
Do NOT create a new invoice. The invoice already exists in the sandbox.

## Credit Note Sequence
For tasks that say "create credit note" or "kreditnota" for an existing invoice:
1. Find the invoice: GET /invoice?invoiceDateFrom=2020-01-01&invoiceDateTo=2030-12-31
2. Create credit note: PUT /invoice/{id}/:createCreditNote with query params: date=YYYY-MM-DD, comment=<reason>.

## Travel Expense Sequence
1. Create or find the employee (POST /employee or GET /employee)
2. Look up payment types: GET /travelExpense/paymentType (pick the first one)
3. Create travel expense with just employee and title: POST /travelExpense
4. Add each cost separately: POST /travelExpense/cost with travelExpense {{id}}, paymentType {{id}}, amountCurrencyIncVat, currency {{id: 1}}, date
Do NOT include costs inline in the travelExpense POST. Always add them as separate calls.

## Employment Details Sequence
If the prompt mentions arslonn/salary, stillingsprosent/percentage, startdato/start date, or ansettelse/employment:
1. Create department: POST /department
2. Create employee WITH dateOfBirth (use "1990-01-15" if not in prompt): POST /employee
3. Create employment (division NOT needed): POST /employee/employment with {{"employee": {{"id": <emp_id>}}, "startDate": "<YYYY-MM-DD>", "isMainEmployer": true}}
4. Create employment details: POST /employee/employment/details with {{"employment": {{"id": <emp_id>}}, "date": "<same as startDate>", "employmentType": "ORDINARY", "percentageOfFullTimeEquivalent": <number>, "annualSalary": <number>}}
NEVER skip steps 3-4 when salary or percentage is mentioned.

## Norwegian Accounting Conventions
- VAT (MVA/moms): 25% standard, 15% food, 12% transport/hotels, 0% exempt
- Currency: NOK | Fiscal year: Jan 1 - Dec 31
- Organization numbers: 9 digits | National identity numbers: 11 digits (DDMMYY + 5)
- Bank account numbers: 11 digits (XXXX.XX.XXXXX)

## Language Vocabulary
- Ansatt/tilsett = Employee | Kunde = Customer | Produkt/vare = Product
- Faktura = Invoice | Avdeling = Department | Prosjekt = Project
- Reiseregning = Travel expense | Betaling = Payment
- Kreditnota = Credit note | Slett/fjern = Delete
- Opprett/lag = Create | Oppdater/endre = Update
- Stillingsprosent = Employment percentage | Arslonn = Annual salary
- Organisasjonsnummer = Organization number | Personnummer = National ID

{TRIPLETEX_API_REFERENCE}

## Response Format
After completing all API calls, respond with a brief summary of what was done.
If you encounter an unresolvable error, explain what went wrong.
"""

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
            elif pair.strip():
                log.warning("Malformed query param (no '='), dropped: '%s'", pair)

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
            params=params or None,
            auth=auth,
            headers={"Content-Type": "application/json; charset=utf-8"} if json_body is not None else {},
            timeout=30.0,
        )

        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError):
            log.warning(
                "Non-JSON response from %s %s (status=%d): %s",
                method, path, response.status_code, response.text[:200],
            )
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
        elif response.status_code >= 500:
            result["error"] = data
            log.error("Tripletex SERVER ERROR: %s %s -> %d: %s",
                      method, path, response.status_code, str(data)[:500])
        else:
            result["error"] = data
            log.warning("API client error: %s %s -> %d: %s",
                        method, path, response.status_code, str(data)[:300])

        return result

    except httpx.TimeoutException:
        log.error("Tripletex API timeout: %s %s (30s)", method, path)
        return {"error": "Request timed out after 30s", "status_code": 408}
    except httpx.ConnectError as e:
        log.error("Tripletex API connection error: %s %s: %s", method, path, e)
        return {"error": f"Connection failed: {e}", "status_code": 503}
    except Exception as e:
        log.error("Tripletex API unexpected error: %s %s: %s\n%s",
                  method, path, e, traceback.format_exc())
        return {"error": str(e), "status_code": 500}


def validate_and_fix_body(method: str, path: str, body: str | None) -> str | None:
    """Intercept and fix common LLM mistakes in API call bodies.

    Gemini sometimes ignores system prompt instructions. This catches
    known errors before they hit the API and waste efficiency score.
    """
    if not body or method not in ("POST", "PUT"):
        return body

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return body  # Can't fix invalid JSON

    changed = False

    # POST /customer: isCustomer MUST be true
    if method == "POST" and "/customer" in path and "customer" in path.split("/")[-1]:
        if not data.get("isCustomer"):
            data["isCustomer"] = True
            changed = True
            log.info("VALIDATOR: Added isCustomer=true to customer POST")

    # POST /product: fix common vatType errors
    if method == "POST" and "/product" in path:
        vat = data.get("vatType", {})
        vat_id = vat.get("id") if isinstance(vat, dict) else None
        # id=5 is 0% exempt, id=6 is "utgående mva høy sats" which is wrong
        # Standard 25% = id 3. If LLM picked 5 or 6, fix to 3.
        if vat_id in (5, 6):
            data["vatType"] = {"id": 3}
            changed = True
            log.info("VALIDATOR: Fixed vatType from %d to 3 (25%% standard)", vat_id)

    # POST /employee: ensure department exists
    if method == "POST" and path.rstrip("/") == "/employee":
        if not data.get("department"):
            log.warning("VALIDATOR: Employee POST missing department (LLM forgot)")

    # POST /invoice: ensure deliveryDate on inline orders
    if method == "POST" and "/invoice" in path:
        for order in data.get("orders", []):
            if not order.get("deliveryDate") and order.get("orderDate"):
                order["deliveryDate"] = order["orderDate"]
                changed = True
                log.info("VALIDATOR: Added deliveryDate from orderDate on inline order")

    if changed:
        return json.dumps(data, ensure_ascii=False)
    return body


def truncate_result(result: dict[str, Any], max_chars: int = 8000) -> str:
    """Serialize an API result to JSON, truncating if it exceeds max_chars."""
    result_str = json.dumps(result, default=str, ensure_ascii=False)
    if len(result_str) <= max_chars:
        return result_str

    if isinstance(result.get("data"), list) and len(result["data"]) > 10:
        result["data"] = result["data"][:10]
        result["_truncated"] = True
        result_str = json.dumps(result, default=str, ensure_ascii=False)

    if len(result_str) > max_chars:
        log.warning("API response >%d chars (%d). Hard-truncating.", max_chars, len(result_str))
        result_str = result_str[:max_chars - 10] + '..."}'

    return result_str


async def run_agent(
    prompt: str,
    files: list[dict] | None,
    base_url: str,
    session_token: str,
) -> dict[str, Any]:
    """Run the Gemini agent loop to solve an accounting task."""

    t0 = time.time()
    api_calls = 0
    errors_4xx = 0

    user_parts: list[types.Part] = []
    user_parts.append(types.Part.from_text(text=f"Task prompt:\n{prompt}"))

    if files:
        for f in files:
            filename = f.get("filename", "unknown")
            content_b64 = f.get("content_base64", "")
            mime_type = f.get("mime_type", "application/octet-stream")

            if not content_b64:
                log.warning("File '%s' has no content_base64. Task may need this file.", filename)
                user_parts.append(types.Part.from_text(
                    text=f"[File {filename} was provided but contained no data]"
                ))
                continue

            try:
                raw_bytes = base64.b64decode(content_b64)
                user_parts.append(types.Part.from_bytes(data=raw_bytes, mime_type=mime_type))
                log.info("Attached file: %s (%s, %d bytes)", filename, mime_type, len(raw_bytes))
            except Exception as e:
                log.warning("Failed to decode file %s: %s", filename, e)
                user_parts.append(types.Part.from_text(
                    text=f"[File {filename} could not be decoded: {e}]"
                ))

    contents: list[types.Content] = [
        types.Content(role="user", parts=user_parts),
    ]
    agent_completed = False
    consecutive_malformed = 0
    current_model = GEMINI_MODEL

    async with httpx.AsyncClient() as http_client:
        for turn in range(MAX_AGENT_TURNS):
            elapsed = time.time() - t0
            if elapsed > DEADLINE_SECONDS:
                log.warning("Approaching 300s timeout (%.0fs elapsed), stopping agent loop", elapsed)
                break

            log.info("Agent turn %d (api_calls=%d, errors=%d, elapsed=%.0fs, model=%s)",
                     turn + 1, api_calls, errors_4xx, elapsed, current_model)

            try:
                response = await asyncio.to_thread(
                    gemini_client.models.generate_content,
                    model=current_model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        tools=[TRIPLETEX_TOOL],
                        temperature=0.0,
                        max_output_tokens=8192,
                    ),
                )
            except Exception as e:
                log.error("Gemini API error on turn %d: %s", turn + 1, e)
                return {
                    "status": "error",
                    "error": f"LLM error: {e}",
                    "api_calls": api_calls,
                    "errors_4xx": errors_4xx,
                    "elapsed_seconds": time.time() - t0,
                }

            if not response.candidates:
                log.error("SCORING-ZERO: Gemini returned NO candidates. "
                          "Possible safety filter or quota issue.")
                break

            candidate = response.candidates[0]

            reason = getattr(candidate.finish_reason, "name", None)
            if reason and reason in ("MALFORMED_FUNCTION_CALL", "UNEXPECTED_TOOL_CALL"):
                consecutive_malformed += 1
                log.warning("Gemini %s on turn %d (streak=%d, model=%s).",
                            reason, turn + 1, consecutive_malformed, current_model)
                if consecutive_malformed >= 3:
                    if current_model != GEMINI_FALLBACK_MODEL:
                        # Switch to more reliable pro model
                        current_model = GEMINI_FALLBACK_MODEL
                        log.warning("Switching to fallback model: %s", current_model)
                    # Also inject a hint to simplify
                    contents.append(types.Content(role="user", parts=[
                        types.Part.from_text(
                            text="Your function call JSON was malformed. "
                                 "Simplify: use flat JSON, no nested strings. "
                                 "Ensure all braces and quotes are balanced."
                        ),
                    ]))
                    consecutive_malformed = 0
                continue
            else:
                consecutive_malformed = 0

            if reason and reason not in ("STOP", "MAX_TOKENS", "FINISH_REASON_UNSPECIFIED"):
                log.error("Gemini finish_reason=%s. Content may have been blocked.", reason)

            if not candidate.content or not candidate.content.parts:
                log.warning("Gemini empty content on turn %d. Retrying.", turn + 1)
                continue  # Retry instead of breaking

            function_calls = [p for p in candidate.content.parts if p.function_call]

            if not function_calls:
                text_parts = [p.text for p in candidate.content.parts if p.text]
                log.info("Agent completed: %s", " ".join(text_parts)[:200])
                agent_completed = True
                break

            contents.append(candidate.content)
            function_responses: list[types.Part] = []
            for fc_part in function_calls:
                fc = fc_part.function_call
                args = dict(fc.args) if fc.args else {}

                method = args.get("method")
                path = args.get("path")

                if not method or not path:
                    log.error("LLM emitted function call without method/path: args=%s", args)
                    function_responses.append(
                        types.Part.from_function_response(
                            name=fc.name,
                            response={"result": json.dumps({
                                "error": "Missing required argument 'method' or 'path'",
                                "status_code": 400,
                            })},
                        )
                    )
                    continue

                body_str = validate_and_fix_body(method, path, args.get("body"))
                log.info("Calling: %s %s body=%s", method, path, (body_str or "")[:200])

                result = await call_tripletex(
                    client=http_client,
                    base_url=base_url,
                    session_token=session_token,
                    method=method,
                    path=path,
                    body=body_str,
                    query_params=args.get("query_params"),
                )

                api_calls += 1
                status = result.get("status_code", 0)
                if 400 <= status < 500:
                    errors_4xx += 1

                function_responses.append(
                    types.Part.from_function_response(
                        name=fc.name,
                        response={"result": truncate_result(result)},
                    )
                )

            contents.append(types.Content(role="user", parts=function_responses))

    if not agent_completed:
        log.error("TURN-LIMIT: Agent did not complete naturally. "
                  "api_calls=%d, errors_4xx=%d, turns=%d",
                  api_calls, errors_4xx, MAX_AGENT_TURNS)

    elapsed = time.time() - t0
    log.info("Done: %d API calls, %d 4xx errors, %.1fs elapsed, completed=%s",
             api_calls, errors_4xx, elapsed, agent_completed)

    return {
        "status": "completed" if agent_completed else "incomplete",
        "api_calls": api_calls,
        "errors_4xx": errors_4xx,
        "elapsed_seconds": elapsed,
    }


@app.get("/health")
async def health():
    return {"status": "ok", "model": GEMINI_MODEL}


@app.post("/solve")
async def solve(request: Request):
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError) as e:
        log.warning("Invalid JSON in request body: %s", e)
        return JSONResponse({"status": "completed"})
    except Exception as e:
        log.error("Failed to read request body: %s", e)
        return JSONResponse({"status": "completed"})

    prompt = body.get("prompt", "")
    files = body.get("files", [])
    creds = body.get("tripletex_credentials", {})
    base_url = creds.get("base_url", "")
    session_token = creds.get("session_token", "")

    if not prompt or not base_url or not session_token:
        log.error("Missing required fields. prompt=%d, base_url=%d, token=%d",
                  len(prompt), len(base_url), len(session_token))
        return JSONResponse({"status": "completed"})

    log.info("=== SOLVE: prompt_len=%d, files=%d ===", len(prompt), len(files))
    log.info("Prompt: %s", prompt[:300])

    try:
        result = await run_agent(
            prompt=prompt,
            files=files,
            base_url=base_url,
            session_token=session_token,
        )
        log.info("Agent result: status=%s, api_calls=%s, errors_4xx=%s, elapsed=%.1fs",
                 result.get("status"), result.get("api_calls"),
                 result.get("errors_4xx"), result.get("elapsed_seconds", 0))
        return JSONResponse({"status": "completed"})
    except Exception as e:
        log.error("AGENT-CRASH: Agent crashed. Returning 'completed' but work may be incomplete. "
                  "Error: %s\n%s", e, traceback.format_exc())
        # Bad runs never lower score; returning error risks the platform not scoring at all
        return JSONResponse({"status": "completed"})


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
