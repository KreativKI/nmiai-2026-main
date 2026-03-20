# Tripletex AI Accounting Agent -- Execution Plan

**Track:** NLP | **Weight:** 33.33%
**Last updated:** 2026-03-20 16:00 CET
**Approach:** Structured workflows (LLM extracts fields, Python executes API calls)
**Bot version:** tripletex_bot_v3.py (deployed), tripletex_bot_v4.py (building)

## Current Scores

| Task Type | Score | Max | Notes |
|-----------|-------|-----|-------|
| Create customer (fr) | 8/8 | 100% | Locked in |
| Unknown task (8/8) | 8/8 | 100% | Locked in |
| Register payment | 2/7 | 29% | Fixed, needs re-test |
| 6/7 task (from auto-submit) | 6/7 | 86% | From session 5 auto-submit |
| 4/8 task (from auto-submit) | 4/8 | 50% | From session 5 auto-submit |

## Current Phase: 4 (Building v4)

## Phase 0: Local Test Infrastructure (DONE)
Docker + QC workflow established. qc-verify.py tests 8 Tier 1 + 5 Tier 2 task types.

## Phase 1: Audit All Task Types (DONE)
Completed session 3. All 7 categories tested.

## Phase 2: Fix Failures (DONE)
All critical fixes applied: isCustomer, bank account, payment types, travel expense costs.

## Phase 3: Gemini Reliability Investigation (DONE)
**Finding:** Gemini 2.5 Flash function calling is unreliable (~30-40% MALFORMED errors on complex tasks). Neither prompt engineering nor model fallback (gemini-2.5-pro) fully solves this. Claude not available on this GCP project.

**Decision (JC approved):** Switch to structured workflows. LLM extracts fields only, Python executes deterministic API sequences. This eliminates function calling failures.

## Phase 4: Build tripletex_bot_v4 (ACTIVE)

**Architecture:** See solutions/plan_v4.md for full design.

```
POST /solve -> Gemini extracts {task_type, fields} -> Python executes API sequence -> {"status": "completed"}
```

**Task types to implement (15):**
A. create_customer, create_employee, create_product, create_department
B. create_project, create_invoice, register_payment, create_travel_expense
C. create_credit_note, create_employment, update_customer, update_employee
D. delete_employee, delete_travel_expense, create_contact

**Boris workflow:** Explore (done) -> Plan (done) -> Code -> Review -> Simplify -> Validate -> Commit

**Validation criteria:**
- QC 8/8 PASS on Tier 1 (must match v3 baseline)
- QC 13/13 PASS on Tier 1 + Tier 2
- Two consecutive QC passes before deploying
- Zero MALFORMED errors (no function calling used)

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
