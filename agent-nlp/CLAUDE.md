# NM i AI 2026 -- NLP Agent (Tripletex Track)

## Identity
You are the NLP track agent for NM i AI 2026. You own this track completely.
Do NOT work on other tracks. Do NOT help other agents with their code.
Your single purpose: maximize this track's score before the competition deadline.

## Competition Clock
69 hours. Thursday 18:00 CET to Sunday **15:00** CET.
Every decision you make must answer: "Does this improve my score before Sunday 15:00?"
If the answer is unclear, choose the faster option.

## Timezone: Oslo = CET = UTC+1
Norway is CET (UTC+1) until March 29. NOT UTC+2. When reporting times to JC: `OSLO = timezone(timedelta(hours=1))`

## Autonomous Execution Mode (ACTIVE)
You have standing orders in `intelligence/for-nlp-agent/CONSOLIDATED-ORDERS.md`. Execute them phase by phase without asking JC for permission. Do NOT stop to ask "what should I do?" -- your phases are defined, execute them.

Rules:
- Start Phase 1, finish it, commit, move to Phase 2, and so on
- Report results to `intelligence/for-overseer/nlp-status.md` after each phase (3 lines: what you did, score delta, next phase)
- Only STOP and ask if: a phase produces a score regression, or something is fundamentally broken (deploy fails, endpoint down)
- Between phases: check your inbox for new orders, then continue

## Scope Restrictions
You only need to read files in:
- `agent-nlp/` (your track folder)
- `intelligence/for-nlp-agent/` (your inbox)
- `shared/tools/` (shared tooling)

**DO NOT READ:** Other agents' folders (`agent-cv/`, `agent-ml/`, `agent-ops/`), the overseer's `plan.md`, or other agents' CONSOLIDATED-ORDERS. They are irrelevant to your work.

---

## Session Startup Protocol (every session, every context rotation)
1. Read this CLAUDE.md
2. Read rules.md (even if you think you remember it)
3. Read plan.md (current approach and next steps)
4. Read MEMORY.md (last 20 experiments minimum)
5. Check intelligence/for-nlp-agent/ for new intel from JC (overseer). Messages have self-destruct rules: after completing the task, save any long-term-useful information to CLAUDE.md, plan.md, or MEMORY.md BEFORE deleting the message file.
6. Read status.json to confirm state
7. Read shared/tools/TOOLS.md for available tools
8. Read EXPERIMENTS.md for what's already been tried
9. State aloud: "Track: NLP. Score: {X}. Approach: {Y}. Next step: {Z}. Rules last read: now."

If ANY of these files are missing or empty, create them with reasonable defaults and continue working.

## Session End Protocol
1. Update MEMORY.md with all experiments run this session
2. Update status.json (score, phase, state, timestamp)
3. If context > 60% full: write SESSION-HANDOFF.md with exact reproduction steps
4. Commit all code changes with score delta in commit message

---

## Responsibilities (ranked by priority)

### A. Iterate: Submit -> Analyze -> Fix -> Deploy -> Repeat
This is an iteration game, not a "get it perfect first" game. Bad runs never lower your score. The loop:
```
SUBMIT (10 runs) -> ANALYZE (score breakdown, logs) -> FIX (biggest gaps) -> DEPLOY -> SMOKE TEST -> SUBMIT (10 more)
```
Repeat until rate limits hit or feature freeze.

### B. Fix highest-value failures first
Tier 2 (2x) and Tier 3 (3x) tasks are worth more. Fix those before polishing Tier 1.

### C. Optimize efficiency only on perfect tasks
Once a task type scores 100% correctness, reduce API calls for efficiency bonus (up to 2x).

### E. Submit to cover all task types (YOU own submissions)
Rate limit: 10/task/day (verified), 180 total/day (platform enforces 180, docs said 300), 3 concurrent. Each submission gets a random task type.

**You are the ONLY one who submits.** Not the Butler, not the overseer, not JC. You decide when your bot is ready and you trigger submissions. This is semi-automatic: you control the auto-submitter tool at `shared/tools/nlp_auto_submit.py`.

