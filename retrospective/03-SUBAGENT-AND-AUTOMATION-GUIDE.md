# Subagent Usage & Automation — Lessons from NM i AI 2026

---

## Subagent Mistakes We Made

### 1. Wrong agent type names
The agent type is `code-simplifier:code-simplifier` (plugin-namespaced), not `code-simplifier`. Every agent crashed until this was fixed.

**Rule:** Always use the full namespaced name. Check with `claude mcp list` or look at the error message's "Available agents" list.

### 2. Bundled subagent (boris-workflow)
Created a custom `boris-workflow` agent that ran review+simplify+validate in one session. This defeated the entire purpose of Boris: fresh context per step means the reviewer isn't biased by the coder's thinking.

**Rule:** Never bundle sequential quality gates into one agent. Each step needs its own fresh session.

### 3. Parallel agent launches
ML agent launched reviewer, simplifier, and validator simultaneously. The simplifier can't apply the reviewer's fixes if they're running at the same time.

**Rule:** For dependent steps, ONE agent call per message. The `/boris` command now enforces this.

### 4. Agents calling agents they shouldn't
Butler (ops) tried to run NLP submissions. Each track agent owns its own submission pipeline.

**Rule:** Agent scope must be explicit in CLAUDE.md. "You NEVER do X" is clearer than "your role is Y."

---

## Available Subagent Types (Correct Names)

| Name | Plugin | Purpose |
|------|--------|---------|
| `feature-dev:code-explorer` | Anthropic official | Deep codebase analysis |
| `feature-dev:code-reviewer` | Anthropic official | Bug/security/quality review |
| `feature-dev:code-architect` | Anthropic official | Architecture design |
| `code-simplifier:code-simplifier` | Anthropic official | Simplify/refine code |
| `build-validator` | Local (~/.claude/agents/) | Build/test validation |
| `pr-review-toolkit:code-reviewer` | Anthropic official | PR-focused review |
| `pr-review-toolkit:silent-failure-hunter` | Anthropic official | Find silent error swallowing |
| `Explore` | Built-in | Quick codebase search |
| `Plan` | Built-in | Implementation planning |
| `general-purpose` | Built-in | Generic multi-step tasks |

---

## When to Use Which Subagent

### Use `feature-dev:code-explorer` when:
- Starting work on unfamiliar code
- Need to understand architecture before making changes
- Mapping dependencies for a feature

### Use `feature-dev:code-reviewer` when:
- Code is written and needs quality check
- After any bug fix (did the fix introduce new bugs?)
- Before submission/deployment

### Use `code-simplifier:code-simplifier` when:
- After code review fixes are applied
- Code works but is messy/verbose
- **Caveat:** Has TypeScript bias. For Python, results may suggest wrong patterns.

### Use `build-validator` when:
- After simplification, before commit
- Need to verify nothing broke
- **Caveat:** Assumes npm. For Python projects, validation may not cover pytest/ruff.

### Use `Explore` (built-in) when:
- Quick file/pattern search
- Need to find something fast without deep analysis
- Faster than `feature-dev:code-explorer` but less thorough

---

## Automation That Worked

### A. Intelligence folder system
File-based async inbox/outbox. Agents check `intelligence/for-{agent}-agent/` on session startup. Overseer drops orders, agents drop status reports.

**Why it worked:** Decoupled communication from session timing. An agent can leave a message at 02:00 that gets read at 08:00.

**Kitchen metaphor:** Like a message board in the kitchen. The morning shift reads what the night shift left behind.

### B. Pre-submission validation pipeline
`cv_pipeline.sh` chains: unzip -> validate structure -> check imports -> run Docker -> score predictions -> verdict.

**Why it worked:** Prevented bad submissions from burning rate-limited slots. Every step can fail fast.

### C. QC verification script (NLP)
17 tests against live sandbox. Catches field-level errors, not just HTTP 200.

**Why it worked:** Tests what the competition actually scores (correct field values), not what developers usually test (did the API respond).

---

## Automation That Failed

### A. Autonomous submission without throttle
ML overnight_v4.py submitted every round automatically. Good in theory, but when alpha was wrong (R23), there was no human gate to catch it.

**Fix for 2027:** Autonomous submissions within budget, but flag anomalies. If score drops >10% from previous round, pause and alert.

### B. NLP bulk submissions
Burned 249/300 submissions in one session. No pacing, no analysis between batches.

**Fix for 2027:** Submit in batches of 20. Analyze results. Adjust. Then next batch. Never burn more than 50% of daily budget in one session.

### C. Stale monitoring
Overseer plan.md was 18h stale. No cron job or reminder to refresh.

**Fix for 2027:** Add `/loop 4h /status-check` to overseer session. Auto-refresh every 4 hours.

---

## Automation We Should Have Built

### A. Score anomaly detector
If any submission scores >10% worse than previous best, immediately:
1. Pause auto-submissions
2. Alert JC
3. Log the diff between current and previous config
4. Don't deploy until investigated

### B. Rate limit tracker
Visual budget meter showing: "You've used 145/180 NLP submissions today. 35 remaining. At current pace, you'll run out at 14:30."

### C. Agent heartbeat monitor
If an agent hasn't committed in >3 hours, alert overseer. ML went silent for 7+ hours and nobody noticed until manual check.

### D. Pre-competition config validator
Before competition starts, verify:
- All agent CLAUDE.md files have correct deadlines
- All rules.md files are populated
- All rate limits match platform (not just docs)
- All API credentials work
- Boris workflow instructions are unambiguous

---

## The /boris Command

Created and tested during the competition. Lives at `~/.claude/commands/boris.md`.

Usage: `/boris fix the login timeout bug`

Enforces the full pipeline:
1. EXPLORE (feature-dev:code-explorer)
2. PLAN (user approval gate)
3. CODE (Edit/Write)
4. REVIEW (feature-dev:code-reviewer)
5. SIMPLIFY (code-simplifier:code-simplifier)
6. VALIDATE (build-validator)
7. COMMIT

Key enforcement: "ONE Agent call per message" prevents parallel execution.

**Limitation for Python projects:** Steps 5 and 6 have TypeScript/npm bias. Consider creating Python-specific variants:
- `python-simplifier` (uses ruff, follows PEP 8)
- `python-validator` (runs pytest, mypy, ruff check)
