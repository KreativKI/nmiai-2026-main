"""
QC Verification Script for Tripletex Bot

Sends test prompts to the bot endpoint, then queries the Tripletex sandbox
API to verify that entities were created with the correct fields.

This is the real QC: not just "did it return 200" but "did it create
the right entity with the right data."

Usage:
    python3 scripts/qc-verify.py [endpoint]
    Default endpoint: http://localhost:8080
"""

import json
import os
import sys
import time
import uuid

import httpx

ENDPOINT = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"

# Load sandbox credentials
env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
env_vars = {}
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip()

TX_BASE = env_vars.get("TRIPLETEX_BASE_URL", "")
TX_TOKEN = env_vars.get("TRIPLETEX_SESSION_TOKEN", "")

if not TX_BASE or not TX_TOKEN:
    print("ERROR: Missing TRIPLETEX_BASE_URL or TRIPLETEX_SESSION_TOKEN in .env")
    sys.exit(1)

AUTH = ("0", TX_TOKEN)
RUN_ID = uuid.uuid4().hex[:6]

PASS_COUNT = 0
FAIL_COUNT = 0
RESULTS = []


def tx_get(path, params=None):
    """Query Tripletex sandbox API."""
    r = httpx.get(f"{TX_BASE}{path}", auth=AUTH, params=params, timeout=15)
    return r.json()


def solve(prompt, timeout=90):
    """Send a prompt to the bot endpoint."""
    r = httpx.post(
        f"{ENDPOINT}/solve",
        json={
            "prompt": prompt,
            "files": [],
            "tripletex_credentials": {
                "base_url": TX_BASE,
                "session_token": TX_TOKEN,
            },
        },
        timeout=timeout,
    )
    return r.json(), r.elapsed.total_seconds()


def verify(name, prompt, check_fn, timeout=90):
    """Run a test: send prompt, then verify with check function."""
    global PASS_COUNT, FAIL_COUNT
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"Prompt: {prompt[:100]}...")

    try:
        result, elapsed = solve(prompt, timeout)
        print(f"Response: {result} ({elapsed:.1f}s)")
    except Exception as e:
        print(f"FAIL: endpoint error: {e}")
        FAIL_COUNT += 1
        RESULTS.append({"name": name, "status": "FAIL", "reason": f"endpoint error: {e}"})
        return

    time.sleep(0.5)

    try:
        passed, details = check_fn()
        if passed:
            print(f"QC PASS: {details}")
            PASS_COUNT += 1
            RESULTS.append({"name": name, "status": "PASS", "details": details, "time": f"{elapsed:.1f}s"})
        else:
            print(f"QC FAIL: {details}")
            FAIL_COUNT += 1
            RESULTS.append({"name": name, "status": "FAIL", "reason": details, "time": f"{elapsed:.1f}s"})
    except Exception as e:
        print(f"QC FAIL: verification error: {e}")
        FAIL_COUNT += 1
        RESULTS.append({"name": name, "status": "FAIL", "reason": f"verification error: {e}"})


# ---------------------------------------------------------------------------
# Test cases with field-level verification
# ---------------------------------------------------------------------------

def test_create_customer():
    cust_name = f"QCKunde{RUN_ID}"
    org_nr = str(900000000 + int(RUN_ID[:6], 16) % 99999999)[:9]
    email = f"post@{RUN_ID}.no"

    def check():
        data = tx_get("/customer", {"name": cust_name})
        customers = [c for c in data.get("values", []) if c.get("name") == cust_name]
        if not customers:
            return False, f"Customer '{cust_name}' not found (exact match)"
        c = customers[0]
        issues = []
        if not c.get("isCustomer"):
            issues.append("isCustomer is false/missing (CRITICAL: scored field)")
        if c.get("email") != email:
            issues.append(f"email: expected '{email}', got '{c.get('email')}'")
        if not c.get("phoneNumber") and not c.get("phoneNumberMobile"):
            issues.append("no phone number set (phoneNumber or phoneNumberMobile)")
        if issues:
            return False, "; ".join(issues)
        return True, f"Customer '{cust_name}' OK (isCustomer=true, email={email})"

    verify(
        "Create Customer",
        f"Registrer en kunde med navn {cust_name}, e-post {email}, telefon 22334455.",
        check,
    )


