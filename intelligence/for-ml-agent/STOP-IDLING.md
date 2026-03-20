---
priority: HIGH
from: overseer
timestamp: 2026-03-20 05:20 CET
self-destruct: after reading and updating plan.md, delete
---

## Stop Idle Monitoring. Do Productive Work Between Rounds.

Polling every 60s for a round that opens every ~3 hours is wasted context. Instead:

### Between Rounds, Work On:
1. **Analyze all ground truth data** from completed rounds. Build detailed transition matrices per terrain type, per neighborhood configuration.
2. **Build a better model.** You have ground truth from rounds 1-4. Use it. Train a proper spatial model that accounts for neighboring cell influence.
3. **Optimize query strategy.** Simulate: given your current model, which 50 queries would reduce KL the most? Write an optimization script.
4. **Research.** Read the competition docs with `mcp__nmiai__search_docs` for any scoring details you missed (you already found the 3x multiplier and best-round scoring, there may be more).
5. **Score formula insight:** score = 100 * exp(-3 * KL). Small KL improvements = big score jumps. Focus on getting KL from 0.3 to 0.15 (score jumps from 40 to 63).

### How to Check for Rounds Without Burning Context
Don't poll every 60s. Instead:
- Check once every 15-20 minutes with a single API call
- Spend the rest of the time on productive work above
- Commit after each productive phase

Update your plan.md with this. The round will come. Be ready with a better model when it does.
