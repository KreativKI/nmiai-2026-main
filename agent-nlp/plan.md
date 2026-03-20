# Tripletex AI Accounting Agent — Plan

**Track:** NLP | **Task:** AI Accounting Agent | **Weight:** 33.33%
**Last updated:** 2026-03-19 22:55 CET

## The Problem
Build an HTTPS endpoint that receives accounting task prompts (7 languages, some with PDF/image attachments), interprets them, and executes the correct Tripletex API calls. 30 task types, 56 variants each. Scored field-by-field + efficiency bonus on perfect scores.

## What's new in 2026 that matters here

### Tool-use / Function-calling Models
- Claude 4, GPT-5, Gemini 2.5 all have native function-calling
- **Don't build a prompt parser + API mapper separately** — give the LLM the Tripletex API schema as tools and let it call them directly
- This is an agentic tool-use problem, not a traditional NLP pipeline

### MCP Integration
- Competition provides MCP docs server: `claude mcp add --transport http nmiai https://mcp-docs.ainm.no/mcp`
- The agent can query docs in real-time during development

## Approach A (Primary): LLM Agent with Tripletex Tools

1. **Architecture:** FastAPI endpoint → LLM (Gemini 2.5 Flash or Claude Haiku for speed/cost) → Tripletex API calls
2. **Tool definitions:** Map Tripletex API endpoints as function-calling tools with typed parameters
3. **Prompt:** System prompt with accounting context + Norwegian conventions. User message = task prompt.
4. **Attachments:** Use multimodal LLM (Gemini) for PDF/image processing — extract data directly
5. **Verification loop:** After executing, query back created resources to verify correctness
6. **Deploy:** GCP Cloud Run (free with competition account) or ngrok tunnel
7. **Time:** 4-6 hours
8. **Expected:** 3.0-5.0 (out of 6.0)

## Approach B (Fallback): Keyword Router + Hardcoded Flows

1. Detect task type from keywords (create employee, create invoice, etc.)
2. Extract field values with regex + LLM
3. Execute hardcoded API call sequence per task type
4. Cover top 10 task types in Norwegian + English
5. **Time:** 2-3 hours
6. **Expected:** 1.5-2.5

## Approach C (Baseline — SHIP FIRST): Top 5 Tasks Only

1. Implement only: Create Employee, Create Customer, Create Product, Create Invoice, Delete Employee
2. Simple pattern matching
3. Norwegian + English only
4. **Time:** 1-2 hours
5. **Expected:** 0.5-1.5

## Tier Strategy
- **Tier 1 (now):** Foundation tasks — get these perfect for guaranteed base score
- **Tier 2 (Friday):** Multi-step workflows — expand agent capabilities
- **Tier 3 (Saturday):** Complex scenarios — push for high multipliers (up to 6.0)

## Efficiency Optimization (applies ONLY to perfect scores)
- Minimize API calls — plan before calling
- Zero 4xx errors — validate inputs before sending
- Don't fetch entities you just created (you have the ID from POST response)
- Efficiency benchmarks recalculated every 12h — the bar rises as teams improve

## Norwegian Accounting Gotchas
- Comma as decimal separator (1.000,50 = 1000.50)
- Date format: DD.MM.YYYY
- VAT rates: 25% (standard), 15% (food), 12% (transport), 0% (exempt)
- Nynorsk ≠ Bokmål — different vocabularies for same concepts

## Deployment
- **Option 1:** GCP Cloud Run (recommended — free, HTTPS, auto-scaling)
- **Option 2:** FastAPI + ngrok (faster setup, less reliable)
- **Option 3:** FastAPI + Cloudflare Tunnel (middle ground)

## Submission Strategy
- Rate limit: 5 per task per day (verified), 2 (unverified)
- Each submission gets a RANDOM task type — can't control which one
- Weighted toward tasks attempted less often
- **Strategy:** Submit frequently to cover all 30 task types over time
