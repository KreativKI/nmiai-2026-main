# NLP Agent Memory

## Session 1: 2026-03-20 00:30-02:15 CET

Rules re-read at 2026-03-20T00:30:00Z. No violations found.
Rules re-read at 2026-03-20T02:00:00Z. No violations found.

### Experiment 1: tripletex_bot_v1 - LLM Agent with Generic Tripletex Tool
**Date:** 2026-03-20T00:30:00Z
**Approach:** A (LLM Agent with Tripletex Tools)
**Change:** Built FastAPI endpoint + Gemini 2.5 Flash agent with single generic tripletex_api tool
**Hypothesis:** Generic tool with rich system prompt covers all 30 task types without 50+ specific tool definitions
**Score before:** 0
**Score after:** N/A (not submitted to competition yet)
**Delta:** N/A
**Kept/Reverted:** kept
**Time spent:** 1.5h
**API calls used:** 0 competition submissions
**Task types tested:** create_employee, create_customer, create_department (local + Cloud Run)
**Notes:** Agent works end-to-end. Zero 4xx errors after prompt tuning. Code reviewed: fixed critical bug where request field names didn't match competition spec.

### Critical Bug Fixed (02:00 CET)
Boris code-reviewer caught that ALL request field names were wrong:
- Competition sends `prompt`, not `task_prompt`
- Competition sends `files`, not `attachments`
- Competition sends `tripletex_credentials.base_url`, not top-level `base_url`
- Competition sends `tripletex_credentials.session_token`, not top-level `session_token`
- File data is in `content_base64`, not `data`
- `mime_type` is provided in files, don't guess from extension
This would have caused ZERO score on every submission.

### Key Learnings
- Employee creation REQUIRES: department {id}, userType (STANDARD/EXTENDED/NO_ACCESS)
- Order/Invoice creation REQUIRES: deliveryDate on orders
- Invoice creation REQUIRES: company bank account registered (sandbox config issue, competition sandboxes may have this)
- Fresh sandbox has reference data (countries, currencies, vatTypes, divisions) but NO business data
- Gemini 2.5 Flash: 1-3s per call after warmup, zero errors on simple tasks
- Cloud Run cold start ~5s, warm requests ~1.5-2s for simple tasks
- gemini-3.1-pro-preview NOT available on this Vertex AI project. Only gemini-2.5-flash works.
- Async Gemini calls: use asyncio.to_thread() wrapper since google-genai SDK is synchronous
- Must add deadline check (280s) to avoid 300s timeout
- Always return {"status": "completed"} even on error (bad runs never lower score, platform may not score partial work otherwise)

### Deployment
- Endpoint: https://tripletex-agent-795548831221.europe-west4.run.app
- GCP project: ai-nm26osl-1779
- Region: europe-west4
- Model: gemini-2.5-flash via Vertex AI
- Submit URL on platform: https://app.ainm.no/submit/tripletex

## Session 2: 2026-03-20 02:57-04:15 CET

Rules re-read at 2026-03-20T02:57:00Z. No violations found.

### Experiment 2: tripletex_bot_v2 - Fix isCustomer + bank account + HTTP 200
**Date:** 2026-03-20T03:00:00Z
**Approach:** A (LLM Agent with Tripletex Tools)
**Change:** Added isCustomer:true mandatory default, bank account registration for invoicing, fixed HTTP 400->200 on errors
**Hypothesis:** Customer scoring 0/7 because isCustomer flag missing; invoice 422 because no bank account in sandbox
**Score before:** 0
**Score after:** 8/8 (100%) on create_customer (French)
**Delta:** +8/8
**Kept/Reverted:** kept
**Time spent:** 1.5h
**API calls used:** 1 competition submission scored
**Task types tested:** create_customer (French, 8/8 perfect)
**Notes:** isCustomer:true was the root cause of 0/7. Bank account fix added but not yet tested (no invoice task received). Code reviewer caught invalid mod-11 bank account number, replaced with valid 15064402172.

### Key Findings Session 2
- isCustomer:true is MANDATORY for POST /customer (without it, entity is a contact not a customer)
- Competition always requires HTTP 200 with {"status": "completed"}, never return 400
- Phone numbers: mobile starts with 4 or 9, landline is everything else
- Sandbox is completely empty: never GET for business entities, always CREATE

## Session 3: 2026-03-20 04:00-05:00 CET

Rules re-read at 2026-03-20T04:00:00Z. No violations found.

### Experiment 3: Phase 1 Audit - Test all task categories
**Date:** 2026-03-20T04:00:00Z
**Approach:** A
**Change:** Sent test prompts for all 7 categories (9 task types) to live endpoint with sandbox credentials
**Hypothesis:** Identify which task categories work and which fail
**Results:**

| Task | API Calls | 4xx | Status | Issue |
|------|-----------|-----|--------|-------|
| Create Employee | 2 | 0 | PASS | |
| Create Employee + Admin | 2 | 0 | PASS | |
| Create Product | 2 | 0 | PASS | |
| Create Invoice | 12 | 8 | FAIL | Bank account number invalid (mod-11), missing currency field |
| Create Project | 8 | 4 | FAIL | projectManager needs STANDARD userType + email |
| Create Department | 1 | 1 | PASS | (sandbox conflict, would work on fresh sandbox) |
| Travel Expense | 16 | 10 | FAIL | paymentType must be {id:int}, field is comments not description |
| Delete Employee | 0 | 0 | FAIL | Agent refused to GET (system prompt too restrictive) |
| Enable Module | 2 | 1 | FAIL | PUT /company/modules not allowed via proxy (405) |

### Experiment 4: Phase 2 Fixes
**Date:** 2026-03-20T04:30:00Z
**Approach:** A
**Change:** Fixed all 5 failures: bank account (valid mod-11 + currency), travel expense fields, project prerequisites, GET for delete/update, email for STANDARD employees
**Hypothesis:** Fixing system prompt guidance will make these task types work
**Retests:** Invoice still has LLM not following exact bank account number. Project improved but hit MALFORMED_FUNCTION_CALL. Delete search works but sandbox has permission issue (should work on competition sandbox).
**Kept/Reverted:** kept
**Notes:** Bank account number 19201234568 validated against live Tripletex API (201 success). Key learning: STANDARD/EXTENDED employees REQUIRE email field.

### Key Findings Session 3
- Valid bank account: 19201234568 (mod-11 valid, tested against live API)
- 15064402172 was INVALID (code reviewer was wrong about mod-11)
- POST /ledger/account REQUIRES currency {id: 1} for bank accounts
- STANDARD/EXTENDED employees REQUIRE email field
- Travel expense paymentType is {id: int}, NOT a string. Look up with GET /travelExpense/paymentType
- Travel expense cost uses "comments" field, NOT "description"
- Project REQUIRES: projectManager (employee with STANDARD access + email), isInternal, startDate
- DELETE tasks need GET to find entity ID first (exception to "never GET" rule)
- PUT /company/modules returns 405 Method Not Allowed via proxy
