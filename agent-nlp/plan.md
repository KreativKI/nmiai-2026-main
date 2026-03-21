# Tripletex AI Accounting Agent -- Plan

**Track:** NLP | **Weight:** 33.33%
**Last updated:** 2026-03-21 23:00 CET
**Bot:** tripletex_bot_v4.py (27 executors, rev 91 deployed)
**Time remaining:** ~16 hours (deadline Sunday 15:00 CET)
**Submissions:** 300 fresh at 01:00 CET

---

## Current Score & Gaps

Score: 29.08 (rank #107). Rev 91 has 15+ fixes not yet reflected in score.

| Check count | Best score | Status | Likely task types |
|-------------|-----------|--------|-------------------|
| 7 checks | 100% | Done | create_customer, create_employee, create_project |
| 8 checks | 100% | Done | create_invoice, create_travel_expense |
| 10 checks | varies | **Gap: 0/10 still common** | Multiple task types share this |
| 11 checks | varies | Partial | create_employee_with_employment |
| 13 checks | 100% | Done | Was 0/13, now fixed |
| 14 checks | 79% | Partial | Tier 3 tasks |
| 22 checks | 68% | **Gap: 15/22 best** | Complex multi-step task |

**Biggest remaining gap:** 0/10 scores (31 in last 100 subs). Need to identify which executors produce these after rev 91 deploys.

---

## Session Done (21:00 - 23:00 CET, rev 83 -> 91)

### Round 1: Tier 3 payment fixes (rev 85-86)
- bank_reconciliation: voucher postings (was 7-8 x 404)
- overdue_invoice_reminder: voucher for partial payment (was 1 x 404)
- analyze_ledger_create_projects: removed failing activity creation (was 6 x 422)
- register_payment/create_invoice_with_payment: voucher fallback

### Round 2: Full audit findings (rev 87-88)
- Currency paidAmount: now sends curr_amt * pay_rate
- year_end_closing: prepaid-only path unblocked
- Supplier invoice: 3-line VAT voucher (was missing VAT line)
- Bank account: conditional PUT, travel expense: zone enum, email null guard

### Round 3: Final fixes (rev 89-91)
- PM 422 elimination: rename admin instead of employee creation
- Ledger error correction: correct account for duplicates
- Extraction prompt: register_payment disambiguation
- register_payment: skip /:payment entirely (always 404, save the error)

---

## Phase 1: Diagnose 0/10 gap (01:00 - 02:00 CET)
Submit 15 runs with rev 91. Immediately check Cloud Run logs.
For every 0/10: which executor ran? What went wrong?
The 0/10 is the single biggest remaining scoring gap.

## Phase 2: Fix top 0/10 causes (02:00 - 06:00 CET)
Based on Phase 1 data, fix the executors that produce 0/10.
Boris workflow on every change. Deploy and verify with 5-run batches.

## Phase 3: Efficiency sprint (06:00 - 09:00 CET)
Optimize API call counts on tasks already at 100% correctness.
Run efficiency_analyzer.py to identify wasteful calls.

## Phase 4: Feature freeze (09:00 - 15:00 CET)
Bug fixes only. Strategic submissions on weakest task types.
Final submissions by 14:30. Make repo public at 14:45.

---

## Rules
- Audit-and-submit pipeline (`bash agent-nlp/scripts/audit-and-submit.sh`) for every batch
- Max 15 per batch, analyze logs before next batch
- Boris workflow on every code change (3 separate fresh-context agents)
- Every 4xx error from Tripletex API calls costs efficiency points
