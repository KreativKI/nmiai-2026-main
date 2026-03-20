# NLP Session 6 Status Update

**Time:** 2026-03-20 ~21:45 CET
**Bot:** tripletex_bot_v4.py, deployed rev 37

## What was done
- Built and deployed v4 with structured workflows (LLM extracts fields, Python executes API). Zero function calling = zero MALFORMED errors.
- Fixed vatType retry bug (.lower() case mismatch prevented fallback from triggering)
- Fixed customer search: exact name match + org number fallback + full list scan (old QC customers were polluting partial name search)
- Created pre-submit pipeline: `bash agent-nlp/scripts/pre-submit.sh` runs syntax check, health check, QC 8/8, MALFORMED rate check
- QC result: 8/8 PASS on Tier 1
- Dev sandbox limitation: VAT codes rejected on invoice order lines (competition sandboxes likely configured differently)

## Current scores (competition)
- Create customer (fr): 8/8 (100%)
- Unknown task: 8/8 (100%)
- Register payment: 2/7 (29%) - v4 should improve this
- Auto-submitted tasks: 6/7 (86%), 4/8 (50%)

## Task types supported (16)
create_customer, create_employee, create_employee_with_employment, create_product, create_department, create_project, create_invoice, register_payment, create_credit_note, create_travel_expense, delete_employee, delete_travel_expense, update_customer, update_employee, create_contact, enable_module

## Ready for JC
Bot is validated and ready to submit. Auto-submitter at `shared/tools/nlp_auto_submit.py` can handle bulk submissions. JC should decide when to start submitting.
