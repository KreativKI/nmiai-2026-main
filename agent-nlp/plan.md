# Tripletex AI Accounting Agent -- Execution Plan

**Track:** NLP | **Weight:** 33.33%
**Last updated:** 2026-03-20 21:45 CET
**Approach:** Structured workflows (LLM extracts fields, Python executes API calls)
**Bot version:** tripletex_bot_v4.py (deployed, rev 37, QC 8/8 PASS)

## Current Scores

| Task Type | Score | Max | Notes |
|-----------|-------|-----|-------|
| Create customer (fr) | 8/8 | 100% | Locked in |
| Unknown task (8/8) | 8/8 | 100% | Locked in |
| Register payment | 2/7 | 29% | Fixed, needs re-test |
| 6/7 task (from auto-submit) | 6/7 | 86% | From session 5 auto-submit |
| 4/8 task (from auto-submit) | 4/8 | 50% | From session 5 auto-submit |

## Current Phase: 5 (Tier 2 Submission)

## Phase 0: Local Test Infrastructure (DONE)
Docker + QC workflow established. qc-verify.py tests 8 Tier 1 + 5 Tier 2 task types.

## Phase 1: Audit All Task Types (DONE)
Completed session 3. All 7 categories tested.

## Phase 2: Fix Failures (DONE)
All critical fixes applied: isCustomer, bank account, payment types, travel expense costs.

## Phase 3: Gemini Reliability Investigation (DONE)
**Finding:** Gemini 2.5 Flash function calling is unreliable (~30-40% MALFORMED errors on complex tasks). Neither prompt engineering nor model fallback (gemini-2.5-pro) fully solves this. Claude not available on this GCP project.

**Decision (JC approved):** Switch to structured workflows. LLM extracts fields only, Python executes deterministic API sequences. This eliminates function calling failures.

## Phase 4: Build tripletex_bot_v4 (DONE)

**Architecture:** LLM extracts {task_type, fields} -> Python executes API sequence -> {"status": "completed"}

**Result:** 16 task types implemented. QC 8/8 PASS on Tier 1. Deployed rev 37. Zero MALFORMED errors.

**Key fixes during validation:**
- vatType retry: .lower() case mismatch prevented fallback
- Product vatType: omit for 25% (sandbox default), only send non-standard
- Customer search: exact match + org number fallback + full list scan
- Pre-submit pipeline: `bash agent-nlp/scripts/pre-submit.sh`

## Phase 5: Tier 2 Submission (after v4 validated)
Submit via interactive auto-submitter. JC controls each submission.
Target: 100% field correctness on all task types before submitting.

## Phase 6: Tier 3 Preparation (Saturday)
Tier 3 opens with 3.0x multiplier. Complex scenarios. Extend v4 with Tier 3 task types.

## Key Dates

| Time | What |
|------|------|
| Daily 01:00 CET | Rate limits reset |
| Friday (today) | Tier 2 open (2x multiplier) |
| Saturday morning | Tier 3 opens (3x multiplier) |
| Sunday 09:00 | Feature freeze |
| Sunday 15:00 | Competition ends |

## Key Constraints
- 5 submissions per task type per day (resets 01:00 CET)
- ~150 total submissions per day (30 types x 5)
- Bad runs never lower score, but waste daily rate limit
- 100% correctness target before submitting (JC directive)