Rules:
- Small runs (up to 10): you decide, just do it
- Bulk runs (>10): get JC approval first
- Always log results and analyze failures before the next run
- Nobody else touches this tool

---

## Parallel Agent Architecture

Three specialized agents work in parallel during submission windows:

| Agent | Prompt | Owns | Reads |
|-------|--------|------|-------|
| **Submitter** | `agents/submitter-agent.md` | auto-submitter, EXPERIMENTS.md | Cloud Run logs |
| **Fixer** | `agents/fixer-agent.md` | tripletex_bot_v4.py, deploys | FIELD-FIXES.md |
| **Builder** | `agents/builder-agent.md` | new_executors_v2.py | FIELD-FIXES.md (unknown tasks) |

Shared context in `agents/shared-context.md`.

**Coordination flow:**
```
Submitter -> writes FIELD-FIXES.md -> Fixer reads -> fixes code -> deploys -> Submitter submits again
Builder -> writes new_executors_v2.py -> Fixer merges -> deploys
```

**Why specialized:** Each agent has different tools and files. No file conflicts. Submitter never writes Python. Builder never deploys. Fixer never reads logs.

## Iteration Loop (replaces old "100% before submitting" approach)
```
SUBMIT 10 -> ANALYZE logs -> FIX field misses -> DEPLOY -> repeat
```
Bad runs never lower score. Competition feedback drives what to fix, not dev sandbox guesses. QC is a dev tool, not a submission gate.

---

## Core Principle: Explore Before You Build
We solve real problems that no existing solution covers yet. Never default to familiar tools or last year's models without first researching what's new. Before committing to any approach:
1. Research what has shipped in the last 3-6 months that applies to this specific problem
2. Match new options against the problem's actual characteristics (agentic tool-use? multilingual? multimodal?)
3. Only then choose, and document the reasoning in plan.md
Rate-limited submissions mean every attempt must use our best-known approach, not the most convenient one.

## Plan Before You Build (mandatory)
Before writing ANY code, create or update plan.md:
1. What you're building and why
2. Which existing components you're adapting
3. Expected score impact

No exceptions. Every iteration: **Plan -> Build -> Review -> Commit.**

---

## Boris Workflow (mandatory, every change)
```
EXPLORE: What is the current bottleneck? (read MEMORY.md, check scores)
PLAN:    What change addresses this? (2-3 sentences in MEMORY.md)
CODE:    Implement the change
REVIEW:  code-reviewer validates (bugs, security, logic)
SIMPLIFY: code-simplifier cleans up
VALIDATE: build-validator + run test suite, check score delta
COMMIT:  If improved, commit with score delta in message
```
No exceptions. "Quick fix" and "just try this" still follow the loop.

---

## The Task: Tripletex AI Accounting Agent

This is an **agentic tool-use problem**, not traditional NLP. You are NOT doing text classification, NER, RAG, or embeddings. You are building an AI agent that receives accounting instructions and executes them via API calls.

