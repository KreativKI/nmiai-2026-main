# Tripletex AI Accounting Agent -- Execution Plan

**Track:** NLP | **Weight:** 33.33%
**Last updated:** 2026-03-21 18:30 CET
**Approach:** Structured workflows (LLM extracts fields, Python executes API calls)
**Bot version:** tripletex_bot_v4.py (~2500 lines, 27 executors, rev 79 deployed)
**Time remaining:** ~20.5 hours (deadline Sunday 15:00 CET)

## Leaderboard State (2026-03-21 00:50 CET, needs refresh)

| Team | Score | Tasks | Correctness | Efficiency |
|------|-------|-------|-------------|------------|
| #1 Propulsion Optimizers | 46.70 | 18/30 | 14.8 | 31.9 |
| #107 Kreativ KI (us) | 29.08 | 18/30 | 14.7 | 14.4 |

**Gap: +18 points needed.** Audit insight: correctness gains are faster than efficiency gains.

---

## Strategy (NEW -- from audit round 2)

**Priority 1: Fix tasks scoring 0% to score something**
Any score > 0 is free points. Tasks currently at 0:
- Bank reconciliation (0/10): matching bug fixed in rev 72, supplier creation added
- Year-end closing variants (0/10): some variants fail (monthly closing, missing fields)
- Ledger error correction (0/10 on some): classified as unknown on some prompts
- Overdue invoice reminder (0/10): was double-booking, fixed in rev 79
- Analyze ledger (0/10 on some): activity endpoint 422, fixed in rev 76

**Priority 2: Fix tasks scoring 20-70% to 100% (unlocks efficiency bonus)**
These are worth the MOST because going from partial to perfect unlocks 2x multiplier:
- create_employee_with_employment: 41-59% (missing personnummer, stillingskode, dept name)
  - Fixed in rev 73: added nationalIdentityNumber, occupationCode, dept by name
- register_payment with currency: 20% (agio/disagio voucher failing)
  - Fixed in rev 72: added customer ID to account 1500 postings
- Supplier invoice: 0-75% (account number validation, VAT handling)
  - Fixed in rev 74: reject org numbers as account numbers
- process_salary: was multiplying annual salary x12 unconditionally
  - Fixed in rev 79: salary >= 100K treated as annual
- Travel expense: 56% (5/8), missing some fields
- Year-end closing: 20% (2/10), accumulated depreciation account fixed in rev 72

**Priority 3: Optimize API calls for efficiency bonus**
Only matters on tasks with 100% correctness. Done via two audit rounds:
- Hardcoded: VAT IDs, payment type IDs, input VAT IDs (saves 6+ GETs per request)
- POST-first: customer creation, department creation (skip unnecessary GETs on fresh sandbox)
- 403 abort: prevents cascading errors from expired tokens
- Account caching: year_end_closing and ledger_error_correction
- Total call tracking: logs ALL API calls, not just writes

---

## Revisions Today (rev 65 -> 79, 14 deployments)

| Rev | Changes | Impact |
|-----|---------|--------|
| 66 | Look-before-leap employee creation | -36 email conflict errors |
| 67 | Boris review: contextvars fix, VAT cache, email detection | Correctness |
| 68 | 403 abort, dept cache | Prevent cascading errors |
| 69 | Tier 3: analyze_ledger_create_projects | New task type |
| 70 | Tier 3: year_end_closing, bank_reconciliation, overdue_invoice_reminder | 3 new task types |
| 71 | Fix bank_reconciliation 400, year_end accumulated depreciation, ledger_error_correction | 4th Tier 3 type |
| 72 | Fix analyze_ledger 400, bank_recon matching, currency voucher customer ref | Tier 3 bugs |
| 73 | find_customer 1 GET, personnummer, stillingskode, dept by name, userType | Efficiency + correctness |
| 74 | Supplier invoice account validation | Silent failure fix |
| 75 | Account lookup caching | -50% GETs in year_end/ledger_error |
| 76 | Fix overdue_invoice 400, analyze_ledger activity endpoint | Tier 3 bugs |
| 77 | **AUDIT 1**: Hardcode VAT/payment/dept, POST-first patterns, total call tracker | -30-50% API calls |
| 78 | Review fixes: dept number 9999, missed payment type hardcodes | Cleanup |
| 79 | **AUDIT 2**: Salary x12 fix, double-booking fix, dueDate+30, more POST-first | Correctness |

---

## Submission Budget

| Window | Budget | Used | Remaining |
|--------|--------|------|-----------|
| Today (resets 01:00 CET) | 300 | 229 | 71 |
| Tomorrow (01:00-15:00 CET) | 300 | 0 | 300 |
| **Total remaining** | | | **371** |

Rate limit: 5 per task per day per tier.

---

## What to Fix Next (ranked by point impact)

### Immediate (before next submission batch)

A. **Identify which task types we have ZERO score on** -- need Cloud Run logs showing task_type for each 0/10 result. Each new non-zero task type is free points.

B. **Travel expense still at 5/8** -- need to check what 3 fields are wrong. Likely: costs not being posted correctly, or missing per diem details.

C. **Test the salary x12 fix (rev 79)** -- was a confirmed bug, should improve process_salary scores immediately.

### Tomorrow morning (with fresh 300 submissions)

D. **Bulk submit 30-50 to cover all task types** -- platform weights toward less-attempted types, so this naturally covers gaps.

E. **Analyze results, fix the biggest 0-score types** -- iterate: submit -> analyze -> fix -> deploy -> submit.

F. **Feature freeze Sunday 09:00** -- last 6 hours for bug fixes only.

---

## Key Dates

| Time | What |
|------|------|
| Now (18:30 CET Sat) | Fix correctness gaps, submit strategically |
| 01:00 CET Sun | Rate limits reset, 300 fresh submissions |
| 09:00 CET Sun | FEATURE FREEZE |
| 14:45 CET Sun | Repo goes public |
| 15:00 CET Sun | COMPETITION ENDS |

---

## Efficiency Rules (confirmed by audit)

- **ALL API calls count** (GETs + writes). Competition docs: "How many API calls."
- Each 4xx error reduces efficiency bonus.
- Efficiency bonus ONLY applies at 100% correctness.
- Benchmarks recalculated every 12 hours.
- Rate limit: 5 per task per day PER TIER, 300 total/day.

## 27 Executors (rev 79)

**Tier 1/2 (22):** create_customer, create_employee, create_employee_with_employment, create_product, create_department, create_project, create_invoice, create_invoice_with_payment, create_project_invoice, register_payment, create_credit_note, create_travel_expense, delete_employee, delete_travel_expense, update_customer, update_employee, create_contact, enable_module, process_salary, register_supplier_invoice, create_dimension, create_supplier

**Tier 3 (5):** analyze_ledger_create_projects, year_end_closing, bank_reconciliation, overdue_invoice_reminder, ledger_error_correction

**Fallback:** Gemini agent loop for unknown task types
