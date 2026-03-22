# Tripletex AI Accounting Agent -- Plan

**Track:** NLP | **Weight:** 33.33%
**Last updated:** 2026-03-22 12:30 CET
**Bot:** tripletex_bot_v4.py (27 executors, rev 98 deployed)
**Deadline:** Sunday 15:00 CET (~2.5 hours)
**Submissions:** 279/300 remaining today

---

## Current Score & Gaps

Score: 29.08 (rank #107). Rev 98 fixed year_end_closing (now 100%), activity 422, payment cascades.

| Check count | Best score | Status |
|-------------|-----------|--------|
| 6 checks | 100% | LOCKED |
| 7 checks | 100% | LOCKED |
| 8 checks | 100% | LOCKED |
| 10 checks | 75% | GAP: userType + missing fields |
| 11 checks | 36% | GAP: missing fields |
| 13 checks | 100% | LOCKED |
| 14 checks | 79% | GAP: invoice fields |
| 22 checks | 68% | GAP: Tier 3 complex |

---

## Session 3 continued: PMM Audit Fixes

### Already done (rev 95-98):
- [x] ledger_error_correction: credit account 2400 -> 1920
- [x] register_payment: skip 404 cascade
- [x] year_end_closing: fallback account search (NOW WORKING)
- [x] create_contact: search-before-create
- [x] create_employee: +nationalIdentityNumber, +address, +employeeNumber
- [x] Extraction prompt: +8 fields, multilingual parsing
- [x] create_customer: +physicalAddress, +invoicesDueIn, +invoiceSendMethod
- [x] lookup_account: per-request cache
- [x] Travel expense: +costCategory
- [x] create_project_invoice: search-before-create
- [x] update_customer: +postalCode, +city, +physicalAddress
- [x] update_employee: +dateOfBirth, +bankAccountNumber, +nationalIdentityNumber
- [x] occupationCode: uncommented
- [x] Zone detection: substring match fix
- [x] create_invoice_with_payment: skip /:payment cascade
- [x] Activity creation: remove invalid "project" field

### PMM audit fix queue (Boris workflow each):

1. **userType "STANDARD" -> "ADMINISTRATOR"** (Morten)
   - Extraction prompt tells LLM to use "STANDARD" for admin. Should be "ADMINISTRATOR".
   - Likely root cause of 10-check tasks at 30%. Could be worth 5/10 points per employee task.

2. **Add `language`, `deliveryDate` to extraction prompt** (Bo)
   - Customer language (NO/EN/DE/FR/ES/PT) never extracted
   - Invoice deliveryDate never extracted, always uses today

3. **Country as {"id": N} instead of string** (Morten)
   - Current code sends "Norge" as string, Tripletex expects {"id": 161}
   - Build country name-to-ID mapping

4. **Zone detection: add Noruega/Norvege/Norwegen/Noreg** (Arturo)
   - Portuguese/Spanish/French/German/Nynorsk variants of "Norway" missing

5. **Invoice payment amount: use inc-VAT total** (Morten)
   - create_invoice_with_payment may pay ex-VAT amount instead of inc-VAT

### After fixes:
- Deploy final rev
- Submit batch for coverage
- 14:45: repo public

---

## Rules
- Boris SEQUENTIAL for every change: review -> simplify -> validate (separate agents)
- No submissions until JC approves
- Every 4xx error costs efficiency points