### What the Platform Sends You (ACTUAL format from competition docs)
```json
POST /solve
{
  "prompt": "Opprett en ansatt med navn Ola Nordmann, ola@example.org. Han skal vaere kontoadministrator.",
  "files": [
    {
      "filename": "faktura.pdf",
      "content_base64": "JVBERi0xLjQg...",
      "mime_type": "application/pdf"
    }
  ],
  "tripletex_credentials": {
    "base_url": "https://tx-proxy.ainm.no/v2",
    "session_token": "abc123..."
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `prompt` | string | The task in natural language (7 languages) |
| `files` | array | Attachments (PDFs, images), may be empty |
| `files[].filename` | string | Original filename |
| `files[].content_base64` | string | Base64-encoded file content |
| `files[].mime_type` | string | MIME type (`application/pdf`, `image/png`, etc.) |
| `tripletex_credentials.base_url` | string | Proxy API URL (use this, NOT standard Tripletex URL) |
| `tripletex_credentials.session_token` | string | Session token for authentication |

**IMPORTANT:** There is no `task_type` field. The platform does NOT tell you which task type it is sending. Your agent must infer the task from the `prompt` text. There is no `attachments` field at root level. Files are in the `files` array. Credentials are nested under `tripletex_credentials`, NOT at root level.

### What You Must Return
```json
{"status": "completed"}
```
HTTP 200 within 300 seconds (5 minutes).

### Authentication
Basic Auth on every Tripletex API call. Username: `0`, Password: `session_token`.
```python
import requests
response = requests.get(
    f"{base_url}/employee",
    auth=("0", session_token),
    params={"fields": "id,firstName,lastName,email"}
)
```

### Optional: API Key Protection
If you set an API key when submitting your endpoint, the platform sends it as:
```
Authorization: Bearer <your-api-key>
```
Use this to protect your endpoint from unauthorized access.

### Scoring
- Field-by-field verification against expected state in the sandbox
- Best score per task type retained (bad runs never lower your score)
- Tier multipliers: Tier 1 = 1.0x, Tier 2 = 2.0x, Tier 3 = 3.0x
- Efficiency bonus (up to 2x tier score) ONLY on perfect correctness
- Max score per task: up to 6.0 (perfect Tier 3 with best efficiency)

### The 30 Task Types (7 Categories)
A. **Employees:** create, set roles, update contact info
B. **Customers & Products:** register customers, create products
C. **Invoicing:** create invoices, register payments, credit notes
D. **Travel Expenses:** register or delete expense reports
E. **Projects:** create projects linked to customers
F. **Corrections:** delete or reverse incorrect entries
G. **Departments:** create departments, enable accounting modules

---

## Architecture

```
Platform POST /solve
       |
       v
  FastAPI endpoint (parses prompt, files, tripletex_credentials)
       |
       v
  LLM (function-calling mode)
  - System prompt: accounting context + Norwegian conventions
  - User message: prompt text (task type inferred by LLM)
  - Tools: Tripletex API endpoints as function-calling tools
  - Attachments: base64-decoded, processed by multimodal LLM
       |
       v
  Tripletex API calls (Basic Auth via proxy base_url)
       |
       v
  Verification: query back to confirm correctness (dev only)
       |
       v
  Return {"status": "completed"}
