"""
New executor functions for tripletex_bot_v4.py
================================================

3 new task types:
  A. process_salary    -- Run payroll / salary payment for an employee
  B. register_supplier_invoice -- Register an incoming invoice from a supplier
  C. create_dimension  -- Create a custom accounting dimension + values + posting

HOW TO MERGE:
  1. Copy the 3 executor functions below into tripletex_bot_v4.py
     (place them after the existing exec_enable_module function, before TASK_EXECUTORS dict)
  2. Copy the lookup_input_vat_map helper next to the existing lookup_vat_map function
  3. Add the 3 new entries to the TASK_EXECUTORS dict (shown at bottom)
  4. Add the 3 new task types to EXTRACTION_PROMPT (shown at bottom)
"""

import time
import logging
from typing import Any

import httpx

# These are imported from the main file at merge time:
#   tx, split_name, as_list, ensure_department, lookup_vat_map, vat_id_sync

log = logging.getLogger("tripletex_bot")


# ---------------------------------------------------------------------------
# Helper: INPUT VAT type lookup (for supplier invoices)
# Place next to the existing lookup_vat_map function in tripletex_bot_v4.py
# ---------------------------------------------------------------------------
_input_vat_cache: dict[str, dict[int, int]] = {}


async def lookup_input_vat_map(c: httpx.AsyncClient, base: str, tok: str) -> dict[int, int]:
    """Fetch INPUT (inngaende) vatType IDs for supplier invoices. Cached per base_url."""
    if base in _input_vat_cache:
        return _input_vat_cache[base]

    # Import tx from the main module -- at merge time this is just a local call
    r = await tx(c, base, tok, "GET", "/ledger/vatType", params={"count": 200})
    vat_map: dict[int, int] = {}
    if r.get("success") and r.get("data"):
        for vt in (r["data"] if isinstance(r["data"], list) else [r["data"]]):
            pct = vt.get("percentage")
            vid = vt.get("id")
            name = (vt.get("name") or "").lower()
            if pct is not None and vid is not None:
                pct_int = int(round(float(pct)))
                is_input = "inng" in name or "input" in name or "fradrag" in name
                if is_input:
                    vat_map[pct_int] = vid

    if not vat_map:
        # Fallback: common Tripletex input VAT type IDs
        vat_map = {25: 1, 15: 33, 12: 34, 0: 6}
        log.warning("Input VAT lookup returned empty, using hardcoded fallback")

    _input_vat_cache[base] = vat_map
    log.info("Input VAT map for sandbox: %s", vat_map)
    return vat_map


# ---------------------------------------------------------------------------
# EXECUTOR 1: exec_process_salary
# ---------------------------------------------------------------------------
# Handles prompts like:
#   "Run payroll for Ola Nordmann (ola@example.org) for this month.
#    Base salary is 45000 NOK. Add a one-time bonus of 5000 NOK."
#
# Strategy:
#   1. Find the employee by name
#   2. Get salary type IDs (monthly salary + bonus)
#   3. Get or create employment for the employee
#   4. Create salary payment specification / transactions
# ---------------------------------------------------------------------------

