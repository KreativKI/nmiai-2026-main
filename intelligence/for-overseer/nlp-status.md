---
from: nlp-agent
timestamp: 2026-03-21 03:50 CET
---

## NLP Status Update (batch 23 complete)

**Rev:** 63 deployed
**Submissions today:** 94/180 used, 86 remaining
**Estimated score:** ~35-38 (up from 29.08 at session start)

### Session Summary (2026-03-21 00:30 - 03:50 CET)
23 batches submitted (92 submissions). Massive code improvements.

### Confirmed Wins
- Dimension: 0/13 -> 13/13 (2x confirmed, accountingDimensionName API)
- Supplier entity: 0/8 -> 8/8 (POST /supplier is NOT BETA)
- Many task types now scoring 100%: customer, employee, product, department, invoice, credit note, register_payment, dimension, supplier

### Remaining Issues (ranked by impact)
1. **Salary (process_salary)**: 0/8. Monthly salary needs ×12 for annualSalary. Fix deployed in rev 61, not yet confirmed by scoring.
2. **Travel expense**: 0/8. All APIs succeed but scored 0. Per diem compensation endpoint works (201). Something in the data is wrong.
3. **Supplier invoice voucher**: 0-8/8. Inconsistent. Some succeed, some fail on VAT type lock. Fixed vatType removal in rev 63.
4. **Payment reversal** (classified as credit_note): 2/8. Credit note partially handles it but isn't the right approach.
5. **Project invoice**: 4-50%. PM access issues (email conflict with admin). Fixed admin=PM pattern in rev 62.
6. **Project PM**: 5-7/7. Email conflict, admin fallback. Fixed in rev 58.

### Efficiency Status
Removed many unnecessary write calls and 4xx errors:
- Removed bank account retry, vatType retry on products
- GET-first for products (avoid "number in use" 422)
- Removed non-existent salary endpoints (no more 500 errors)
- Using POST /supplier directly instead of /customer fallback

### Tier 3
No Tier 3 tasks observed yet in submissions. Watching for them.

### Next Steps
1. Continue iterate/submit loop (86 slots remaining)
2. Focus on understanding travel expense scoring
3. Watch for Tier 3 tasks
4. Consider context rotation if needed
