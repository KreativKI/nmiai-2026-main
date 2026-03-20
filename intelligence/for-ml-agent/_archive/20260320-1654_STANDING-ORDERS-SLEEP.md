---
priority: HIGH
from: overseer
timestamp: 2026-03-20 05:05 CET
self-destruct: delete when JC wakes up and confirms new orders
---

## Standing Orders: JC Is Sleeping

You have FULL AUTONOMY to submit every round. Missing rounds = 0 points forever.

### FIRST: Update Your plan.md

Before doing any work, update your plan.md with a phased work plan for each round. Use the phases below as a starting point but adapt based on what you learn from each round.

**Structure your plan.md like this:**
```
## Current Phase: [N] (Round [R])
## Round [R] Phases
### Phase 1: [name] — Status: [done/active/pending]
- Tasks...
- Commit: "Round R Phase 1: [description]"

### Phase 2: [name] — Status: [pending]
...
```

Update "Current Phase" as you progress. If context resets, the next session reads plan.md and continues.

**Commit plan.md first:** `git add plan.md && git commit -m "Updated phased plan for sleep mode" && git push origin agent-ml`

### Suggested Per-Round Phases (adapt as needed)

**Phase 1:** Detect round open. Note round number, weight, close time.
**Phase 2:** Execute observation strategy (50 queries across 5 seeds).
**Phase 3:** Build predictions. Floor 0.01, renormalize, validate.
**Phase 4:** Submit all 5 seeds. Log IDs.
**Phase 5:** Analyze previous round scores. Identify error sources.
**Phase 6:** Experiment between rounds (spatial modeling, Gaussian processes, parameter inference).
**Phase 7:** Update status.json and write to intelligence/for-overseer/ if running >2h.

After Phase 7: loop back to Phase 1.

### Key Rules
- ALWAYS submit every round
- ALWAYS floor at 0.01 and renormalize
- ALWAYS submit all 5 seeds
- Commit after EVERY phase
- Check intelligence/for-ml-agent/ at :00 and :30 past each hour
