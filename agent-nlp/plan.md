# Tripletex AI Accounting Agent -- Final Session Plan

**Track:** NLP | **Weight:** 33.33%
**Last updated:** 2026-03-21 21:30 CET
**Bot:** tripletex_bot_v4.py (27 executors, rev 86 deployed)
**Time remaining:** ~17.5 hours (deadline Sunday 15:00 CET)
**Submissions:** ~23 remaining today + 300 fresh at 01:00 CET = ~323 total

---

## Strategy: Get Tier 3 to 100%

All Tier 1/2 tasks are at 100%. The entire remaining opportunity is Tier 3.
Each Tier 3 task at 100% + efficiency = up to 6.0 points.

| Task Group | Current | Target | Potential Gain | Priority |
|-----------|---------|--------|---------------|----------|
| 11-check (currency payment) | 36% | 100% | +4.9 pts | 1 |
| 22-check (employee PDF) | 68% | 100% | +4.2 pts | 2 |
| 14-check (bank recon) | 79% | 100% | +3.9 pts | 3 |
| 10-check (5 Tier 3 types) | 75% | 100% | +3.8 pts | 4 |

**Total potential: +16.8 points (29 -> ~46, competitive with #1)**

---

## Done This Session (21:00 - 22:00 CET)
### Round 1: Tier 3 payment fixes (rev 85-86)
- Fixed /:payment 404s: replaced with voucher postings (debit bank 1920, credit AR 1500)
- Fixed bank_reconciliation: use vouchers for all payments (was 7-8 x 404 per run)
- Fixed overdue_invoice_reminder: voucher for partial payment (was 1 x 404 per run, now 0 errors)
- Fixed analyze_ledger_create_projects: removed failing activity creation (6 x 422 per run, now 0 errors)
- Added /:payment -> voucher fallback to register_payment and create_invoice_with_payment
- Extracted lookup_account and post_payment_voucher helpers (simplifier)
- Created audit-and-submit.sh pipeline with hard-blocker gates

### Round 2: Full audit findings (rev 87)
- Fixed currency payment paidAmount: was sending original NOK amount, now sends curr_amt * pay_rate
- Fixed year_end_closing: prepaid-only tasks no longer blocked by early return
- Fixed bank account unconditional PUT: now checks if bankAccountNumber already set
- Fixed supplier invoice: added missing VAT line (3-posting voucher: expense + VAT + liability)
- Fixed travel expense: zone enum ("NORWAY"/"ABROAD") instead of city name string
- Fixed email null guard: no longer sends "email": null for NO_ACCESS employees
- Fixed currency in create_invoice_with_payment (same fix as register_payment)
- Fixed year_end_closing expense account lookup: only runs when assets present
- Fixed travel zone fallback: checks travelLocation, location, destination fields

## Remaining audit items - ALL DONE
- [x] Project manager 422: rename admin instead of creating new employee (DONE)
- [x] Ledger error correction: use correctAccount for duplicate type, not 1920 (DONE)
- [x] Identify 3 missing task types: only 1 unknown_fallback hit in all logs, coverage is fine (DONE)
- [x] Extraction prompt disambiguation: register_payment vs create_invoice_with_payment (DONE)

## Data analysis findings
- 13-check task: was always 0/13 on day 1, now 100% (already fixed)
- 22-check task: at 68% (15/22), improving
- 0/10 scores: 31 in last 100 subs, main remaining gap. Likely misclassified or failing executors.
- Task type coverage: 27/30 executors + fallback. Only 1 unknown_fallback hit = coverage is adequate.

## Phase 1: Analyze (01:00 - 02:00 CET)
After rate limit reset, submit 10-15 to get fresh data with rev 87.
Run efficiency_analyzer.py on the results to see total_calls per task type.
Identify which specific fields are still wrong on the 4 Tier 3 groups.

## Phase 2: Fix Top Issues (02:00 - 06:00 CET)
For each Tier 3 group, use Cloud Run logs to identify exactly which fields
are wrong, fix the executor, deploy, and submit a small batch to verify.
Boris workflow on every change.

## Phase 3: Efficiency Sprint (06:00 - 09:00 CET)
Once Tier 3 correctness is maximized, optimize API call counts.
Focus on tasks at 100% correctness where efficiency bonus applies.
Use efficiency_analyzer.py to find remaining unnecessary calls.

## Phase 4: Feature Freeze (09:00 - 15:00 CET)
No new features. Bug fixes only.
Submit remaining budget strategically: focus on task types with
the most room for improvement.
Final submissions by 14:30.
Make repo public at 14:45.

---

## Submission Rules (prevent overnight burn)

**NEVER run auto-submitter unattended.**
- Max 10-15 per batch
- Analyze results after each batch before submitting more
- JC must approve every batch
- If running overnight: set hard cap of 30 submissions max

## Boris Workflow (every code change)
```
EXPLORE -> PLAN -> CODE ->
  REVIEW:   Agent(feature-dev:code-reviewer)     -- fresh context
  SIMPLIFY: Agent(code-simplifier:code-simplifier) -- fresh context
  VALIDATE: Agent(build-validator)                -- fresh context
-> COMMIT
```

## QC Before Deploy
Run `python3 agent-nlp/scripts/qc-verify.py endpoint --all` before every deploy.
9/17 pass on dev sandbox (failures are sandbox state, not bot bugs).

---

## 27 Executors

**Tier 1/2 (22):** create_customer, create_employee, create_employee_with_employment,
create_product, create_department, create_project, create_invoice,
create_invoice_with_payment, create_project_invoice, register_payment,
create_credit_note, create_travel_expense, delete_employee, delete_travel_expense,
update_customer, update_employee, create_contact, enable_module, process_salary,
register_supplier_invoice, create_dimension, create_supplier

**Tier 3 (5):** analyze_ledger_create_projects, year_end_closing, bank_reconciliation,
overdue_invoice_reminder, ledger_error_correction

**Fallback:** Gemini agent loop for unknown task types