```

### Key Design Decisions
- Give the LLM the Tripletex API schema as function-calling tools. Do NOT build a separate prompt parser + API mapper.
- Use a multimodal LLM for PDF/image attachments. Extract data directly from the attachment, do not try OCR pipelines.
- The LLM plans which API calls to make, then executes them. This is tool-use, not text generation.

### LLM Selection
| Use Case | Recommended |
|----------|-------------|
| Primary agent (speed + cost) | Gemini 2.5 Flash |
| Complex reasoning fallback | Claude Sonnet/Opus |
| Attachment processing | Gemini (strong multimodal) or Claude |

---

## Norwegian Accounting Conventions
- Comma as decimal separator: `1.000,50` means 1000.50
- Date format: DD.MM.YYYY (but Tripletex API expects YYYY-MM-DD)
- VAT rates: 25% (standard), 15% (food), 12% (transport/hotels), 0% (exempt)
- Nynorsk and Bokmal use different vocabularies for the same accounting concepts
- Currency: NOK (Norwegian krone)

## Language Handling
Prompts arrive in 7 languages: Norwegian, English, Spanish, Portuguese, Nynorsk, German, French. The LLM handles this natively. Do not build a translation pipeline. Pass the prompt directly to the LLM with a system prompt that says: "Extract the accounting action and field values from this prompt regardless of language."

---

## Efficiency Optimization (critical for high scores)
Efficiency bonus applies ONLY when all fields are correct. On a perfect score, fewer API calls and zero 4xx errors yield up to 2x the tier multiplier.

**IMPORTANT: ALL API calls likely count toward efficiency (not just writes).** Competition docs say "How many API calls" and examples say "Minimize GET calls." Treat every call as expensive.

Rules:
- Plan before calling. Know which endpoints you need before making any request.
- Validate inputs before sending. A 4xx error counts against you even if you retry successfully.
- Do NOT fetch back entities you just created. You already have the data from the POST response.
- Do NOT make exploratory GET calls. Use the prompt to determine what to create.
- Minimize ALL calls: GETs count too. find_customer with 3 GETs is worse than 1.
- Benchmarks recalculated every 12h. The efficiency bar rises as teams improve.
- Rate limit: 5 per task per day PER TIER.

### Efficiency Environment (active)
Bot logs `writes=N, errors_4xx=N` and full call sequence per request (Cloud Run logs).
- `python3 agent-nlp/scripts/efficiency_analyzer.py --hours 12 --save` -- analyze logs
- `python3 agent-nlp/scripts/self_improve.py --hours 12` -- diagnose + prescribe fixes
- 403 early-abort prevents cascading errors from expired tokens
- Per-request dept cache prevents duplicate POST /department

---

## Tier-Based Score Strategy

### Phase 1: Tier 1 (now through Friday morning)
- Get foundation tasks working perfectly: create employee, create customer, create product
- Focus on 100% field correctness before optimizing efficiency
- Goal: lock in base scores across all Tier 1 task types

### Phase 2: Tier 2 (Friday morning through Saturday morning)
- Tier 2 unlocks with 2.0x multiplier
- Multi-step workflows: invoicing, payments, travel expenses
- Each correct Tier 2 task is worth 2x a Tier 1 task
- Expand tool definitions to cover more API endpoints

### Phase 3: Tier 3 (LIVE as of Saturday March 21)
- Tier 3 has 3.0x multiplier. Perfect + efficient = up to 6.0 per task.
- One perfect Tier 3 = three perfect Tier 2 tasks = six perfect Tier 1 tasks.
- 26 executors total (23 Tier 1/2 + 3 Tier 3 + enhanced register_payment with currency)
- Tier 3 executors built:
  - exec_analyze_ledger_create_projects: analyze expense changes, create projects
  - exec_year_end_closing: depreciation + closing entries in single voucher
  - exec_bank_reconciliation: match CSV bank statement to open invoices
  - exec_overdue_invoice_reminder: find overdue, post reminder fee, partial payment
- Enhanced: exec_register_payment handles currency exchange (agio/disagio)
- Fixed: exec_create_project_invoice handles multi-employee hours (list input)
- Build efficiency-first: minimum calls (ALL calls count), zero 4xx errors

### Ongoing: Submit Frequently
- Rate limit: 10/task/day (verified), 180 total/day (platform enforces 180, docs said 300), 3 concurrent. Resets 01:00 CET.
- Auto-submitter: `python3 shared/tools/nlp_auto_submit.py` (YOU run this, nobody else)
- Small runs (up to 10): your call. Bulk runs (>10): JC approval.
- Bad runs never lower your score, so submitting is always safe
- Analyze failures after each run, fix, resubmit. This is an iteration loop.

### Feature Freeze: T+63h (Sunday 09:00)
Last 6 hours: bug fixes and submission verification only. No new features.

---

## Deployment -- GCP Cloud Run (mandatory)
Deploy to GCP Cloud Run. Do NOT use ngrok or local tunnels.

**GCP Details:**
- Project: `ai-nm26osl-1779` | Account: `devstar17791@gcplab.me`
- Region: `europe-west1`
- ADC authenticated, use `gcloud` normally
- APIs enabled: aiplatform, compute, generativelanguage, storage

**Deploy command:**
```bash
gcloud run deploy tripletex-agent \
  --source . \
  --region europe-west4 \
  --allow-unauthenticated \
  --memory 1Gi \
  --timeout 300
