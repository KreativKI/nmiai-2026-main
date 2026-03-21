# Tripletex AI Accounting Agent -- Execution Plan

**Track:** NLP | **Weight:** 33.33%
**Last updated:** 2026-03-21 13:30 CET
**Approach:** Structured workflows (LLM extracts fields, Python executes API calls)
**Bot version:** tripletex_bot_v4.py (~1760 lines, 22 executors, rev 68 deployed)
**Efficiency plan:** See EFFICIENCY-PLAN.md for full strategy

## Leaderboard State (2026-03-21 00:50 CET)

| Team | Score | Tasks | Correctness | Efficiency |
|------|-------|-------|-------------|------------|
| #1 Propulsion Optimizers | 46.70 | 18/30 | 14.8 | 31.9 |
| #2 Proof Left to the Reader | 46.17 | 18/30 | 15.5 | 30.7 |
| #3 Slop Overflow | 46.13 | 18/30 | 16.0 | 30.1 |
| #107 Kreativ KI (us) | 29.08 | 18/30 | 14.7 | 14.4 |

**Root cause:** Efficiency bonus is 14.4 vs top teams' ~31.0. Correctness is nearly equal.
The efficiency bonus can DOUBLE tier scores on perfect tasks.

---

## Efficiency Improvements: Yesterday vs Today

### Yesterday (rev 37-65, March 20)
- No efficiency tracking at all: could not measure write calls or 4xx errors
- Executors used "fire and pray": POST /employee without checking if it exists
- 81 4xx errors across 177 submissions (46% of requests had at least one error)
- VAT cache could serve wrong IDs across different sandboxes
- process_salary reported fake "success: True" even when it failed
- Email conflict detection only matched Norwegian "e-post" error text
- per_diem_days variable shadowed itself (used wrong value for per diem block)
- delete_travel_expense could delete wrong employee's expense (no exact name match)

### Today (rev 67, March 21)
- **Write-call instrumentation active**: every request logs `writes=N, errors_4xx=N` + full API call sequence
- **Self-improving pipeline**: `self_improve.py` analyzes logs, diagnoses inefficiencies, prescribes ranked fixes
- **Efficiency analyzer**: `efficiency_analyzer.py` generates per-executor efficiency reports
- **Look-before-leap pattern**: all employee-creating executors now GET first (free), POST only if needed
- **4xx error elimination**: email conflicts caught via admin match (name + email), before POST
- **Conditional writes**: dateOfBirth PUT only when actually null (not on every existing employee)
- **Correct VAT cache**: keyed by (base_url, token), not just base_url
- **Honest success tracking**: process_salary returns real success state
- **Robust error detection**: matches "e-post", "email", "duplicate", "already" in any language
- **Safe concurrency**: contextvars race condition fixed (no shared mutable default)

### Expected Impact (to be measured when submissions resume)
- 4xx errors: 81 -> estimated 20-30 (elimination of the 36 email conflicts + 7 dateOfBirth errors)
- Efficiency bonus: 14.4 -> estimated 20-25 (fewer errors = higher bonus)
- The self-improving loop will continue pushing this higher after each submission batch

---

## Current Phase: Ready to Submit + Self-Improve

### Efficiency Tooling

| Tool | Command | Purpose |
|------|---------|---------|
| Efficiency Analyzer | `python3 agent-nlp/scripts/efficiency_analyzer.py --hours 12 --save` | Analyze logs, rank targets |
| Self-Improve Pipeline | `python3 agent-nlp/scripts/self_improve.py --hours 12` | Full diagnose -> prescribe loop |
| Write Call Tracker | Built into bot via contextvars | Per-request write/error counting |

### Self-Improving Loop (autonomous)

```
1. Submit 10 runs (submitter agent)
2. Read Cloud Run logs (writes=N, errors_4xx=N per request)
3. Run self_improve.py to diagnose + prescribe
4. Implement highest-impact fix (fixer agent)
5. Deploy new revision
6. Repeat from step 1
```

### Strategy: Priority Order

