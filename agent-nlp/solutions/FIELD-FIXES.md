# Field-Level Fixes: Top 3 Issues from Cloud Run Logs

Analysis of 400 lines of Cloud Run logs from 2026-03-20 22:36-23:03 UTC.
Focus: tasks that were correctly identified but scored partially due to field/API bugs.

---

## Issue 1: `exec_create_employee` sends `employmentType` in employment POST body (rejected by API)

**Executor:** `exec_create_employee` (line 413)

**What happens:**
When `create_employee` is routed (not `create_employee_with_employment`) and the prompt
includes a `startDate`, the code creates employment with `"employmentType": "ORDINARY"` in
the POST body to `/employee/employment`. The Tripletex API rejects this field:

```
POST /employee/employment -> 422
validationMessages: [{'field': 'employmentType', 'message': 'Feltet eksisterer ikke i objektet.'}]
```

This was seen twice in the logs (Nathan Moreau at 22:38:48, Miguel Sanchez at 22:41:10).
The employee is created successfully, but employment creation fails silently, so any
employment-related fields (startDate, employmentPercentage) are lost from the scored result.

**Root cause:** `employmentType` is NOT a valid field on `/employee/employment`. It belongs
on `/employee/employment/details` only. Compare with `exec_create_employee_with_employment`
(line 459) which correctly omits it from the employment POST.

**Suggested fix (line 413-416):**
Change from:
```python
emp_r = await tx(c, base, tok, "POST", "/employee/employment", {
    "employee": {"id": emp_id},
    "startDate": start_date,
    "employmentType": "ORDINARY",
})
```
To:
```python
emp_r = await tx(c, base, tok, "POST", "/employee/employment", {
    "employee": {"id": emp_id},
    "startDate": start_date,
    "isMainEmployer": True,
})
```

---

## Issue 2: `exec_create_department` crashes when Gemini returns `departmentName` as a list instead of using `departments` array

**Executor:** `exec_create_department` (line 506-527)

**What happens:**
When prompted to create multiple departments (e.g., "Erstellen Sie drei Abteilungen:
Logistikk, Salg, Drift"), Gemini sometimes returns:
```json
{"departmentName": ["Logistikk", "Salg", "Drift"]}
```
instead of the expected:
```json
{"departments": [{"departmentName": "Logistikk"}, ...]}
```

The code at line 524 does `body = {"name": f.get("departmentName") or f.get("name", "")}`,
which passes the list directly as the `name` field. The API rejects it:

```
POST /department -> 422: 'name': 'Verdien er ikke av korrekt type for dette feltet.'
```

A second variant (line 283 in logs): Gemini returns a bare list instead of a dict, causing
`'list' object has no attribute 'get'` which falls through to `unknown` and the fallback
agent.

**Suggested fix (add before line 524):**
```python
dept_name = f.get("departmentName") or f.get("name", "")
if isinstance(dept_name, list):
    # LLM returned flat list of names instead of departments array
    last_r = {"success": False, "error": "No departments"}
    for i, n in enumerate(dept_name):
        last_r = await tx(c, base, tok, "POST", "/department", {"name": n, "departmentNumber": i + 1})
    return last_r
```

---

## Issue 3: `exec_create_dimension` voucher POST sends single posting (always 422: "Et bilag kan ikke registreres uten posteringer")

**Executor:** `exec_create_dimension` (line 1009-1014)

**What happens:**
Every single `create_dimension` task that includes a voucher posting fails with the same
422 error:

```
POST /ledger/voucher -> 422: 'postings': 'Et bilag kan ikke registreres uten posteringer.'
```

Translation: "A voucher cannot be registered without postings."

This error occurs even though the code IS sending a `postings` array with one item. The
real problem is that the Tripletex API requires a BALANCED voucher: a voucher needs at
least TWO postings that balance to zero (debit + credit). The code sends only one posting
(the expense side) but never sends the balancing posting (credit side).

Seen 4 times in the logs (accounts 6590, 7100, 7140, 7300), failing every time.

**Suggested fix (line 1009-1014):**
Change from:
```python
posting = {"account": {"id": acct_id}, "amountGross": float(post_amount), ...}
return await tx(c, base, tok, "POST", "/ledger/voucher", {
    "date": post_date, "description": description, "postings": [posting]})
```
To:
```python
posting_debit = {"account": {"id": acct_id}, "amountGross": float(post_amount),
                 "amountGrossCurrency": float(post_amount), "currency": {"id": 1},
                 "description": description, "date": post_date}
if target_dept_id: posting_debit["department"] = {"id": target_dept_id}
# Balancing credit posting on account 2400 (leverandorgjeld / accounts payable)
credit_acct_r = await tx(c, base, tok, "GET", "/ledger/account", params={"number": 2400})
credit_acct_id = as_list(credit_acct_r["data"])[0]["id"] if credit_acct_r.get("success") and credit_acct_r.get("data") else None
if credit_acct_id:
    posting_credit = {"account": {"id": credit_acct_id}, "amountGross": -float(post_amount),
                      "amountGrossCurrency": -float(post_amount), "currency": {"id": 1},
                      "description": description, "date": post_date}
    return await tx(c, base, tok, "POST", "/ledger/voucher", {
        "date": post_date, "description": description,
        "postings": [posting_debit, posting_credit]})
```

---

## Bonus: Other issues spotted (lower priority)

**A. `register_supplier_invoice` also sends `dueDate` which the API rejects:**
Line 959: `sup_inv_body = {..., "dueDate": invoice_date, ...}`. The supplierInvoice
endpoint does not have a `dueDate` field (error: "Feltet eksisterer ikke i objektet").
Fix: change `"dueDate"` to `"paymentDueDate"` or remove it entirely.

**B. `process_salary` fails to create employment when employee already exists:**
Line 122-123 in logs: `employee.dateOfBirth` is required for employment creation. When the
employee was pre-found via GET (not created by the bot), their dateOfBirth is not fetched
or set. The employment POST fails with "dateOfBirth: Feltet ma fylles ut."
Fix: After finding existing employee via GET, also PUT to set dateOfBirth if needed, or
include it in the employment POST body.

**C. "Register supplier" tasks fall through to `unknown`:**
Prompts like "Register the supplier Silveroak Ltd" get classified as `unknown` because
there is no `create_supplier` task type. The extraction prompt lists `register_supplier_invoice`
but that is for invoices from suppliers, not for creating the supplier entity itself.
Fix: Add `create_supplier` to the task types in the extraction prompt, or teach the LLM
to map "register supplier" to `create_customer` with `isSupplier: true`.