def test_create_employee():
    emp_first = "QCansatt"
    emp_last = f"Test{RUN_ID}"
    email = f"qc{RUN_ID}@firma.no"

    def check():
        data = tx_get("/employee", {"firstName": emp_first, "lastName": emp_last})
        employees = data.get("values", [])
        if not employees:
            return False, f"Employee '{emp_first} {emp_last}' not found"
        e = employees[0]
        issues = []
        if e.get("firstName") != emp_first:
            issues.append(f"firstName: expected '{emp_first}', got '{e.get('firstName')}'")
        if e.get("lastName") != emp_last:
            issues.append(f"lastName: expected '{emp_last}', got '{e.get('lastName')}'")
        if e.get("email") != email:
            issues.append(f"email: expected '{email}', got '{e.get('email')}'")
        if not e.get("department", {}).get("id"):
            issues.append("department not set")
        if issues:
            return False, "; ".join(issues)
        return True, f"Employee '{emp_first} {emp_last}' OK (email={email})"

    verify(
        "Create Employee",
        f"Opprett en ansatt med navn {emp_first} {emp_last}, e-post {email}, mobilnummer 91234567.",
        check,
    )


def test_create_product():
    prod_name = f"QCProdukt{RUN_ID}"
    prod_num = f"QC{RUN_ID[:4]}"

    def check():
        data = tx_get("/product", {"name": prod_name})
        products = [p for p in data.get("values", []) if p.get("name") == prod_name]
        if not products:
            return False, f"Product '{prod_name}' not found"
        p = products[0]
        issues = []
        price = p.get("priceExcludingVatCurrency", 0)
        if abs(price - 1500.0) > 0.01:
            issues.append(f"price: expected 1500.0, got {price}")
        vat = p.get("vatType", {})
        if not vat or not vat.get("id"):
            issues.append("vatType not set (scored field)")
        if issues:
            return False, "; ".join(issues)
        return True, f"Product '{prod_name}' OK (price=1500, vatType={vat.get('id')})"

    verify(
        "Create Product",
        f"Opprett et produkt med navn {prod_name}, produktnummer {prod_num}, pris 1500 kr eks. mva. Standard mva-sats.",
        check,
    )


def test_create_department():
    dept_name = f"QCAvd{RUN_ID}"
    dept_num = int(RUN_ID[:3], 16) % 900 + 100

    def check():
        data = tx_get("/department", {"name": dept_name})
        depts = [d for d in data.get("values", []) if d.get("name") == dept_name]
        if not depts:
            return False, f"Department '{dept_name}' not found"
        d = depts[0]
        issues = []
        actual_num = d.get("departmentNumber")
        if str(actual_num) != str(dept_num):
            issues.append(f"departmentNumber: expected {dept_num}, got {actual_num}")
        if issues:
            return False, "; ".join(issues)
        return True, f"Department '{dept_name}' OK (number={actual_num})"

    verify(
        "Create Department",
        f"Opprett en avdeling med navn {dept_name} og avdelingsnummer {dept_num}.",
        check,
    )


