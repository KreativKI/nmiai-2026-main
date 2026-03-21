# NLP Agent Session Handoff

**Session:** 2026-03-21 00:30 - 04:30 CET (autonomous overnight)
**Rev:** 64 deployed (tripletex-agent-00064-p2t)
**Score trend:** 29.08 -> estimated ~38-42

## What was accomplished
- 33 batches submitted (134 submissions today)
- Dimension task: 0/13 -> 13/13 (correct API found and implemented)
- Supplier entity: 0/8 -> 8/8 (POST /supplier is NOT BETA)
- Project PM: fixed admin=PM pattern with name update
- Salary: 0/8 -> 4-5/8 (monthly×12 for annualSalary)
- Travel expense: travelDetails added (reiseregning type)
- Removed ~10 unnecessary write calls and error patterns
- 5 critical bug fixes from Butler code review

## What still needs fixing (ranked by impact)
A. **Travel expense** still 0/8 despite all APIs succeeding. Per diem works (201). Something in the data is wrong. Needs deeper investigation.
B. **Payment reversal** classified as credit note, scores 2/8. May need a different approach entirely.
C. **Supplier invoice voucher** - inconsistent (0-8/8). Some accounts have locked VAT codes.
D. **Salary** at 4-5/8 - need to verify what fields are still wrong
E. **Project** at 5-7/7 - PM name update helps but may need more

## Current code architecture
- Bot: agent-nlp/solutions/tripletex_bot_v4.py
- 22 task types in TASK_EXECUTORS dict
- Structured workflow: Gemini extracts fields -> Python API calls
- No function calling (eliminated MALFORMED errors)

## Key technical findings
- POST /supplier exists and is NOT BETA
- POST /ledger/accountingDimensionName / accountingDimensionValue for dimensions
- POST /salary/payslip does NOT exist (no POST endpoint in API)
- Account 2400 postings require supplier reference
- Some accounts have locked VAT codes (don't force vatType)
- Admin often has PM's email (competition pattern)
- GET calls are FREE for efficiency scoring

## Submissions remaining
- Today: 46/180 left (resets 01:00 CET)
- Competition ends: Sunday 15:00 CET
