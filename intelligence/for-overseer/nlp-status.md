---
from: nlp-agent
timestamp: 2026-03-21 03:15 CET
---

## NLP Status Update (batch 15 complete)

**Rev:** 58 deployed
**Submissions today:** 62/180 used, 118 remaining
**Estimated score:** ~33-35 (up from 29.08 at session start)

### Key Wins This Session (cumulative)
- Dimension: 0/13 -> 13/13 (correct API: accountingDimensionName/Value)
- Supplier: 0/8 -> 8/8 (POST /supplier is NOT BETA, confirmed in Swagger)
- Invoice efficiency: removed bank account retry, product retry
- Project PM: admin=PM pattern (competition creates admin with PM email)
- Salary: removed non-existent payslip endpoints, fixed duplicate details
- Supplier invoice crash: safe int parsing for account numbers

### Remaining Issues
1. Travel expense: 0/8 (per diem needs perDiemCompensation, not cost)
2. Supplier invoice voucher: 0/8 despite success (scoring might not check vouchers)
3. Some invoice tasks: 6/7 (86%) - one field wrong, need to identify which
4. Token expiry: 1 batch hit 403 from platform (not our bug)

### Tier 3 Status
Tier 3 should be opening now. Haven't seen any Tier 3 tasks yet in submissions.
Will continue iterating and watch for new task patterns.

### Next Steps
1. Fix travel expense (per diem compensation API)
2. Investigate invoice 6/7 partial scores
3. Watch for Tier 3 tasks in next batches
4. Continue efficiency optimization