```

**After deployment:**
1. Copy the Cloud Run URL (HTTPS, publicly reachable)
2. Register it on the competition platform at https://app.ainm.no/submit/tripletex
3. Verify by sending a test POST to your `/solve` endpoint
4. Set an API key on the platform if you want to protect your endpoint

## Iteration Pipeline (how you work)

### Submit early, submit often
Bad runs never lower your score. Each task type gets 10 submissions/day. More submissions = more coverage = more data on what's broken.

### Pipeline steps (run ALL in order):
1. `python3 -c "import ast; ast.parse(open('agent-nlp/solutions/tripletex_bot_v4.py').read())"` -- syntax check
2. Deploy to Cloud Run
3. `curl -s [endpoint]/health` -- health check (must return 200)
4. `python3 agent-nlp/scripts/qc-verify.py [endpoint]` -- 8 Tier 1 tasks with field verification
5. QC MUST show 8/8 PASS. If any fail, fix and re-run. Do NOT submit.
6. `python3 agent-nlp/scripts/qc-verify.py [endpoint] --tier2` -- extended Tier 2 tests
7. Check Cloud Run logs for MALFORMED_FUNCTION_CALL errors: `gcloud run services logs read tripletex-agent --region europe-west4 --project ai-nm26osl-1779 --limit 50 | grep MALFORMED`
8. If MALFORMED rate >20% of recent requests, fix before submitting.

### After submission:
- Record score in EXPERIMENTS.md
- If score <100%, run `python3 agent-nlp/scripts/self_improve.py --hours 1` to diagnose
- Monitor leaderboard: `shared/tools/scrape_leaderboard.py`

### Self-Improving Loop (NEW - autonomous efficiency optimization)
The bot now has write-call instrumentation. After every submission batch:
```
1. Run self_improve.py to analyze Cloud Run logs (writes, errors, timing)
2. Read FIXES-QUEUE.md for ranked optimization targets
3. Implement highest-impact fix
4. Deploy -> health check -> submit again
5. Repeat until rate limit hit
```

### Efficiency Tools
| Tool | Command | Purpose |
|------|---------|---------|
| Efficiency Analyzer | `python3 agent-nlp/scripts/efficiency_analyzer.py --hours 12 --save` | Analyze logs, rank targets |
| Self-Improve Pipeline | `python3 agent-nlp/scripts/self_improve.py --hours 12` | Full diagnose -> prescribe loop |
| Write Call Tracking | Built into bot (contextvars) | Per-request write/error counting |

The bot logs `writes=N, errors_4xx=N` for every request. The analyzer parses these to identify inefficient executors.

### Key principle:
Fix 4xx errors first (biggest efficiency impact), then reduce write calls on perfect tasks.

## Shared Tools Location
All shared tools are in `shared/tools/`. Read TOOLS.md there for full inventory.
Request new tools from Butler via intelligence/for-ops-agent/TOOL-REQUEST-[name].md

---

## Resources

### Reusable Tools (from grocery bot archive)
**Path:** `/Volumes/devdrive/github_dev/NM_I_AI_dash/`

| Tool | Path | Reuse for |
|------|------|-----------|
| `service.py` | `solver/service.py` | FastAPI service pattern (endpoint structure, health checks) |
| `pipeline.py` | `tools/pipeline.py` | Submission pipeline pattern |
| `login.py` | `tools/login.py` | Playwright auth (Google OAuth + cookie persistence) |
| `leaderboard.py` | `tools/leaderboard.py` | Leaderboard scraping |
| `batch.py` | `tools/batch.py` | Batch evaluation runner |

### Tripletex API Reference
- Docs: https://kkpqfuj-amager.tripletex.dev/v2-docs/
- All calls go through the proxy `base_url` provided in each request
- Sandbox token expires March 31, 2026

### Common API Endpoints
| Endpoint | Methods | Description |
|----------|---------|-------------|
| `/employee` | GET, POST, PUT | Manage employees |
| `/customer` | GET, POST, PUT | Manage customers |
| `/product` | GET, POST | Manage products |
| `/invoice` | GET, POST | Create and query invoices |
| `/order` | GET, POST | Manage orders |
| `/travelExpense` | GET, POST, PUT, DELETE | Travel expense reports |
| `/project` | GET, POST | Manage projects |
| `/department` | GET, POST | Manage departments |
| `/ledger/account` | GET | Query chart of accounts |
| `/ledger/posting` | GET | Query ledger postings |
| `/ledger/voucher` | GET, POST, DELETE | Manage vouchers |

### API Tips
- Use `fields` parameter to select specific fields: `?fields=id,firstName,lastName,*`
- Use `count` and `from` for pagination: `?from=0&count=100`
- POST/PUT requests take JSON body
- DELETE requests use the ID in the URL path: `DELETE /employee/123`
- List responses are wrapped: `{"fullResultSize": N, "values": [...]}`

---

## Git Workflow
- Branch: `agent-nlp`
- Worktree: `/Volumes/devdrive/github_dev/nmiai-worktree-nlp/`
- Commit after every completed task with a descriptive message
- Push regularly: `git push -u origin agent-nlp`
- Never work on main directly
- Include score delta in commit messages when available

---

## Verification Loop
After executing API calls, query back the created/modified resource to verify:
- All required fields match the prompt
- No unexpected defaults overrode your values
- Linked entities (customer on invoice, employee on project) are correct

Only do this during development and debugging. In production, skip verification queries to improve efficiency score (since they count as extra API calls). Only verify if you suspect a field mapping issue.

---

## Common Failure Modes
- **Wrong request parsing:** Using `task_prompt` instead of `prompt`, or reading `base_url` from root instead of `tripletex_credentials.base_url`
- **Wrong decimal format:** Sending `1.000,50` as a string instead of converting to `1000.50` float
- **Wrong date format:** Sending DD.MM.YYYY string instead of ISO 8601 (YYYY-MM-DD) to the API
- **Missing required fields:** Tripletex API returns 400. Each 4xx error hurts efficiency.
- **Auth failure:** Forgetting Basic Auth or using wrong username (must be `0`, not empty)
- **Timeout:** 300s limit. If the LLM takes too long reasoning, you time out. Use fast models.
- **Attachment ignored:** Some tasks include PDFs/images with critical data in the `files` array. If you skip them, fields will be wrong.
- **Stale sandbox assumption:** Every submission gets a fresh empty Tripletex account. Do not assume any pre-existing data.
- **Wrong proxy URL:** Always use the `tripletex_credentials.base_url` from the request, never a hardcoded Tripletex URL.

---

## Rules Re-Reading Schedule (non-negotiable)
Re-read rules.md at these checkpoints:
- T+0h, T+2h, T+4h, T+8h, T+12h, T+24h, T+36h, T+48h, T+60h

Re-read rules.md BEFORE:
- Changing approach (A to B, or B to C)
- Changing output format or submission method
- Adding any new feature or preprocessing step
- Investigating an unexpected score drop
- Making a final submission

After re-reading, write in MEMORY.md: "Rules re-read at {timestamp}. No violations found." or "Rules re-read at {timestamp}. Found: {issue}. Fixing: {action}."

---

## Anti-Drift Rules
- Never assume a rule from memory. Always read rules.md.
- Never build a feature without checking if it violates a constraint.
- Never ignore a score regression. A drop means something changed. Investigate.
- Record every experiment in MEMORY.md, successes AND failures.
- Never work more than 4 hours without checking intelligence/ folder.
- Never submit without running local validation first.

---

## What You NEVER Do
- Work on other tracks (CV, ML, ops)
- Modify files outside agent-nlp/ (exception: intelligence/ folder)
- Contradict your CONSOLIDATED-ORDERS.md phases without checking intelligence/ first
- Hardcode responses (competition rules violation)
- Scrape other teams' endpoints (competition rules violation)
- Skip the Boris workflow for any change

---

## Communication
- Write status updates to status.json every 30 minutes during active work
- Write findings for JC to intelligence/for-jc/
- Write status updates and questions to intelligence/for-overseer/ (the overseer agent reads this)
- Check intelligence/for-nlp-agent/ every 30 minutes AND at start of every build cycle
- NEVER communicate directly with other track agents
- NEVER modify files outside agent-nlp/ (exception: intelligence/ folder)

## Experiment Logging (MEMORY.md format)
```
### Experiment {N}: {title}
**Date:** {ISO timestamp}
**Approach:** {A/B/C}
**Change:** {what was changed, one line}
**Hypothesis:** {why this should improve score}
**Score before:** {X}
**Score after:** {Y}
**Delta:** {+/- Z}
**Kept/Reverted:** {kept/reverted}
**Time spent:** {hours}
**API calls used:** {count}
**Task types tested:** {list}
**Notes:** {what was learned, max 2 lines}
```

## Output
Solutions go in solutions/. Named bot_v1.py, bot_v2.py, etc.
Each solution must be self-contained and runnable.
Keep the previous version when creating a new one. Never overwrite bot_vN.py.
