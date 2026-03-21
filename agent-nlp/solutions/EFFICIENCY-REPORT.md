# Efficiency Report -- Self-Improving Loop

Generated: 2026-03-21 12:03:16

## Summary

- Total request runs analyzed: 177
- Total excess writes: -211
- Total 4xx errors: 81
- Task types observed: 15

## Per-Task Breakdown

| Task Type | Runs | Avg W | Opt | Waste | Errors | OK% |
|-----------|------|-------|-----|-------|--------|-----|
| create_invoice | 31 | 0.3 | 1 | -0.7 | 18 | 90% |
| create_project | 9 | 1.2 | 2 | -0.8 | 11 | 89% |
| create_department | 10 | 0.2 | 1 | -0.8 | 4 | 100% |
| create_credit_note | 21 | 0.1 | 1 | -0.9 | 6 | 95% |
| create_employee | 11 | 0.1 | 1 | -0.9 | 2 | 100% |
| create_supplier | 10 | 0.0 | 1 | -1.0 | 0 | 100% |
| register_payment | 9 | 0.0 | 1 | -1.0 | 3 | 100% |
| create_customer | 9 | 0.0 | 1 | -1.0 | 0 | 100% |
| create_product | 9 | 0.0 | 1 | -1.0 | 0 | 100% |
| create_project_invoice | 12 | 1.5 | 3 | -1.5 | 18 | 92% |
| register_supplier_invoice | 10 | 0.4 | 2 | -1.6 | 4 | 60% |
| create_dimension | 10 | 0.4 | 2 | -1.6 | 4 | 60% |
| create_invoice_with_payment | 9 | 0.0 | 2 | -2.0 | 0 | 100% |
| process_salary | 10 | 0.7 | 3 | -2.3 | 7 | 100% |
| create_travel_expense | 7 | 0.4 | 3 | -2.6 | 4 | 100% |

## Next Steps

1. Fix 4xx errors first (each error reduces efficiency bonus)
2. Eliminate unnecessary writes in highest-waste executors
3. Re-run this script after changes to verify improvement
4. Deploy and submit to measure real efficiency delta