1. **Submit and gather data** (need fresh logs with instrumentation to measure real state)
2. **Fix 4xx errors** (each error reduces efficiency bonus)
3. **Reduce writes on perfect-score executors** (efficiency bonus only at 1.0 correctness)
4. **Fix broken/low-score tasks** (travel expense 0/8, payment reversal 2/8, salary 4-5/8)
5. **Tier 3 preparation** (opens Saturday morning, 3x multiplier)

### Per-Executor Write Call Budgets

| Executor | Current max writes | Optimal writes | Status |
|----------|-------------------|----------------|--------|
| create_customer | 1 | 1 | OPTIMAL |
| create_employee | 1-4 | 1-3 | OPTIMIZED (look-before-leap) |
| create_employee_with_employment | 3 | 3 | OPTIMAL |
| create_product | 1 | 1 | OPTIMAL |
| create_department | N (per dept) | N | OPTIMAL |
| create_project | 2-4 | 1-2 | OPTIMIZED (admin match first) |
| create_invoice | 2-3 | 1-2 | Bank PUT still needed on fresh sandbox |
| create_invoice_with_payment | 3-4 | 2-3 | Inherits invoice pattern |
| register_payment | 1 | 1 | OPTIMAL |
| create_credit_note | 1 | 1 | OPTIMAL |
| create_travel_expense | 3-6 | 2-4 | OPTIMIZED (GET employee first) |
| process_salary | 3-6 | 2-4 | OPTIMIZED (conditional dateOfBirth PUT) |
| register_supplier_invoice | 2 | 2 | OPTIMAL |
| create_dimension | 2+N | 2+N | OPTIMAL |
| create_supplier | 1 | 1 | OPTIMAL |
| create_project_invoice | 4-6 | 2-4 | OPTIMIZED (admin match + bank) |

### Efficiency Fixes Applied (rev 65-68)

| Rev | Fix | Impact |
|-----|-----|--------|
| 66 | Look-before-leap: GET employee before POST | Eliminates ~36 email conflict 422s |
| 66 | Conditional dateOfBirth PUT (only when null) | Eliminates ~7 dateOfBirth 422s |
| 67 | Broadened email conflict detection (4 keywords) | Catches English + Norwegian errors |
| 67 | VAT cache keyed by (base_url, token) | Prevents cross-sandbox VAT mismatch |
| 67 | process_salary returns real success state | Honest efficiency tracking |
| 67 | Fixed contextvars race condition | Safe under concurrent requests |
| 68 | Abort writes on proxy token expiry (403) | Prevents cascading 4xx errors |
| 68 | Per-request dept cache (contextvars) | Avoids duplicate POST /department |

### Error Hotspots (before fixes, 177 requests)

| Executor | 4xx errors | Fix applied |
|----------|-----------|-------------|
| create_invoice | 18 | Bank PUT check exists (stays, needed for fresh sandbox) |
| create_project_invoice | 18 | Admin name/email match before POST /employee |
| create_project | 11 | Admin name/email match before POST /employee |
| process_salary | 7 | Conditional dateOfBirth PUT (only when null) |
| create_credit_note | 6 | 403 expired token (can't fix, server-side) |
| create_travel_expense | 4 | GET employee by name first |
| create_dimension | 4 | Can't fix (varies) |
| create_department | 4 | 403 expired token (can't fix) |

### Correctness Fixes Still Needed

| Task | Score | Issue | Priority |
|------|-------|-------|----------|
| Travel expense | 0/8 | Date fix in rev 65, untested | HIGH (Tier 2 = 2x) |
| Payment reversal | 2/8 | Classified as credit_note, may need different approach | HIGH |
| Salary | 4-5/8 | annualSalary x12 partial, may need bonus handling | MEDIUM |
| Supplier invoice voucher | 0-8/8 | Inconsistent, locked VAT codes | MEDIUM |
| Project/Project invoice | 5-7/7 | PM name edge cases | LOW (mostly working) |

### Phase 5D: Tier 3 Preparation (Saturday morning)
- Research complex scenarios: bank reconciliation, error correction, year-end closing
- Build executors for new task types
- Optimize for 3x multiplier tasks

## Submission Budget
- 180/day, resets 01:00 CET
- Current budget: waiting for availability

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
