# Efficiency Plan -- Closing the Gap from 14.4 to 30+

**Created:** 2026-03-21 13:00 CET
**Goal:** Double our efficiency bonus from 14.4 to 28+ (match top teams at ~31)
**Why this matters:** Our correctness (14.7) nearly matches #1 (14.8). The ENTIRE 17-point gap is efficiency.

---

## How Efficiency Scoring Works (from competition docs)

```
If correctness < 1.0:  score = correctness × tier          (NO bonus)
If correctness = 1.0:  score = tier × (1 + efficiency_bonus)  (up to 2× tier)
```

Two factors determine the bonus:
A. **Call efficiency**: our write calls vs "best known solution" for that task
B. **Error cleanliness**: number of 4xx errors (each one reduces bonus)

Benchmarks recalculated every 12 hours. As competitors improve, the bar rises.

**Max scores per tier:**
| Tier | Imperfect (no bonus) | Perfect + worst efficiency | Perfect + best efficiency |
|------|---------------------|---------------------------|--------------------------|
| 1 | 0.0 - 1.0 | ~1.05 | **2.0** |
| 2 | 0.0 - 2.0 | ~2.1 | **4.0** |
| 3 | 0.0 - 3.0 | ~3.15 | **6.0** |

---

## Current State (321 submissions analyzed)

| Check count | Submissions | Perfect rate | Efficiency locked? |
|-------------|-------------|-------------|-------------------|
| 6 checks | 9 | 100% (9/9) | YES - optimize these NOW |
| 7 checks | 95 | 45% (43/95) | PARTIAL - fix failures to unlock bonus |
| 8 checks | 200 | 30% (60/200) | PARTIAL - biggest opportunity |
| 13 checks | 17 | 29% (5/17) | PARTIAL - dimension tasks |

---

## The Plan: 5 Phases

### Phase 1: AUDIT (immediate, no submissions needed)

**Goal:** Know exactly where every write call goes for every task type.

Steps:
1. Run `efficiency_analyzer.py` on Cloud Run logs from overnight session
2. For each of the 22 executors, count: current writes, current 4xx errors
3. Compare against theoretical minimum writes (see table below)
4. Rank by: (current_writes - minimum_writes) × submission_frequency × tier

**Theoretical minimum writes per executor on a fresh sandbox:**

| Executor | Minimum writes | Breakdown | Notes |
|----------|---------------|-----------|-------|
| create_customer | 1 | POST customer | Nothing else needed |
| create_product | 1 | POST product | Never send vatType |
| create_department | 1 per dept | POST department | Simple |
| create_supplier | 1 | POST supplier | Single call |
| create_employee | 1 | POST employee | Use existing dept if any, else 2 |
| create_employee_with_employment | 3 | POST emp + POST employment + POST details | Dept from GET if exists |
| delete_employee | 1 | DELETE employee | GET to find ID is free |
| delete_travel_expense | 1 | DELETE travelExpense | GETs to find are free |
| update_customer | 1 | PUT customer | GET to find is free |
| update_employee | 1 | PUT employee | GET to find is free |
| register_payment | 1 | PUT invoice/:payment | All GETs to find customer/invoice/paymentType are free |
| create_credit_note | 1 | PUT invoice/:createCreditNote | All GETs are free |
| create_contact | 1-2 | POST customer (if needed) + POST contact | Customer might need creating |
| create_invoice | 2-3 | POST customer + PUT bank account + POST invoice | Bank PUT is unavoidable on fresh sandbox |
| create_invoice_with_payment | 3-4 | invoice writes + PUT payment | Inherits invoice |
| create_project | 1-2 | POST project + maybe PUT admin name | Admin IS the PM in most cases |
| create_project_invoice | 3-5 | POST customer + POST project + PUT bank + POST invoice | Lots of setup |
| create_travel_expense | 2+N | POST emp + POST travel + N POST costs + maybe POST perDiem | Employee might exist |
| process_salary | 3-4 | POST emp + POST employment + POST details | Depends on existing employee |
| register_supplier_invoice | 2 | POST supplier + POST voucher | Minimum 2 writes |
| create_dimension | 1+N | POST dimName + N POST dimValues + maybe POST voucher | Depends on whether posting is needed |
| enable_module | 0-1 | POST department or nothing | Proxy blocks PUT modules |

### Phase 2: ZERO 4xx ERRORS (highest ROI, do first)

**Goal:** Eliminate ALL 4xx errors. Each error is pure waste that directly reduces efficiency bonus.

**Pattern: "Look Before You Leap" (GET is free, errors are expensive)**

For every executor, follow this rule:
```
BEFORE any POST/PUT: GET to check if entity exists (FREE)
BEFORE any field: validate locally (no API call needed)
NEVER: POST with fields that might be rejected
NEVER: PUT fields that haven't changed
```

Specific 4xx error sources to eliminate:

A. **POST /employee 422 (email conflict)** - 36 errors
   - Rev 67 fix: check admin match first, GET existing employee
   - Remaining risk: when admin email doesn't match AND employee already exists from a previous step
   - Fix: add GET /employee by email as fallback check

B. **PUT /employee 422 (dateOfBirth)** - 7 errors
   - Rev 67 fix: only PUT when dateOfBirth is null
   - Remaining risk: PUT with empty/invalid dateOfBirth
   - Fix: validate dateOfBirth format before PUT (YYYY-MM-DD)

C. **403 errors (expired token)** - ~10 errors
   - Can't fix server-side. But we CAN detect it early and stop making more calls.
   - Fix: if any call returns 403, abort immediately (no more writes)

D. **POST with invalid vatType** - occasional
   - Fix: never send vatType on products (sandbox default handles it)
   - For invoices: use the looked-up vat_map, never hardcode

