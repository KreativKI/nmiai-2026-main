---
priority: HIGH
from: overseer
timestamp: 2026-03-20 05:05 CET
self-destruct: delete when JC wakes up and confirms new orders
---

## Standing Orders: JC Is Sleeping

Dashboard, CORS fix, ML ground truth viewer, branding all done. Good work.

### FIRST: Update Your plan.md

Before doing any work, update your plan.md with a phased work plan. Use the phases below as a starting point but adapt based on what makes sense.

**Structure your plan.md like this:**
```
## Current Phase: [N]
## Phases
### Phase 1: [name] — Status: [done/active/pending]
- Tasks...
- Commit: "Phase 1: [description]"

### Phase 2: [name] — Status: [pending]
...
```

Update "Current Phase" as you progress. If context resets, the next session reads plan.md and continues.

**Commit plan.md first:** `git add plan.md && git commit -m "Updated phased plan for sleep mode" && git push origin agent-ops`

### Suggested Phases (adapt as needed)

**Phase 1:** CV submission viewer. Inspect ZIPs: run.py contents, model sizes, blocked import check.
**Phase 2:** Pre-submission validation tools. One-click validate for CV/NLP/ML.
**Phase 3:** Leaderboard tracking. Scrape top 10, store with timestamps, show progression chart.
**Phase 4:** Auto-refresh and polish. 5-min refresh cycle, Playwright-validate all views.
**Phase 5:** Write sleep report to intelligence/for-overseer/ops-sleep-report.md.

After Phase 5: keep polishing.

### Key Rules
- Do NOT touch solution code in agent-cv/, agent-ml/, agent-nlp/
- Do NOT make any competition submissions
- Do NOT automate platform UI clicks
- Commit after EVERY phase
- Update status.json after every phase
- Use kreativki-frontend skill for all UI work
- Check intelligence/for-ops-agent/ at :15 and :45 past each hour