def test_create_project():
    proj_name = f"QCProsjekt{RUN_ID}"
    proj_num = f"P{RUN_ID[:4]}"

    # Get expected admin employee ID for comparison
    whoami = tx_get("/token/session/>whoAmI")
    expected_pm_id = whoami.get("value", {}).get("employee", {}).get("id")

    def check():
        data = tx_get("/project", {"name": proj_name})
        projects = [p for p in data.get("values", []) if p.get("name") == proj_name]
        if not projects:
            return False, f"Project '{proj_name}' not found"
        p = projects[0]
        issues = []
        pm = p.get("projectManager", {})
        pm_id = pm.get("id") if pm else None
        if not pm_id:
            issues.append("projectManager not set")
        elif expected_pm_id and pm_id != expected_pm_id:
            issues.append(f"projectManager: expected admin {expected_pm_id}, got {pm_id}")
        if not p.get("startDate"):
            issues.append("startDate not set")
        if issues:
            return False, "; ".join(issues)
        return True, f"Project '{proj_name}' OK (PM={pm_id}, startDate={p.get('startDate')})"

    verify(
        "Create Project",
        f"Opprett et prosjekt med navn {proj_name}, prosjektnummer {proj_num}.",
        check,
    )


def test_create_invoice():
    cust_name = f"QCFaktura{RUN_ID}"
    org_nr = str(967000000 + int(RUN_ID[:5], 16) % 999999)[:9]

    def check():
        cust_data = tx_get("/customer", {"name": cust_name})
        customers = [c for c in cust_data.get("values", []) if c.get("name") == cust_name]
        if not customers:
            return False, f"Customer '{cust_name}' not found"
        cust_id = customers[0]["id"]
        if not customers[0].get("isCustomer"):
            return False, "Customer created but isCustomer=false"

        inv_data = tx_get("/invoice", {
            "customerId": cust_id,
            "invoiceDateFrom": "2020-01-01",
            "invoiceDateTo": "2030-12-31",
        })
        invoices = inv_data.get("values", [])
        if not invoices:
            return False, f"No invoice found for customer {cust_id}"

        inv = invoices[0]
        issues = []
        amount = inv.get("amount", 0)
        expected_amount = 25000 * 1.25  # 25% VAT
        if abs(amount - expected_amount) > 100:
            issues.append(f"amount: expected ~{expected_amount}, got {amount}")
        if not inv.get("invoiceDueDate"):
            issues.append("invoiceDueDate not set")
        if issues:
            return False, "; ".join(issues)
        return True, f"Invoice OK for '{cust_name}' (amount={amount}, due={inv.get('invoiceDueDate')})"

    verify(
        "Create Invoice",
        f"Opprett en faktura til kunde {cust_name} (org.nr {org_nr}) pa 25000 kr eks. mva for Konsulenttjenester. Standard mva.",
        check,
        timeout=120,
    )


def test_create_travel_expense():
    emp_first = "QCReise"
    emp_last = f"Test{RUN_ID}"

    def check():
        emp_data = tx_get("/employee", {"firstName": emp_first, "lastName": emp_last})
        employees = emp_data.get("values", [])
        if not employees:
            return False, f"Employee '{emp_first} {emp_last}' not found"
        emp_id = employees[0]["id"]

        te_data = tx_get("/travelExpense", {"employeeId": emp_id})
        expenses = te_data.get("values", [])
        if not expenses:
            return False, f"No travel expense found for employee {emp_id}"

        te = expenses[0]
        issues = []
        if not te.get("title"):
            issues.append("title not set")
        # Check costs exist
        costs = te.get("costs", [])
        if not costs:
            issues.append("no costs attached (scored field)")
        if issues:
            return False, "; ".join(issues)
        cost_count = len(costs)
        return True, f"Travel expense OK: '{te.get('title')}' ({cost_count} costs)"

    verify(
        "Create Travel Expense",
        f"Opprett ansatt {emp_first} {emp_last} og registrer en reiseregning. Tittel: Kundebesok Bergen. Togbillett 800 kr inkl. mva.",
        check,
        timeout=120,
    )


