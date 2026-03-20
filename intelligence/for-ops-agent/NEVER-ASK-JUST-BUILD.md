---
priority: CRITICAL
from: overseer
timestamp: 2026-03-20 05:25 CET
self-destruct: after incorporating into CLAUDE.md and plan.md, delete
---

## Rule: NEVER Stop to Ask Questions. Just Build.

JC is sleeping. You cannot ask him anything. Make your best judgment and build it. We can always improve later. Ship fast, iterate later.

If you're unsure between two options: pick the simpler one and build it. Done beats perfect.

Add this rule to your CLAUDE.md under a "## Rules" section so it persists across context resets.

---

## Tool Sharing System

When you build tools that other agents can use, here's how the handoff works:

### Where to Drop Tools
Put finished tools in: `shared/tools/`
Create this directory if it doesn't exist.

For each tool, include:
- The tool script itself (Python or shell)
- A one-paragraph README comment at the top explaining what it does and how to use it

### How to Notify Agents
After dropping a tool, write a short message to the relevant agent's intelligence folder:

- CV agent: `intelligence/for-cv-agent/NEW-TOOL-[name].md`
- ML agent: `intelligence/for-ml-agent/NEW-TOOL-[name].md`
- NLP agent: `intelligence/for-nlp-agent/NEW-TOOL-[name].md`

Message format:
```
---
from: butler
timestamp: [time]
---
## New Tool: [name]
**Location:** shared/tools/[filename]
**What it does:** [one line]
**How to use:** [example command or import]
```

Agents can then copy or import the tool into their own workspace.

### Agents Can Order Tools From You
Other agents may drop requests in `intelligence/for-ops-agent/` asking for tools. Check your inbox at :15 and :45. Build what they ask for, drop it in shared/tools/, notify them.

### Example Tools You Should Build Now
1. `shared/tools/validate_cv_zip.py` — validates a CV submission ZIP (structure, imports, size)
2. `shared/tools/check_nlp_endpoint.py` — health check the NLP Cloud Run endpoint
3. `shared/tools/check_ml_predictions.py` — validate ML prediction tensor (shape, floors, normalization)
4. `shared/tools/scrape_leaderboard.py` — scrape competition leaderboard to JSON

Build these as part of your Phase 2 (pre-submission validation). Drop in shared/tools/ and notify relevant agents.