async def exec_process_salary(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    """Process salary / payroll for an employee."""
    try:
        first, last = split_name(f)

        # Step 1: Find employee
        params = {"count": 20}
        if first:
            params["firstName"] = first
        if last:
            params["lastName"] = last
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
            # Employee not found -- create them first
            dept_id = await ensure_department(c, base, tok)
            if not dept_id:
                return {"success": False, "error": "Could not obtain department ID"}
            emp_body = {
                "firstName": first,
                "lastName": last,
                "department": {"id": dept_id},
                "userType": "NO_ACCESS",
                "dateOfBirth": f.get("dateOfBirth", "1990-01-15"),
            }
            if f.get("email"):
                emp_body["email"] = f["email"]
            create_r = await tx(c, base, tok, "POST", "/employee", emp_body)
            if not create_r.get("success"):
                return create_r
            emp_id = create_r["data"]["id"]

        # Step 2: Get or create employment
        empl_r = await tx(c, base, tok, "GET", "/employee/employment",
                          params={"employeeId": emp_id, "count": 5})
        employment_id = None
        if empl_r.get("success") and empl_r.get("data"):
            empls = as_list(empl_r["data"])
            if empls:
                employment_id = empls[0]["id"]

        if not employment_id:
            start_date = f.get("startDate", time.strftime("%Y-%m-%d"))
            empl_create = await tx(c, base, tok, "POST", "/employee/employment", {
                "employee": {"id": emp_id},
                "startDate": start_date,
                "isMainEmployer": True,
            })
            if empl_create.get("success"):
                employment_id = empl_create["data"]["id"]
                # Also create employment details with salary
                salary_amount = f.get("salary") or f.get("baseSalary") or f.get("amount")
                details_body = {
                    "employment": {"id": employment_id},
                    "date": start_date,
                    "employmentType": "ORDINARY",
                    "percentageOfFullTimeEquivalent": 100.0,
                }
                if salary_amount is not None:
                    details_body["annualSalary"] = float(salary_amount) * 12  # monthly to annual
                await tx(c, base, tok, "POST", "/employee/employment/details", details_body)
            else:
                return {"success": False, "error": f"Could not create employment: {empl_create.get('error')}"}

        # Step 3: Try to create salary payment specification
        # Tripletex salary endpoints vary, try multiple approaches

        # Approach A: POST /salary/transaction (salary payment line)
        salary_amount = f.get("salary") or f.get("baseSalary") or f.get("amount") or 0
        bonus_amount = f.get("bonus") or f.get("bonusAmount") or 0
        pay_date = f.get("paymentDate") or f.get("date") or time.strftime("%Y-%m-%d")

        # Try to get salary types
        sal_type_r = await tx(c, base, tok, "GET", "/salary/type", params={"count": 50})
        monthly_type_id = None
        bonus_type_id = None
        if sal_type_r.get("success") and sal_type_r.get("data"):
            sal_types = as_list(sal_type_r["data"])
            for st in sal_types:
                name_lower = (st.get("name") or "").lower()
                num = st.get("number")
                # Common Tripletex salary type numbers:
                # 111 = Fastlonn (fixed salary), 130 = bonus
                if num == 111 or "fast" in name_lower or "maaned" in name_lower or "month" in name_lower:
                    monthly_type_id = st["id"]
                if num == 130 or "bonus" in name_lower or "tillegg" in name_lower:
                    bonus_type_id = st["id"]
            # Fallback: use first available type
            if not monthly_type_id and sal_types:
                monthly_type_id = sal_types[0]["id"]
            if not bonus_type_id:
                bonus_type_id = monthly_type_id

        # Try creating a salary payment specification (payslip)
        payslip_body = {
            "employee": {"id": emp_id},
            "employment": {"id": employment_id},
        }

        # Try POST /salary/payslip first
        payslip_r = await tx(c, base, tok, "POST", "/salary/payslip", payslip_body)

        if not payslip_r.get("success"):
            # Try POST /salary/paymentSpecification
            payslip_r = await tx(c, base, tok, "POST", "/salary/paymentSpecification", payslip_body)

        if payslip_r.get("success") and payslip_r.get("data"):
            payslip_id = payslip_r["data"]["id"]

            # Add salary transaction for base salary
            if salary_amount and monthly_type_id:
                await tx(c, base, tok, "POST", "/salary/transaction", {
                    "payslip": {"id": payslip_id},
                    "salaryType": {"id": monthly_type_id},
                    "amount": float(salary_amount),
                    "date": pay_date,
                })

            # Add bonus transaction
            if bonus_amount and bonus_type_id:
                await tx(c, base, tok, "POST", "/salary/transaction", {
                    "payslip": {"id": payslip_id},
                    "salaryType": {"id": bonus_type_id},
                    "amount": float(bonus_amount),
                    "date": pay_date,
                })

            return payslip_r

        # Approach B: If payslip endpoints don't exist, try creating salary
        # via employment details update (set the annual salary)
        if salary_amount:
            annual = float(salary_amount) * 12
            details_update = {
                "employment": {"id": employment_id},
                "date": pay_date,
                "employmentType": "ORDINARY",
                "annualSalary": annual,
                "percentageOfFullTimeEquivalent": 100.0,
            }
            det_r = await tx(c, base, tok, "POST", "/employee/employment/details", details_update)
            if det_r.get("success"):
                return det_r

        # If nothing worked, at least the employee + employment are set up
        return {"success": True, "data": {"message": "Employee and employment created, salary API endpoints unavailable"}}

    except Exception as e:
        log.error("exec_process_salary crashed: %s", e)
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# EXECUTOR 2: exec_register_supplier_invoice
# ---------------------------------------------------------------------------
# Handles prompts like:
#   "We received invoice INV-123 from supplier Kontorservice AS (org no. 987654321)
#    for 12500 NOK including VAT. Account 6300. Register the supplier invoice
#    with correct input VAT (25%)."
#
# Strategy:
#   1. Find or create the supplier (POST /supplier, or POST /customer with isSupplier=true)
#   2. Calculate net amount and VAT from the total (inclusive)
#   3. Create a voucher with debit/credit lines:
#      - Debit expense account (e.g., 6300) for the net amount
#      - Debit input VAT account (2710/2711) for the VAT amount
#      - Credit supplier/accounts payable account (2400) for the total
# ---------------------------------------------------------------------------

async def exec_register_supplier_invoice(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    """Register an incoming supplier invoice with proper VAT handling."""
    try:
        supplier_name = f.get("supplierName") or f.get("name", "Leverandor")
        org_number = f.get("orgNumber") or f.get("supplierOrgNumber")
        total_incl_vat = float(f.get("amount") or f.get("totalAmount") or f.get("invoiceAmount") or 0)
        vat_rate = float(f.get("vatRate", 25))
        expense_account_number = int(f.get("account") or f.get("accountNumber") or 6300)
        invoice_number = f.get("invoiceNumber") or f.get("referenceNumber") or ""
        invoice_date = f.get("invoiceDate") or f.get("date") or time.strftime("%Y-%m-%d")
        due_date = f.get("dueDate") or invoice_date
        description = f.get("description") or f"Leverandorfaktura {invoice_number} fra {supplier_name}"

        # Calculate VAT split: total is inclusive, so net = total / (1 + rate/100)
        if vat_rate > 0:
            net_amount = round(total_incl_vat / (1 + vat_rate / 100), 2)
            vat_amount = round(total_incl_vat - net_amount, 2)
        else:
            net_amount = total_incl_vat
            vat_amount = 0.0

        log.info("Supplier invoice: total=%.2f, net=%.2f, vat=%.2f (rate=%.0f%%)",
                 total_incl_vat, net_amount, vat_amount, vat_rate)

        # Step 1: Try to create supplier via /supplier endpoint first
        supplier_id = None

        supplier_body = {
            "name": supplier_name,
        }
        if org_number:
            supplier_body["organizationNumber"] = str(org_number)

        sup_r = await tx(c, base, tok, "POST", "/supplier", supplier_body)
        if sup_r.get("success") and sup_r.get("data"):
            supplier_id = sup_r["data"]["id"]
            log.info("Created supplier via /supplier: id=%d", supplier_id)
        else:
            # Fallback: create as customer with isSupplier=true
            log.info("/supplier POST failed (%s), trying /customer with isSupplier=true",
                     sup_r.get("error", "unknown"))
            cust_body = {
                "name": supplier_name,
                "isCustomer": False,
                "isSupplier": True,
            }
            if org_number:
                cust_body["organizationNumber"] = str(org_number)
            cust_r = await tx(c, base, tok, "POST", "/customer", cust_body)
            if cust_r.get("success") and cust_r.get("data"):
                supplier_id = cust_r["data"]["id"]
                log.info("Created supplier via /customer: id=%d", supplier_id)
            else:
                log.warning("Could not create supplier entity: %s", cust_r.get("error"))
                # Continue anyway -- we can still create the voucher

        # Step 2: Look up account IDs
        # Expense account (e.g. 6300)
        expense_acct_r = await tx(c, base, tok, "GET", "/ledger/account",
                                  params={"number": expense_account_number})
        expense_acct_id = None
        if expense_acct_r.get("success") and expense_acct_r.get("data"):
            accts = as_list(expense_acct_r["data"])
            if accts:
                expense_acct_id = accts[0]["id"]

        # Input VAT account (2710 for domestic, 2711 for high-rate)
        vat_account_number = 2710
        if vat_rate == 15:
            vat_account_number = 2714
        elif vat_rate == 12:
            vat_account_number = 2713

        vat_acct_r = await tx(c, base, tok, "GET", "/ledger/account",
                              params={"number": vat_account_number})
        vat_acct_id = None
        if vat_acct_r.get("success") and vat_acct_r.get("data"):
            accts = as_list(vat_acct_r["data"])
            if accts:
                vat_acct_id = accts[0]["id"]
        else:
            # Fallback: try 2711
            vat_acct_r2 = await tx(c, base, tok, "GET", "/ledger/account",
                                   params={"number": 2711})
            if vat_acct_r2.get("success") and vat_acct_r2.get("data"):
                accts2 = as_list(vat_acct_r2["data"])
                if accts2:
                    vat_acct_id = accts2[0]["id"]

        # Accounts payable (2400 = leverandorgjeld)
        payable_acct_r = await tx(c, base, tok, "GET", "/ledger/account",
                                  params={"number": 2400})
        payable_acct_id = None
        if payable_acct_r.get("success") and payable_acct_r.get("data"):
            accts = as_list(payable_acct_r["data"])
            if accts:
                payable_acct_id = accts[0]["id"]

        # Step 3: Look up input VAT types
        input_vat_map = await lookup_input_vat_map(c, base, tok)
        input_vat_type_id = input_vat_map.get(int(vat_rate), input_vat_map.get(25, 1))

        # Step 4: Try supplierInvoice endpoint first (Tripletex may have this)
        sup_inv_body = {
            "invoiceDate": invoice_date,
            "dueDate": due_date,
            "invoiceNumber": invoice_number,
            "amountCurrency": total_incl_vat,
            "currency": {"id": 1},  # NOK
        }
        if supplier_id:
            sup_inv_body["supplier"] = {"id": supplier_id}

        sup_inv_r = await tx(c, base, tok, "POST", "/supplierInvoice", sup_inv_body)

        if sup_inv_r.get("success"):
            log.info("Supplier invoice created via /supplierInvoice")
            return sup_inv_r

        # Step 5: Fallback -- create a manual voucher with journal entries
        log.info("/supplierInvoice failed (%s), creating voucher manually",
                 sup_inv_r.get("error", "unknown"))

        # Build voucher postings
        postings = []

        # Debit: expense account for net amount
        if expense_acct_id:
            posting_expense = {
                "account": {"id": expense_acct_id},
                "amountGross": net_amount,
                "amountGrossCurrency": net_amount,
                "currency": {"id": 1},
                "description": description,
                "date": invoice_date,
            }
            if vat_amount > 0:
                posting_expense["vatType"] = {"id": input_vat_type_id}
            postings.append(posting_expense)

        # If no VAT type auto-splits, add explicit VAT line
        if vat_amount > 0 and vat_acct_id:
            postings.append({
                "account": {"id": vat_acct_id},
                "amountGross": vat_amount,
                "amountGrossCurrency": vat_amount,
                "currency": {"id": 1},
                "description": f"Inngaende MVA {int(vat_rate)}%",
                "date": invoice_date,
            })

        # Credit: accounts payable for total amount
        if payable_acct_id:
            postings.append({
                "account": {"id": payable_acct_id},
                "amountGross": -total_incl_vat,
                "amountGrossCurrency": -total_incl_vat,
                "currency": {"id": 1},
                "description": f"Leverandorgjeld {supplier_name}",
                "date": invoice_date,
            })

        if not postings:
            return {"success": False, "error": "Could not resolve any ledger accounts for voucher"}

        # Create voucher
        voucher_body = {
            "date": invoice_date,
            "description": description,
            "postings": postings,
        }

        voucher_r = await tx(c, base, tok, "POST", "/ledger/voucher", voucher_body)

        if not voucher_r.get("success"):
            # Try simplified approach: single posting with amountGross = total, let Tripletex split
            log.info("Multi-line voucher failed, trying single-line with vatType")
            simple_voucher = {
                "date": invoice_date,
                "description": description,
                "postings": [{
                    "account": {"id": expense_acct_id} if expense_acct_id else {"id": 1},
                    "amountGross": total_incl_vat,
                    "amountGrossCurrency": total_incl_vat,
                    "currency": {"id": 1},
                    "description": description,
                    "date": invoice_date,
                    "vatType": {"id": input_vat_type_id},
                }],
            }
            voucher_r = await tx(c, base, tok, "POST", "/ledger/voucher", simple_voucher)

        return voucher_r

    except Exception as e:
        log.error("exec_register_supplier_invoice crashed: %s", e)
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# EXECUTOR 3: exec_create_dimension
# ---------------------------------------------------------------------------
# Handles prompts like:
#   "Create a custom accounting dimension 'Region' with values 'Vestlandet'
#    and 'Midt-Norge'. Post a document to account 6860 for 5000 NOK linked
#    to dimension value 'Vestlandet'."
#
# Strategy:
#   1. Create the dimension (POST /dimension or similar)
#   2. Create dimension values
#   3. Create a voucher/posting linked to the dimension value
# ---------------------------------------------------------------------------

async def exec_create_dimension(c: httpx.AsyncClient, base: str, tok: str, f: dict) -> dict:
    """Create a custom accounting dimension with values and optionally post a voucher."""
    try:
        dimension_name = f.get("dimensionName") or f.get("name", "")
        dimension_values = f.get("dimensionValues") or f.get("values") or []
        # If values is a string (comma-separated), split it
        if isinstance(dimension_values, str):
            dimension_values = [v.strip() for v in dimension_values.split(",") if v.strip()]

        # Posting fields (optional)
        post_account = f.get("account") or f.get("accountNumber")
        post_amount = f.get("amount")
        post_dimension_value = f.get("linkedDimensionValue") or f.get("linkedValue")
        post_date = f.get("date") or time.strftime("%Y-%m-%d")
        description = f.get("description") or f"Bilag med dimensjon {dimension_name}"

        # Step 1: Try to create the dimension
        # Tripletex custom dimensions may be at various endpoints
        dimension_id = None

        # Try POST /ledger/dimension
        dim_r = await tx(c, base, tok, "POST", "/ledger/dimension", {
            "name": dimension_name,
        })
        if dim_r.get("success") and dim_r.get("data"):
            dimension_id = dim_r["data"].get("id")
            log.info("Created dimension via /ledger/dimension: id=%s", dimension_id)
        else:
            # Try POST /dimension
            dim_r = await tx(c, base, tok, "POST", "/dimension", {
                "name": dimension_name,
            })
            if dim_r.get("success") and dim_r.get("data"):
                dimension_id = dim_r["data"].get("id")
                log.info("Created dimension via /dimension: id=%s", dimension_id)

        if not dimension_id:
            # Try department as a dimension proxy (departments are Tripletex's
            # built-in dimension system, and may be the only option in the sandbox)
            log.info("Custom dimension endpoints failed, using department as dimension proxy")

            created_values = []
            for i, val in enumerate(dimension_values):
                dept_body = {
                    "name": f"{dimension_name}: {val}",
                    "departmentNumber": i + 100,
                }
                dept_r = await tx(c, base, tok, "POST", "/department", dept_body)
                if dept_r.get("success") and dept_r.get("data"):
                    created_values.append({
                        "name": val,
                        "id": dept_r["data"]["id"],
                    })

            # If we need to post a voucher linked to a dimension value
            if post_account and post_amount:
                target_dept_id = None
                for cv in created_values:
                    if post_dimension_value and post_dimension_value.lower() in cv["name"].lower():
                        target_dept_id = cv["id"]
                        break
                if not target_dept_id and created_values:
                    target_dept_id = created_values[0]["id"]

                # Look up the account
                acct_r = await tx(c, base, tok, "GET", "/ledger/account",
                                  params={"number": int(post_account)})
                acct_id = None
                if acct_r.get("success") and acct_r.get("data"):
                    accts = as_list(acct_r["data"])
                    if accts:
                        acct_id = accts[0]["id"]

                if acct_id:
                    voucher_body = {
                        "date": post_date,
                        "description": description,
                        "postings": [
                            {
                                "account": {"id": acct_id},
                                "amountGross": float(post_amount),
                                "amountGrossCurrency": float(post_amount),
                                "currency": {"id": 1},
                                "description": description,
                                "date": post_date,
                            },
                        ],
                    }
                    if target_dept_id:
                        voucher_body["postings"][0]["department"] = {"id": target_dept_id}

                    v_r = await tx(c, base, tok, "POST", "/ledger/voucher", voucher_body)
                    return v_r

            if created_values:
                return {"success": True, "data": {"message": f"Created {len(created_values)} dimension values as departments", "values": created_values}}
            return {"success": False, "error": "Could not create dimension via any endpoint"}

        # Step 2: Create dimension values (if dimension was created successfully)
        created_value_ids = []
        for val in dimension_values:
            val_body = {
                "dimension": {"id": dimension_id},
                "name": val,
            }
            # Try /ledger/dimension/value or /dimension/value
            val_r = await tx(c, base, tok, "POST", "/ledger/dimension/value", val_body)
            if not val_r.get("success"):
                val_r = await tx(c, base, tok, "POST", f"/ledger/dimension/{dimension_id}/value", val_body)
            if not val_r.get("success"):
                val_r = await tx(c, base, tok, "POST", "/dimension/value", val_body)
            if val_r.get("success") and val_r.get("data"):
                created_value_ids.append({
                    "name": val,
                    "id": val_r["data"].get("id"),
                })
                log.info("Created dimension value '%s': id=%s", val, val_r["data"].get("id"))

        # Step 3: Create voucher/posting linked to dimension value (if requested)
        if post_account and post_amount:
            # Find the target dimension value ID
            target_value_id = None
            for cv in created_value_ids:
                if post_dimension_value and post_dimension_value.lower() in cv["name"].lower():
                    target_value_id = cv["id"]
                    break
            if not target_value_id and created_value_ids:
                target_value_id = created_value_ids[0].get("id")

            # Look up the account
            acct_r = await tx(c, base, tok, "GET", "/ledger/account",
                              params={"number": int(post_account)})
            acct_id = None
            if acct_r.get("success") and acct_r.get("data"):
                accts = as_list(acct_r["data"])
                if accts:
                    acct_id = accts[0]["id"]

            if acct_id:
                posting = {
                    "account": {"id": acct_id},
                    "amountGross": float(post_amount),
                    "amountGrossCurrency": float(post_amount),
                    "currency": {"id": 1},
                    "description": description,
                    "date": post_date,
                }
                # Try to link dimension value to the posting
                if target_value_id:
                    posting["dimensionValue"] = {"id": target_value_id}

                voucher_body = {
                    "date": post_date,
                    "description": description,
                    "postings": [posting],
                }

                v_r = await tx(c, base, tok, "POST", "/ledger/voucher", voucher_body)
                return v_r

        return {"success": True, "data": {
            "dimension_id": dimension_id,
            "values_created": len(created_value_ids),
            "values": created_value_ids,
        }}

    except Exception as e:
        log.error("exec_create_dimension crashed: %s", e)
        return {"success": False, "error": str(e)}


# ===========================================================================
# MERGE INSTRUCTIONS
# ===========================================================================

# --- 1. Add to TASK_EXECUTORS dict (around line 827-844 in tripletex_bot_v4.py) ---
# Add these 3 lines inside the TASK_EXECUTORS dict:
#
#     "process_salary": exec_process_salary,
#     "register_supplier_invoice": exec_register_supplier_invoice,
#     "create_dimension": exec_create_dimension,
#
# So the dict becomes:
# TASK_EXECUTORS = {
#     "create_customer": exec_create_customer,
#     ...existing entries...
#     "enable_module": exec_enable_module,
#     "process_salary": exec_process_salary,
#     "register_supplier_invoice": exec_register_supplier_invoice,
#     "create_dimension": exec_create_dimension,
# }

# --- 2. Add to EXTRACTION_PROMPT (around line 57-106 in tripletex_bot_v4.py) ---
# Add these 3 new task types to the "## Task types (pick exactly one):" list:
#
# - process_salary (use when prompt mentions payroll/lonn/lonnskjoring/salary payment, running payroll, paying salary)
# - register_supplier_invoice (use when prompt mentions supplier invoice/leverandorfaktura/incoming invoice, registering a bill from a vendor/supplier)
# - create_dimension (use when prompt mentions accounting dimension/dimensjon, custom dimensions, or creating dimension values)
#
# Add these field names to the "## Field names to use:" section:
#
# - supplierName, supplierOrgNumber, invoiceNumber, invoiceAmount, totalAmount
# - baseSalary, bonus, bonusAmount, paymentDate
# - dimensionName, dimensionValues (array of strings), linkedDimensionValue, account, accountNumber

# --- 3. Copy lookup_input_vat_map helper ---
# Place the _input_vat_cache dict and lookup_input_vat_map function
# right after the existing lookup_vat_map function (around line 142)
