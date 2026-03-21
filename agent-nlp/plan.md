# Tripletex AI Accounting Agent -- Execution Plan

**Track:** NLP | **Weight:** 33.33%
**Last updated:** 2026-03-21 01:00 CET
**Approach:** Structured workflows (LLM extracts fields, Python executes API calls)
**Bot version:** tripletex_bot_v4.py (deployed, rev 47)

## Leaderboard State (2026-03-21 00:50 CET)

| Team | Score | Tasks | Correctness | Efficiency |
|------|-------|-------|-------------|------------|
| #1 Propulsion Optimizers | 46.70 | 18/30 | 14.8 | 31.9 |
| #2 Proof Left to the Reader | 46.17 | 18/30 | 15.5 | 30.7 |
| #3 Slop Overflow | 46.13 | 18/30 | 16.0 | 30.1 |
| #107 Kreativ KI (us) | 29.08 | 18/30 | 14.7 | 14.4 |

**Root cause:** Efficiency bonus is 14.4 vs top teams' ~31.0. Correctness is nearly equal.
The efficiency bonus can DOUBLE tier scores on perfect tasks. Top teams get 4.0 on Tier 2 tasks, we get 1.0-2.0.

## Current Phase: Efficiency + Correctness Sprint (AUTONOMOUS)

JC asleep for 12h. Full autonomy granted. Boris workflow mandatory.

### Strategy: Fix Quality First, Submit Second
1. Minimize write calls (POST/PUT/DELETE) - GET is free
2. Eliminate 4xx errors (each one reduces efficiency bonus)
3. Fix partial-score tasks (tasks 09, 15, 16, 18 have biggest gaps)
4. Prepare for Tier 3 (opens Saturday morning, 3x multiplier)

### Phase 5A: Efficiency Optimization (IN PROGRESS)
For each executor, remove unnecessary write calls:

| Executor | Current writes | Optimal | Fix |
|----------|---------------|---------|-----|
| create_invoice | PUT bank + POST invoice = 2 | POST invoice = 1 | Remove bank PUT |
| create_product | POST + retry = 2 | POST = 1 | Never send vatType |
| create_project | POST employee (422) + POST project = 2 | POST employee + POST project = 2 | Fix email conflict |
| create_employee | 3 with employment | 3 with employment | OK if employment needed |
| create_customer | 1 | 1 | OK |
| register_payment | 1 PUT | 1 PUT | OK |
| create_credit_note | 1 PUT | 1 PUT | OK |

### Phase 5B: Correctness Fixes
| Task | Our score | Top score | Issue |
|------|-----------|-----------|-------|
| Task 09 | 1.25 | 4.00 | Unknown - need to identify task type |
| Task 15 | 1.50 | 4.00 | Unknown |
| Task 16 | 1.00 | 4.00 | Unknown |
| Task 18 | 0.50 | 4.00 | Unknown |
| Task 11 | --- | 4.00 | Not scored yet |
| Task 17 | --- | 4.00 | Not scored yet |

### Phase 5C: Dimension Fix (DEPLOYED rev 47)
- Changed from department proxy to proper API:
  POST /ledger/accountingDimensionName + POST /ledger/accountingDimensionValue
- Voucher postings use freeAccountingDimension1/2/3
- Added row numbers to voucher postings

### Phase 5D: Tier 3 Preparation (Saturday morning)
- Research complex scenarios: bank reconciliation, error correction, year-end closing
- Build executors for new task types
- Optimize for 3x multiplier tasks

## Completed Today
- Fixed create_dimension (real API, not department proxy)
- Added create_invoice_with_payment for multi-step tasks
- Skipped BETA /supplier endpoint (403), use /customer with isSupplier
- Fixed supplier invoice voucher (balanced postings with row numbers)
- Fixed product number conflicts (GET existing instead of failing)
- Fixed process_salary dateOfBirth for existing employees
- Fixed create_project (create specified PM employee)

## Submission Budget
- 180/day, resets 01:00 CET
- Budget after reset: 180 fresh

## Key Dates
| Time | What |
|------|------|
| Daily 01:00 CET | Rate limits reset |
| Saturday morning | Tier 3 opens (3x multiplier) |
| Sunday 09:00 | Feature freeze |
| Sunday 15:00 | Competition ends |

## Efficiency Rules (from competition docs)
- Only WRITE calls (POST/PUT/DELETE/PATCH) count for efficiency
- GET requests are FREE - read as much as needed
- Each 4xx error reduces efficiency bonus
- Efficiency bonus only applies on PERFECT correctness (1.0)
- Benchmarks recalculated every 6 hours
