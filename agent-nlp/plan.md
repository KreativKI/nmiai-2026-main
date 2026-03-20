# Tripletex AI Accounting Agent -- Execution Plan

**Track:** NLP | **Weight:** 33.33% | **Current Score:** 8/8 on create_customer
**Last updated:** 2026-03-20 04:30 CET
**Approach:** A (LLM Agent with Gemini 2.5 Flash + generic Tripletex tool)
**Bot version:** tripletex_bot_v2.py deployed to Cloud Run

## Phase 1: Audit All 30 Task Types (current)

**Goal:** Test every task category against live endpoint using sandbox credentials. Identify which task types work, which fail, and what's missing in the system prompt.

**Method:** Send representative test prompts to the Cloud Run endpoint using sandbox credentials. Check logs for API calls, errors, and completion status.

**Test categories (7 categories, ~30 types):**

| Category | Test prompts to write | Priority |
|----------|----------------------|----------|
| A. Employees | create, update, set role, employment details, delete | HIGH (Tier 1) |
| B. Customers & Products | create customer, create product, update | HIGH (Tier 1) |
| C. Invoicing | create invoice, payment, credit note | HIGH (Tier 1-2) |
| D. Travel Expenses | create, add costs, delete | MEDIUM (Tier 2) |
| E. Projects | create, link to customer | MEDIUM (Tier 1-2) |
| F. Corrections | delete entries, reverse invoice | MEDIUM (Tier 2) |
| G. Departments & Modules | create dept, enable module | HIGH (Tier 1) |

**Expected output:** Test results matrix showing pass/fail per task type, with failure analysis.

**Commit after:** Yes, commit test results to MEMORY.md + any prompt fixes found.

## Phase 2: Fix Failures from Phase 1

**Goal:** Update system prompt to handle all failing task types. Focus on Tier 1 tasks first (highest priority, available now).

**Method:** For each failure, identify the root cause (missing API endpoint in reference, wrong field names, missing prerequisites) and add targeted guidance to the system prompt.

**Boris per fix:** EXPLORE(failure analysis) -> PLAN(what to change) -> CODE(edit prompt) -> REVIEW(code-reviewer) -> VALIDATE(build-validator + retest) -> COMMIT

**Commit after:** Yes, one commit per category of fixes.

## Phase 3: Deploy and Verify Fixes

**Goal:** Deploy updated bot, retest failed task types, confirm fixes work.

**Method:** Redeploy to Cloud Run, rerun failing test prompts, verify passing.

**Commit after:** Yes, with test results.

## Phase 4: Efficiency Optimization (after Phase 3)

**Goal:** For task types that score perfectly, reduce API calls and eliminate 4xx errors.

**Method:** Analyze logs for unnecessary GET calls, redundant lookups, and wasted API calls. Update system prompt to be more directive about minimum-call strategies.

**Commit after:** Yes.

## Phase 5: Tier 2 Preparation (Friday)

**Goal:** When Tier 2 opens, handle multi-step workflows: invoicing with payment, credit notes, travel expenses, employment details.

**Method:** Expand API reference and system prompt with multi-step workflow guidance.

## Phase 6: Tier 3 Preparation (Saturday)

**Goal:** Handle complex scenarios: bank reconciliation, ledger corrections, year-end closing.

## Sandbox Credentials (for local testing)

- Base URL: https://kkpqfuj-amager.tripletex.dev/v2
- Session token: from .env file
- Note: sandbox is PERSISTENT (data accumulates), unlike competition (fresh each time)
