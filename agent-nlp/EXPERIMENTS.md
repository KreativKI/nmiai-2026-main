# NLP Track Experiments Log

## Competition Scores (latest)

| Task Type | Score | Max | Submission | Notes |
|-----------|-------|-----|------------|-------|
| Create customer (fr) | 8/8 | 100% | Competition | Locked in |
| Unknown task | 8/8 | 100% | Competition | Locked in |
| Register payment | 2/7 | 29% | Competition | Fixed (wrong paymentType), needs re-test |

## QC Results (local Docker, 2026-03-20 12:30 CET)

| Task Type | Status | API Calls | 4xx Errors | Notes |
|-----------|--------|-----------|------------|-------|
| Create customer | PASS | 1 | 0 | isCustomer:true mandatory |
| Create employee | PASS | 2 | 0 | dept + userType required |
| Create product | PASS | 2 | 0 | |
| Create department | PASS | 1 | 0 | |
| Create invoice | PASS | 4 | 0 | Bank acct 1920 PUT, not POST |
| Create project | PASS | 2 | 0 | whoAmI admin as PM |
| Register payment | PASS | 4 | 0 | /invoice/paymentType (incoming) |
| Travel expense | PASS | 4 | 0 | Separate POST /travelExpense/cost |

## Experiment History

### Exp 1: tripletex_bot_v1 (Session 1, 00:30 CET)
- Built FastAPI + Gemini 2.5 Flash agent with generic tripletex_api tool
- Result: Deployed, but field names were wrong (prompt/files/credentials)
- Critical bug caught by Boris code-reviewer

### Exp 2: tripletex_bot_v2 (Session 2, 03:00 CET)
- Fixed isCustomer:true, bank account registration, HTTP 200 on errors
- Result: 8/8 (100%) on create_customer (French)

### Exp 3: Phase 1 Audit (Session 3, 04:00 CET)
- Tested all 7 categories (9 task types) against live endpoint
- PASS: customer, employee, product, department
- FAIL: invoice (bank acct), project (PM access), travel expense (paymentType), delete (GET blocked), module (405)

### Exp 4: Phase 2 Fixes (Session 3, 04:30 CET)
- Fixed bank account, travel expense fields, project prerequisites, GET for delete/update

### Exp 5: Local Docker + QC (Session 4, 07:00 CET)
- Built OrbStack-based local testing pipeline + qc-verify.py
- Catches field-level issues before burning competition submissions

### Exp 6: Invoice fix (Session 4, 08:00 CET)
- Account 1920 exists, use GET id + PUT bankAccountNumber instead of POST

### Exp 7: Project fix (Session 4, 08:30 CET)
- Use sandbox admin from whoAmI as project manager

### Exp 8: Payment fix (Session 4, 11:00 CET)
- GET /invoice/paymentType (incoming), NOT /ledger/paymentTypeOut (outgoing)

### Exp 9: Gemini MALFORMED_FUNCTION_CALL fixes (Session 4, 12:30 CET)
- JSON escaping guidance, temperature=0, MAX_AGENT_TURNS=25
- Reduces error rate from ~15% to ~2%

## Session 5: 2026-03-20 14:00-15:30 CET

### Experiment 10: Tier 2 system prompt expansion (REVERTED)
- Added 7 new workflow sections: employment, update, contact, credit note, project+customer, PDF, multi-line
- System prompt grew 67% (6709 -> 11260 chars)
- Result: Degraded Gemini reliability (product/invoice failures). Reverted.

### Experiment 11: Employment details fix (KEPT)
- Added dateOfBirth requirement + employment/details sequence to system prompt
- Tested employment API directly: dateOfBirth REQUIRED, division NOT required
- Employment creation works: salary=600000, percentage=80% verified via API
- Minimal prompt addition (~200 chars)

### Experiment 12: Gemini MALFORMED_FUNCTION_CALL degradation
- Gemini started producing more MALFORMED errors around 14:30 CET
- Both v2 and v3 affected equally: product and invoice tasks fail intermittently
- Root cause: Gemini API-side, not code change
- Competition impact: low (best score per task retained, bad runs don't lower score)

## Session 6: 2026-03-20 19:00-21:45 CET

### Experiment 13: tripletex_bot_v4 - Structured workflows
**Date:** 2026-03-20T19:00:00Z
**Approach:** C (Structured workflows: LLM extracts fields, Python executes API)
**Change:** Complete rewrite. Gemini extracts {task_type, fields} as JSON, Python functions execute deterministic API sequences. No function calling.
**Hypothesis:** Eliminates MALFORMED_FUNCTION_CALL errors entirely (30-40% rate with function calling)
**Score before:** 8/8 + 8/8 + 6/7 + 4/8 + 2/7
**Score after:** QC 8/8 PASS (not yet submitted to competition)
**Delta:** N/A (pending submission)
**Kept/Reverted:** kept
**Time spent:** 2.5h
**Task types tested:** 8 Tier 1 (all PASS)
**Notes:** Three bugs found and fixed during QC:
1. vatType retry: `.lower()` case mismatch prevented fallback from triggering on invoice vatType rejection
2. Product vatType: omit for standard 25% (sandbox default works), only send for non-standard rates
3. Customer search: Tripletex name search is partial match. Old QC customers polluted results. Fixed: exact match + org number fallback + full list scan

### Key Findings Session 6
- Dev sandbox rejects ALL vatType codes on invoice order lines (even code 3 "Utgående avgift, høy sats"). Competition sandboxes likely configured differently.
- Tripletex GET /customer name search is PARTIAL match (LIKE query). Must filter for exact match locally.
- `.lower()` in string comparisons: if checking `"vatType" in str(...).lower()`, the search term must also be lowercase ("vattype").
- Pre-submit pipeline built: syntax check, health check, QC 8/8, MALFORMED rate check. Single script.

## Bot Versions

| Version | File | Status | Key Change |
|---------|------|--------|------------|
| v1 | bot_v1.py | Superseded | Wrong field names |
| v1.1 | tripletex_bot_v1.py | Superseded | Fixed field names |
| v2 | tripletex_bot_v2.py | Superseded | All fixes, QC 8/8 PASS |
| v3 | tripletex_bot_v3.py | Superseded | v2 + employment details fix |
| v4 | tripletex_bot_v4.py | DEPLOYED | Structured workflows, no function calling |

## Deployed Endpoint
- URL: https://tripletex-agent-795548831221.europe-west4.run.app
- Region: europe-west4
- Model: gemini-2.5-flash via Vertex AI
- Revision: 37
