# NLP Agent Session Handoff

**Session:** 2026-03-21 00:30 - 05:15 CET (autonomous overnight)
**Rev:** 65 deployed (tripletex-agent-00065-2h5)
**Score trend:** 29.08 -> estimated ~40-43
**Submissions:** 177/180 today (budget exhausted, resets 01:00 CET)

## What was accomplished
- 44 batches (177 submissions), average score 0.60 (up from 0.54)
- Dimension: 0/13 -> 13/13 (accountingDimensionName API, 5x confirmed)
- Supplier entity: 0/8 -> 8/8 (POST /supplier is NOT BETA)
- Salary: 0/8 -> 4-5/8 (monthly x12 for annualSalary)
- Project PM: admin=PM pattern with name update (PUT admin name)
- Travel expense: travelDetails added, perDiemCompensation endpoint, date fix
- Removed unnecessary write calls and 4xx error patterns
- 5 critical bug fixes from Butler code review
- 20 revisions deployed (rev 45 -> 65)

## What still needs fixing (ranked by impact)
A. **Travel expense** 0/8 despite ALL APIs succeeding (201). Rev 65 fixes departure/return dates. UNTESTED (budget exhausted).
B. **Payment reversal** 2/8 - classified as credit_note but should reverse payment differently
C. **Supplier invoice voucher** 0-8/8 inconsistent. Some accounts have locked VAT codes (fixed in rev 63).
D. **Salary** 4-5/8 - annualSalary x12 partially fixed. May need bonus handling.
E. **Project/Project invoice** 5-7/7 - PM name update helps. Still some edge cases.

## Key technical discoveries
- POST /supplier: NOT BETA (confirmed in Swagger docs, works 8/8)
- POST /ledger/accountingDimensionName + /accountingDimensionValue: NOT BETA
- POST /salary/payslip: DOES NOT EXIST (no POST endpoint in API)
- Account 2400 postings require supplier reference
- Some accounts have locked VAT codes (don't force vatType)
- Admin often has PM's email (competition pattern: update admin name)
- GET calls are FREE for efficiency scoring (only POST/PUT/DELETE/PATCH count)
- travelDetails required for reiseregning type (vs ansattutlegg)
- monthlySalary is readOnly (derived from annualSalary/12)

## Current code
- Bot: agent-nlp/solutions/tripletex_bot_v4.py (~1500 lines)
- 22 task types in TASK_EXECUTORS
- Architecture: Gemini extracts {task_type, fields} -> Python API calls
- No function calling (eliminated MALFORMED errors)

## Next session priorities
1. Test travel expense date fix (rev 65, untested)
2. Fix payment reversal approach
3. Improve salary scoring
4. Watch for Tier 3 tasks (opened Saturday morning)
5. Optimize efficiency on tasks already at 100%
6. Rate limit resets 01:00 CET - 180 fresh submissions
