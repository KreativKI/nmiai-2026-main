# Tripletex AI Accounting Agent — Rules

**Source:** Competition docs fetched 2026-03-20 00:00 CET
**Last verified:** 2026-03-20 00:00 CET
**Track weight:** 33.33% of total score
**Change log:** (append here when rules change)
- 2026-03-20 00:00: Initial rules populated from competition docs
- 2026-03-20 00:30: Added UTC rate limit reset time (midnight UTC = 01:00 CET)

## Submission
- Submit your HTTPS endpoint URL on the platform
- Platform sends POST /solve requests to your endpoint
- Must return HTTP 200 with {"status": "completed"} within 300 seconds
- Rate limit: 5 submissions per task type per day (verified), 2/day (unverified). Resets midnight UTC = 01:00 CET.
- Each submission gets a RANDOM task type (weighted toward less-attempted ones)

## What the Platform Sends
```json
POST /solve
{
  "task_prompt": "Create an employee named...",
  "task_type": "create_employee",
  "attachments": [{"filename": "...", "data": "base64..."}],
  "base_url": "https://xxx.tripletex.dev/v2",
  "session_token": "abc123..."
}
```
- 7 languages: Norwegian, English, Spanish, Portuguese, Nynorsk, German, French
- Some tasks include PDF or image attachments with critical data

## Authentication
- Every Tripletex API call: Basic Auth
- Username: `0` (the digit zero)
- Password: the session_token from the request
- Fresh empty Tripletex sandbox each submission (no pre-existing data)

## 30 Task Types (7 Categories)
A. Employees: create, set roles, update contact info
B. Customers & Products: register customers, create products
C. Invoicing: create invoices, register payments, credit notes
D. Travel Expenses: register or delete expense reports
E. Projects: create projects linked to customers
F. Corrections: delete or reverse incorrect entries
G. Departments: create departments, enable accounting modules

## Scoring
- Field-by-field verification against expected state
- Raw score = points_earned / max_points (0-1)
- Tier multipliers: Tier 1 = 1.0x, Tier 2 = 2.0x, Tier 3 = 3.0x
- Efficiency bonus (up to 2x tier score) ONLY on perfect correctness
- Max score per task: up to 6.0 (perfect Tier 3 + best efficiency)
- Best score per task type retained. Bad runs never lower your score.
- Benchmarks recalculated every 12 hours

## Tier Release Schedule
- Tier 1: Available from competition start (foundation tasks)
- Tier 2: Opens early Friday (multi-step workflows)
- Tier 3: Opens early Saturday (complex scenarios)

## Efficiency Bonus
Only applies when ALL fields are correct. Based on:
- Fewer API calls = higher bonus
- Zero 4xx errors = higher bonus
- Do NOT fetch back entities you just created (wastes a call)
- Do NOT make exploratory GETs

## Norwegian Accounting Conventions
- Decimal separator: comma (1.000,50 = 1000.50)
- Date format in prompts: DD.MM.YYYY (but Tripletex API uses YYYY-MM-DD)
- VAT rates: 25% (standard), 15% (food), 12% (transport/hotels), 0% (exempt)
- Currency: NOK
- Nynorsk and Bokmal have different vocabularies for same concepts

## Tripletex API
- Base URL: provided in each request as base_url
- Documentation: https://kkpqfuj-amager.tripletex.dev/v2-docs/
- REST API, JSON payloads
- Sandbox token expires March 31, 2026

## Competition-Wide Rules
- AI tools allowed
- No sharing solutions between teams
- No hardcoded responses
- Repo goes public at Sunday 14:45
- Deadline: Sunday March 22, 15:00 CET
