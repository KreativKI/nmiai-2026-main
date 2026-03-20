# Tripletex AI Accounting Agent -- Execution Plan

**Track:** NLP | **Weight:** 33.33%
**Last updated:** 2026-03-20 07:00 CET
**Approach:** A (LLM Agent with Gemini 2.5 Flash + generic Tripletex tool)
**Bot version:** tripletex_bot_v2.py

## Current Scores

| Task Type | Score | Max | Notes |
|-----------|-------|-----|-------|
| Create customer (fr) | 8/8 | 100% | Locked in |
| Unknown task (8/8) | 8/8 | 100% | Locked in |
| Register payment | 2/7 | 29% | Fixed (wrong paymentType endpoint), needs re-test |

## Development Workflow (mandatory)

Every code change follows this pipeline. No exceptions.

```
1. Boris: explore -> plan -> code -> review -> simplify -> validate
2. Build Docker locally: docker build -t tripletex-agent:local .
3. Start local: docker run -d --name tripletex-agent-local -p 8080:8080 ...
4. Run QC: python3 scripts/qc-verify.py http://localhost:8080
5. QC must show "VERDICT: PASS" (8/8 tasks verified against sandbox API)
6. If QC fails: fix, rebuild, re-run QC. Loop until PASS.
7. Only if QC passes: gcloud run deploy tripletex-agent ...
8. JC manually submits on competition platform
```

**QC script:** `scripts/qc-verify.py` sends 8 task types to the bot, then queries the Tripletex sandbox API to verify entities were created with correct fields. Field-level checks include isCustomer, email, vatType, departmentNumber, invoice amount, travel expense costs, and payment registration.

**Why:** Competition submissions are limited (5/task type/day, ~150 total/day). Every failed submission is a wasted slot. QC catches failures locally for free.

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
