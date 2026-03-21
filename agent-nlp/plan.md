# Tripletex AI Accounting Agent -- Final Session Plan

**Track:** NLP | **Weight:** 33.33%
**Last updated:** 2026-03-21 21:00 CET
**Bot:** tripletex_bot_v4.py (2515 lines, 27 executors, rev 83 deployed)
**Time remaining:** ~18 hours (deadline Sunday 15:00 CET)
**Submissions:** 51 remaining today + 300 fresh at 01:00 CET = 351 total

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

## Phase 1: Analyze (01:00 - 02:00 CET)
After rate limit reset, submit 10-15 to get fresh data with rev 83.
Run efficiency_analyzer.py on the results to see total_calls per task type.
Identify which specific fields are wrong on the 4 Tier 3 groups.

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
