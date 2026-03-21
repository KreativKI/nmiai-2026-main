---
from: nlp-agent
timestamp: 2026-03-21 05:30 CET
---

## NLP Final Status (daily budget exhausted)

**Rev:** 64 deployed
**Submissions today:** 177/180 (budget reached)
**Average score:** 0.60 (up from 0.54 at session start)
**Estimated total score:** ~40-43 (up from 29.08)

### Score improvements this session
- Average per-submission: 0.54 -> 0.60 (+11%)
- Dimension: 0/13 -> 13/13 (multiple confirmations)
- Supplier entity: 0/8 -> 8/8
- Salary: 0/8 -> 4-5/8
- Many task types now consistently 100%

### Task types performance summary
| Task Type | Best Score | Status |
|-----------|-----------|--------|
| create_customer | 100% | Stable |
| create_employee | 100% | Stable |
| create_product | 100% | Stable |
| create_department | 100% | Stable |
| create_invoice | 100% | Stable |
| register_payment | 100% | Stable |
| create_credit_note | 100% | Stable |
| create_supplier | 100% | Stable |
| create_dimension | 100% | Stable |
| create_invoice_with_payment | 100% | Stable |
| create_project | 71-100% | PM access issue |
| process_salary | 50-63% | Monthly×12 helps |
| create_project_invoice | 50-75% | PM access issue |
| register_supplier_invoice | 0-75% | VAT lock issue |
| create_travel_expense | 0% | Unknown data issue |
| payment reversal | 25% | Wrong approach |

### Next session priorities
1. Rate limits reset at 01:00 CET - 180 fresh submissions
2. Fix travel expense (deep investigation needed)
3. Fix payment reversal approach
4. Improve salary scoring (verify correct annualSalary)
5. Watch for Tier 3 tasks
6. Optimize efficiency on perfect tasks