def test_register_payment():
    """Test payment on an existing invoice (the highest-priority gap)."""
    # First create a customer + invoice that we'll pay
    cust_name = f"QCBetaling{RUN_ID}"
    org_nr = str(950000000 + int(RUN_ID[:5], 16) % 999999)[:9]
    amount = 10000

    # Step 1: Create the invoice via the bot
    print(f"\n{'='*60}")
    print(f"TEST: Register Payment (setup: creating invoice first)")
    solve(
        f"Opprett en faktura til kunde {cust_name} (org.nr {org_nr}) pa {amount} kr eks. mva for Renholdstjenester. Standard mva.",
        timeout=120,
    )
    time.sleep(1)

    # Find the invoice we just created
    cust_data = tx_get("/customer", {"name": cust_name})
    customers = [c for c in cust_data.get("values", []) if c.get("name") == cust_name]
    if not customers:
        print("QC FAIL: Setup failed - customer not created for payment test")
        global FAIL_COUNT
        FAIL_COUNT += 1
        RESULTS.append({"name": "Register Payment", "status": "FAIL", "reason": "setup: customer not created"})
        return

    cust_id = customers[0]["id"]
    inv_data = tx_get("/invoice", {
        "customerId": cust_id,
        "invoiceDateFrom": "2020-01-01",
        "invoiceDateTo": "2030-12-31",
    })
    invoices = inv_data.get("values", [])
    if not invoices:
        print("QC FAIL: Setup failed - invoice not created for payment test")
        FAIL_COUNT += 1
        RESULTS.append({"name": "Register Payment", "status": "FAIL", "reason": "setup: invoice not created"})
        return

    inv_id = invoices[0]["id"]
    inv_amount = invoices[0].get("amount", 0)
    print(f"Setup OK: invoice {inv_id}, amount={inv_amount}")

    # Step 2: Ask the bot to register payment
    def check():
        # Re-fetch the invoice to check payment status
        inv_data2 = tx_get("/invoice", {
            "customerId": cust_id,
            "invoiceDateFrom": "2020-01-01",
            "invoiceDateTo": "2030-12-31",
        })
        invoices2 = inv_data2.get("values", [])
        if not invoices2:
            return False, "Invoice disappeared after payment attempt"
        inv = invoices2[0]
        amount_due = inv.get("amountOutstanding", inv.get("amountRoundoff", -1))
        is_paid = inv.get("isPaid", False)
        if is_paid:
            return True, f"Invoice {inv_id} is fully paid"
        # Check if any payment was registered (amountOutstanding < original amount)
        if amount_due == 0:
            return True, f"Invoice {inv_id} has no outstanding amount"
        return False, f"Invoice {inv_id} not paid (isPaid={is_paid}, outstanding={amount_due})"

    verify(
        "Register Payment",
        f"Kunden {cust_name} (org.nr {org_nr}) har en utestaende faktura pa {inv_amount} kr for Renholdstjenester. Registrer full betaling pa denne fakturaen i dag.",
        check,
        timeout=120,
    )


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------

print(f"QC Verification Run: {RUN_ID}")
print(f"Endpoint: {ENDPOINT}")
print(f"Sandbox: {TX_BASE}")
print(f"{'='*60}")

test_create_customer()
test_create_employee()
test_create_product()
test_create_department()
test_create_project()
test_create_invoice()
test_create_travel_expense()
test_register_payment()

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

print(f"\n{'='*60}")
print(f"QC SUMMARY: {PASS_COUNT} passed, {FAIL_COUNT} failed out of {PASS_COUNT + FAIL_COUNT}")
print(f"{'='*60}")
for r in RESULTS:
    status = r["status"]
    name = r["name"]
    detail = r.get("details", r.get("reason", ""))
    t = r.get("time", "")
    marker = "PASS" if status == "PASS" else "FAIL"
    print(f"  [{marker}] {name} ({t}): {detail}")

if FAIL_COUNT > 0:
    print(f"\nVERDICT: BLOCK DEPLOY. {FAIL_COUNT} task(s) failed QC.")
    sys.exit(1)
else:
    print(f"\nVERDICT: PASS. All {PASS_COUNT} tasks verified against sandbox.")
    sys.exit(0)