E. **POST /department conflict** - when dept number already taken
   - Fix: GET /department first (free), use existing if found

### Phase 3: MINIMIZE WRITES ON PERFECT TASKS (second highest ROI)

**Goal:** For tasks already at 100% correctness, reduce writes to match the benchmark.

**Priority: Tasks with the biggest write reduction opportunity × tier multiplier**

#### 3A: Single-write tasks (already optimal, verify only)
These should be at 1 write. If they're at more, something is wrong:
- create_customer: should be 1 POST. Verify no extra calls.
- create_product: should be 1 POST. Verify no vatType retry.
- create_supplier: should be 1 POST. Verify no fallback to /customer.
- register_payment: should be 1 PUT. Verify no extra GETs to find paymentType get logged as writes.
- create_credit_note: should be 1 PUT. Verify.

#### 3B: Department creation optimization
The `ensure_department` helper is called from many executors. On a fresh sandbox:
- GET /department (free) -> empty -> POST /department (1 write)
This 1 write happens in EVERY executor that needs a department. For tasks that create an employee as a prerequisite, this adds 1 unnecessary write if we can find another way.

**Question to research:** Does the fresh sandbox have a default department (id=1)?
- If YES: skip ensure_department entirely, use id=1
- If NO: the POST is unavoidable, but make sure it only happens ONCE per request

#### 3C: Invoice bank account optimization
Currently: GET account 1920 (free) -> if no bankAccountNumber -> PUT (1 write)
This PUT happens on EVERY invoice task. On a fresh sandbox, account 1920 never has a bank number.

**Question to research:** Can we create an invoice WITHOUT the bank account?
- If YES: skip the PUT entirely (save 1 write per invoice task)
- If NO: the PUT is unavoidable, accept it

#### 3D: Project PM optimization
Currently: GET whoAmI (free) -> compare admin name/email -> POST /employee if no match -> POST /project
The admin IS the PM in most competition variants. With rev 67's look-before-leap:
- Best case: 1 POST /project (admin matches) = 1 write
- Worst case: POST /employee + POST /project = 2 writes

#### 3E: Travel expense employee optimization
Currently: GET /employee by name (free) -> if found use existing -> else POST
On a fresh sandbox, the employee never exists (except for delete_travel_expense tasks).
So POST is usually unavoidable. But ensure we're not creating duplicate employees.

### Phase 4: FIX 86% TASKS TO 100% (unlocks efficiency bonus)

Some tasks score 6/7 (86%) or 5/8 (63%). One missing field. Fix it -> unlock the full efficiency bonus.

**These tasks are worth more than optimizing perfect tasks**, because going from 86% to 100% with efficiency bonus could mean going from 1.72 to 4.0 on a Tier 2 task (2.3x improvement).

Known partial-score tasks to fix:
A. **Travel expense 0/8** - date fix untested, per diem fields, costs
B. **Payment reversal 2/8** - classified as credit_note, may need different approach
C. **Salary 4-5/8** - annualSalary x12 partial, bonus handling
D. **Supplier invoice voucher 0-8/8** - inconsistent, locked VAT codes

### Phase 5: TIER 3 PREPARATION (Saturday morning)

Apply ALL efficiency lessons from Phases 1-4 to Tier 3 tasks:
- Minimum writes from the start
- Zero 4xx errors from the start
- Every executor follows look-before-leap pattern
- Test with efficiency_analyzer before submitting

Tier 3 tasks are worth 3x (up to 6.0). One perfect + efficient Tier 3 task = three perfect Tier 1 tasks.

---

## Execution Timeline

| When | Phase | Action |
|------|-------|--------|
| Now | 1 | Run audit: efficiency_analyzer on logs, map write counts |
| Now | 2 | Code: add early-abort on 403, validate fields before POST |
| Now | 3A | Code: verify single-write tasks are actually single-write |
| Now | 3B | Research: does fresh sandbox have default department? |
| Now | 3C | Research: can invoices work without bank account PUT? |
| Next submissions | 2+3 | Submit batch with rev 67+, analyze new instrumented logs |
| After analysis | 4 | Fix highest-value partial tasks (travel expense, salary) |
| Saturday AM | 5 | Build Tier 3 executors with efficiency-first design |
| Sunday 09:00 | - | FEATURE FREEZE |

---

## Success Metrics

| Metric | Current | Target | How to measure |
|--------|---------|--------|----------------|
| Efficiency score | 14.4 | 28+ | Leaderboard |
| 4xx errors per request | ~0.46 (81/177) | <0.05 | Cloud Run logs |
| Avg writes per simple task | unknown | 1.0 | Instrumentation |
| Avg writes per complex task | unknown | 3-4 | Instrumentation |
| Perfect rate (100%) | 36% | 60%+ | Submission log |

---

## Key Principle

**Every write call must justify its existence.** Before adding any POST/PUT/DELETE to an executor, answer:
1. Is this call absolutely necessary for correctness?
2. Can I avoid it with a free GET check first?
3. Is there a way to achieve the same result with fewer calls?

If a write call isn't necessary, remove it. If a write call might fail, check first.
The competition rewards agents that "get it right without trial-and-error."

---

## Tools for Execution

| Tool | Command | When to use |
|------|---------|-------------|
| Efficiency Analyzer | `python3 agent-nlp/scripts/efficiency_analyzer.py --hours 12 --save` | After every submission batch |
| Self-Improve Pipeline | `python3 agent-nlp/scripts/self_improve.py --hours 12` | After analyzer, generates fix list |
| Write Tracking | Built into bot (Cloud Run logs: `writes=N, errors_4xx=N`) | Always active |
| Smoke Test | `curl -s endpoint/health` | After every deploy |
| Syntax Check | `python3 -c "import ast; ast.parse(...)"` | Before every deploy |
