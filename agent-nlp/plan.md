# Tripletex AI Accounting Agent -- Execution Plan

**Track:** NLP | **Weight:** 33.33%
**Last updated:** 2026-03-20 07:00 CET
**Approach:** A (LLM Agent with Gemini 2.5 Flash + generic Tripletex tool)
**Bot version:** tripletex_bot_v2.py

## Current Scores

| Task Type | Score | Max | Notes |
|-----------|-------|-----|-------|
| Create customer | 8/8 | 100% | Locked in |
| Register payment | 2/7 | 29% | Fixed, needs re-test |

## Development Workflow (mandatory)

Every code change follows this pipeline. No exceptions.

```
1. Code change (follow Boris: explore -> plan -> code)
2. Build Docker locally (OrbStack)
3. Test against sandbox API (localhost:8080/solve)
4. QC subagent reviews results (pass/fail per task type)
5. Only if QC passes: deploy to Cloud Run
6. Smoke test Cloud Run endpoint
7. JC manually submits on competition platform
```

**Why:** Competition submissions are limited (5/task type/day, ~150 total/day). Every failed submission is a wasted slot. Local testing with the sandbox API catches failures for free.

## Phase 0: Set Up Local Test Infrastructure (CURRENT)

**Goal:** Build the local Docker + QC workflow so we stop burning competition submissions on untested code.

**Deliverables:**
A. Docker build + run script using OrbStack
B. Test harness script: sends all task type prompts to localhost:8080/solve with sandbox credentials
C. QC subagent: reviews test results, produces pass/fail matrix, blocks deploy on failures

**Sandbox credentials:** In `../.env` (TRIPLETEX_BASE_URL, TRIPLETEX_SESSION_TOKEN)
**Note:** Sandbox is PERSISTENT (data accumulates). Competition sandbox is FRESH each time.

**Commit after:** Yes.

## Phase 1: Audit All 30 Task Types (DONE)

Completed in Session 3. Results:
- PASS: customer, employee, product, department, invoice, project
- FIXED: payment (pre-existing invoice handling), credit note
- KNOWN ISSUE: travel expense (paymentType field), module enable (405 via proxy)

## Phase 2: Fix Failures (DONE)

All critical fixes applied. Key learnings captured in MEMORY.md.

## Phase 3: Local QC + Efficiency (NEXT after Phase 0)

**Goal:** Run full test suite locally. For task types that score perfectly, reduce API calls.

**Method:** Use local Docker + QC subagent to iterate without burning submissions.

## Phase 4: Tier 2 Preparation (Friday)

Tier 2 opens with 2.0x multiplier. Multi-step workflows: invoicing with payment, credit notes, travel expenses, employment details. These are worth 2x Tier 1 tasks.

## Phase 5: Tier 3 Preparation (Saturday)

Tier 3 opens with 3.0x multiplier. Complex scenarios: bank reconciliation, ledger corrections, year-end closing. A single perfect Tier 3 task = up to 6.0 points.

## Key Dates

| Time | What |
|------|------|
| Daily 01:00 CET | Rate limits reset |
| Friday morning | Tier 2 opens (2x multiplier) |
| Saturday morning | Tier 3 opens (3x multiplier) |
| Sunday 09:00 | Feature freeze |
| Sunday 15:00 | Competition ends |
