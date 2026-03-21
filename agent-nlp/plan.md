# Tripletex AI Accounting Agent -- Execution Plan

**Track:** NLP | **Weight:** 33.33%
**Last updated:** 2026-03-21 12:00 CET
**Approach:** Structured workflows (LLM extracts fields, Python executes API calls)
**Bot version:** tripletex_bot_v4.py (deployed, rev 47, now with efficiency instrumentation)

## Leaderboard State (2026-03-21 00:50 CET)

| Team | Score | Tasks | Correctness | Efficiency |
|------|-------|-------|-------------|------------|
| #1 Propulsion Optimizers | 46.70 | 18/30 | 14.8 | 31.9 |
| #2 Proof Left to the Reader | 46.17 | 18/30 | 15.5 | 30.7 |
| #3 Slop Overflow | 46.13 | 18/30 | 16.0 | 30.1 |
| #107 Kreativ KI (us) | 29.08 | 18/30 | 14.7 | 14.4 |

**Root cause:** Efficiency bonus is 14.4 vs top teams' ~31.0. Correctness is nearly equal.
The efficiency bonus can DOUBLE tier scores on perfect tasks. Top teams get 4.0 on Tier 2 tasks, we get 1.0-2.0.

## Current Phase: Efficiency Environment Active

### Efficiency Tooling (NEW)

Three new scripts for continuous efficiency improvement:

A. `python3 agent-nlp/scripts/efficiency_analyzer.py` -- Analyze Cloud Run logs, rank optimization targets
B. `python3 agent-nlp/scripts/self_improve.py` -- Full pipeline: analyze, diagnose, prescribe fixes, report
C. `agent-nlp/scripts/write_call_tracker.py` -- Module for per-request write call tracking (imported by bot)

The bot now has write-call instrumentation via contextvars. Every /solve request logs:
- Number of write calls (POST/PUT/DELETE/PATCH)
- Number of 4xx errors
- Full API call sequence

This data appears in Cloud Run logs as `Efficiency detail [task_type]: ...` and is picked up by the analyzer.

### Self-Improving Loop Process

```
1. Run self_improve.py to analyze recent logs
2. Read generated FIXES-QUEUE.md for ranked code changes
3. Implement highest-impact fix
4. Deploy to Cloud Run
5. Submit runs to generate fresh data
6. Re-run self_improve.py to verify improvement
7. Repeat
```

### Strategy: Maximize Efficiency on Already-Correct Tasks FIRST

Priority order:
1. **Fix 4xx errors** (each one reduces efficiency bonus, even on correct tasks)
2. **Reduce writes on perfect-score executors** (efficiency bonus only applies at 1.0 correctness)
3. **Fix broken/low-score tasks** (no efficiency bonus until correctness = 1.0)

### Per-Executor Write Call Budgets

| Executor | Current max writes | Optimal writes | Savings potential |
|----------|-------------------|----------------|-------------------|
| create_customer | 1 | 1 | 0 |
| create_employee | 1-4 | 1-3 | 1 |
| create_employee_with_employment | 3 | 3 | 0 |
| create_product | 1 | 1 | 0 |
| create_department | N (per dept) | N | 0 |
| create_project | 2-4 | 1-2 | 1-2 |
| create_invoice | 2-3 | 1-2 | 1 |
| create_invoice_with_payment | 3-4 | 2-3 | 1 |
| register_payment | 1 | 1 | 0 |
| create_credit_note | 1 | 1 | 0 |
| create_travel_expense | 3-6 | 2-4 | 1-2 |
| process_salary | 3-6 | 2-4 | 1-2 |
| register_supplier_invoice | 2 | 2 | 0 |
| create_dimension | 2+N | 2+N | 0 |

### Error Hotspots (from self_improve.py analysis, 187 requests)

| Executor | 4xx errors | Most common error |
|----------|-----------|-------------------|
| create_invoice | 18 | 403 expired token, PUT employee dateOfBirth |
| create_project_invoice | 18 | POST /employee 422 email conflict, POST /project 422 PM not authorized |
| create_project | 11 | POST /employee 422 email conflict, PUT /employee 422 dateOfBirth |
| process_salary | 7 | PUT /employee 422 dateOfBirth, POST /employee 422 email |
| create_credit_note | 6 | 403 expired token |
| create_dimension | 4 | Varies |
| create_department | 4 | 403 expired token |
| create_travel_expense | 4 | POST /employee 422 email conflict |

### Phase 5A: Efficiency Optimization (TOOLING COMPLETE, FIXES IN PROGRESS)

Known fixes to implement:
A. **create_invoice**: Check if bank account 1920 already has number before PUT (saves 1 write)
B. **create_project**: If admin matches PM name, skip POST /employee entirely (saves 1-2 writes + 422 errors)
C. **process_salary**: GET employee dateOfBirth before PUT; only PUT if null (saves 1 write + 422 error)
D. **create_travel_expense**: GET /employee by name first; if exists, use existing ID (saves 1-2 writes)
E. **create_project_invoice**: Same PM and bank account fixes as create_project + create_invoice

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
- Changed from department proxy to proper API
- Voucher postings use freeAccountingDimension1/2/3

### Phase 5D: Tier 3 Preparation (Saturday morning)
- Research complex scenarios
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
- Built efficiency environment: analyzer, self_improve, write_call_tracker
- Added write-call instrumentation to tripletex_bot_v4.py

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
