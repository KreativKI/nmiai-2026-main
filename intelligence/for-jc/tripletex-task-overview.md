# Tripletex Track: All 30 Task Types

**Last updated:** 2026-03-20 02:30 CET
**Source:** Competition docs + Tripletex API analysis
**Note:** Exact task type names are not published. These are reconstructed from the 7 categories in the docs + Tripletex API capabilities. We'll learn exact names as we submit and see them.

## How Submissions Work

- You submit your endpoint URL ONCE on the platform
- Each time you click "Submit", the platform sends ONE random task
- Task type is random, weighted toward types you've attempted less
- Each task has 56 variants (7 languages x 8 data sets), so same task type = different prompt each time
- Bad runs NEVER lower your score: only improvements count
- With verified status: up to 3 concurrent, 5 per task type per day

## Rate Limits (Verified)

| What | Limit |
|------|-------|
| Concurrent submissions | 3 |
| Per task type per day | 5 |
| Daily reset | 01:00 CET (midnight UTC) |
| Total possible/day | 150 (30 types x 5) |

## Scoring per Task

| Tier | Multiplier | Max score (perfect + best efficiency) | Opens |
|------|-----------|---------------------------------------|-------|
| Tier 1 | x1 | 2.0 | Now |
| Tier 2 | x2 | 4.0 | Friday morning |
| Tier 3 | x3 | 6.0 | Saturday morning |

Efficiency bonus (up to 2x) only applies when ALL fields are correct.
Fewer API calls + zero 4xx errors = higher bonus.

## The 30 Task Types by Category

### A. Employees (estimated 5-6 tasks)

| # | Likely Task | Tier | API Calls Needed | Our Status |
|---|-------------|------|-----------------|------------|
| 1 | Create employee | Tier 1 | POST /department + POST /employee | Tested, works |
| 2 | Set employee roles/permissions | Tier 1 | POST /employee with userType | Should work |
| 3 | Update employee contact info | Tier 1 | GET /employee + PUT /employee/{id} | Should work |
| 4 | Create employee with employment details | Tier 2 | POST /employee + POST /employment + POST /employment/details | Untested |
| 5 | Delete employee | Tier 1 | GET /employee + DELETE /employee/{id} | Should work |
| 6 | Update employee with address/bank | Tier 2 | GET /employee + PUT /employee/{id} | Untested |

### B. Customers & Products (estimated 4-5 tasks)

| # | Likely Task | Tier | API Calls Needed | Our Status |
|---|-------------|------|-----------------|------------|
| 7 | Create/register customer | Tier 1 | POST /customer | Tested, works |
| 8 | Create product | Tier 1 | POST /product (may need vatType lookup) | Untested |
| 9 | Update customer | Tier 1 | GET /customer + PUT /customer/{id} | Should work |
| 10 | Create product with pricing/VAT | Tier 2 | GET /ledger/vatType + POST /product | Untested |

### C. Invoicing (estimated 5-6 tasks)

| # | Likely Task | Tier | API Calls Needed | Our Status |
|---|-------------|------|-----------------|------------|
| 11 | Create invoice | Tier 1 | POST /customer + POST /invoice (with inline order) | Untested |
| 12 | Register payment on invoice | Tier 2 | GET /invoice + PUT /invoice/{id}/:payment | Untested |
| 13 | Create credit note | Tier 2 | GET /invoice + PUT /invoice/{id}/:createCreditNote | Untested |
| 14 | Create invoice from PDF attachment | Tier 2 | Read PDF + POST /customer + POST /invoice | Untested |
| 15 | Invoice with multiple order lines | Tier 2 | POST /customer + POST /product(s) + POST /invoice | Untested |

### D. Travel Expenses (estimated 3-4 tasks)

| # | Likely Task | Tier | API Calls Needed | Our Status |
|---|-------------|------|-----------------|------------|
| 16 | Register travel expense | Tier 2 | POST /employee + POST /travelExpense | Untested |
| 17 | Add costs to travel expense | Tier 2 | POST /travelExpense/cost | Untested |
| 18 | Delete travel expense | Tier 1 | GET /travelExpense + DELETE /travelExpense/{id} | Should work |

### E. Projects (estimated 3-4 tasks)

| # | Likely Task | Tier | API Calls Needed | Our Status |
|---|-------------|------|-----------------|------------|
| 19 | Create project | Tier 1 | POST /customer + POST /project | Untested |
| 20 | Create project linked to customer | Tier 2 | POST /customer + POST /project | Untested |
| 21 | Project with billing setup | Tier 2 | POST /project + configure invoicing | Untested |

### F. Corrections (estimated 3-4 tasks)

| # | Likely Task | Tier | API Calls Needed | Our Status |
|---|-------------|------|-----------------|------------|
| 22 | Delete incorrect entry | Tier 1 | GET entity + DELETE entity/{id} | Should work |
| 23 | Reverse incorrect invoice | Tier 2 | GET /invoice + PUT /:createCreditNote | Untested |
| 24 | Error correction in ledger | Tier 3 | Complex voucher operations | Untested |
| 25 | Bank reconciliation from CSV | Tier 3 | POST /bank/statement/import + reconciliation | Untested |

### G. Departments & Modules (estimated 3-4 tasks)

| # | Likely Task | Tier | API Calls Needed | Our Status |
|---|-------------|------|-----------------|------------|
| 26 | Create department | Tier 1 | POST /department | Tested, works |
| 27 | Enable accounting module | Tier 2 | PUT /company/modules | Untested |
| 28 | Create department with manager | Tier 2 | POST /employee + POST /department | Should work |
| 29 | Year-end closing | Tier 3 | Complex ledger operations | Untested |
| 30 | Complex multi-step workflow | Tier 3 | Multiple linked operations | Untested |

## What We Know Works (Tested)

| Task | API Calls | Errors | Time | Where Tested |
|------|-----------|--------|------|-------------|
| Create department | 1 | 0 | 1.5s | Cloud Run |
| Create customer | 1 | 0 | 1.7s | Cloud Run |
| Create employee | 2 | 0 | 4.6s | Local |

## What We Don't Know Yet

- Exact names of the 30 task types (we learn these by submitting)
- Whether competition sandboxes have company bank accounts pre-configured (needed for invoicing)
- How attachment-based tasks work in practice (PDF parsing)
- Tier 2 and Tier 3 task complexity

## Our Agent Architecture

- FastAPI endpoint on GCP Cloud Run
- Gemini 2.5 Flash (Vertex AI) as the reasoning engine
- Single generic tool: the LLM decides which API calls to make
- Handles all 7 languages natively (LLM understands them all)
- Multimodal: can process PDF and image attachments

## Endpoint (ready to submit)

```
https://tripletex-agent-795548831221.europe-west4.run.app/solve
```

## Strategy

1. Submit now and start collecting scores on Tier 1 tasks
2. Each submission teaches us a new task type name and how it's scored
3. Use results to improve the agent's system prompt with specific guidance per task
4. When Tier 2 opens (Friday), expand to handle multi-step workflows
5. When Tier 3 opens (Saturday), tackle complex scenarios
