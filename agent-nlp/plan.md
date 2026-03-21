# Tripletex AI Accounting Agent -- Execution Plan

**Track:** NLP | **Weight:** 33.33%
**Last updated:** 2026-03-21 20:00 CET
**Bot:** tripletex_bot_v4.py (~2515 lines, 27 executors, rev 83 deployed)
**Time remaining:** ~19 hours (deadline Sunday 15:00 CET)
**Submissions:** 61 remaining today, 300 fresh at 01:00 CET

---

## Strategy: Correctness First, Efficiency Second

1. **Fix tasks scoring 0% to score something** -- DONE (all 8 check-count groups have >0 scores)
2. **Fix tasks scoring 20-70% to 100%** -- IN PROGRESS (4 Tier 3 groups remain)
3. **Optimize API calls for efficiency bonus** -- DONE (audit rounds 1+2 applied)

---

## Current Scores by Task Type

| Checks | Tier | Subs | Best | Status | What's needed |
|--------|------|------|------|--------|---------------|
| 6 | 1 | 9 | 100% | LOCKED | -- |
| 7 | 1/2 | 95 | 100% | LOCKED | -- |
| 8 | 1/2 | 201 | 100% | LOCKED | -- |
| 13 | 2/3 | 17 | 100% | LOCKED | -- |
| **10** | **3** | 49 | **75%** | WORK | year_end monthly variant, overdue_invoice, analyze_ledger activity |
| **11** | **3** | 5 | **36%** | WORK | currency payment paidAmountCurrency, agio sign (fixed rev 82) |
| **14** | **3** | 4 | **71%** | WORK | bank_recon crash fix (rev 83), outgoing payment supplier |
| **22** | **3** | 3 | **59%** | WORK | employee working hours (fixed rev 83), PDF field extraction |

**Potential gain if all Tier 3 hit 100%: +16.8 points (29 -> ~46)**

---

## What Was Done Today (revs 65 -> 83, 18 deployments)

### Efficiency (audit-driven)
- Hardcoded: VAT IDs, payment type IDs, input VAT IDs (saves 6+ GETs per request)
- POST-first: customer, department (skip unnecessary GETs on fresh sandbox)
- 403 abort: prevents cascading errors
- Account caching: year_end, ledger_error
- Total call tracking: ALL API calls counted, not just writes

### Correctness
- 5 Tier 3 executors built: analyze_ledger, year_end_closing, bank_reconciliation, overdue_invoice_reminder, ledger_error_correction
- Employee: personnummer, dept by name, occupationCode disabled (422), salary annual/monthly detection, working hours config
- Currency payment: two exchange rates, paidAmountCurrency fix, agio sign fix
- Supplier invoice: account validation (reject org numbers)
- Invoice: dueDate default today+30
- Overdue reminder: removed voucher double-booking

### Boris Workflow
- 3 separate review agents per round (feature-dev:code-reviewer, code-simplifier:code-simplifier, build-validator)
- Each agent gets fresh context

---

## QC Status (dev sandbox, rev 83)

| Test | Result | Notes |
|------|--------|-------|
| Create Customer | PASS | |
| Create Employee | PASS | |
| Create Product | PASS | |
| Create Department | PASS | |
| Create Project | PASS | |
| Create Invoice | FAIL | Dev sandbox state issue (competition sandboxes are fresh) |
| Create Travel Expense | FAIL | "no costs attached" -- needs investigation |
| Register Payment | FAIL | Depends on invoice test |

**Note:** Dev sandbox accumulates state. Competition sandboxes are fresh per submission. Invoice/Payment failures may be sandbox-specific. Travel expense costs issue is real.

---

## Next Actions

### Before next submission batch
A. Investigate travel expense "no costs attached" from QC
B. Run QC with --tier2 for extended tests
C. Check if travel expense costs are being POSTed correctly

### Tomorrow (01:00 CET reset, 300 fresh submissions)
D. Submit 30-50 to cover all task types with rev 83 fixes
E. Analyze results, fix remaining Tier 3 gaps
F. Feature freeze at 09:00 CET

### Key Dates
| Time | What |
|------|------|
| 01:00 CET Sun | Rate limits reset, 300 fresh submissions |
| 09:00 CET Sun | FEATURE FREEZE |
| 14:45 CET Sun | Repo goes public |
| 15:00 CET Sun | COMPETITION ENDS |

---

## 27 Executors (rev 83)

**Tier 1/2 (22):** create_customer, create_employee, create_employee_with_employment, create_product, create_department, create_project, create_invoice, create_invoice_with_payment, create_project_invoice, register_payment, create_credit_note, create_travel_expense, delete_employee, delete_travel_expense, update_customer, update_employee, create_contact, enable_module, process_salary, register_supplier_invoice, create_dimension, create_supplier

**Tier 3 (5):** analyze_ledger_create_projects, year_end_closing, bank_reconciliation, overdue_invoice_reminder, ledger_error_correction

**Fallback:** Gemini agent loop for unknown task types
