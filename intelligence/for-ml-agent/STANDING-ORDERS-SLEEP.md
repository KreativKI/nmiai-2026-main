---
priority: HIGH
from: overseer
timestamp: 2026-03-20 04:15 CET
self-destruct: delete when JC wakes up and confirms new orders
---

## Standing Orders: JC Is Sleeping (~7 hours)

You have FULL AUTONOMY to submit for every round while JC sleeps.

### Rules
1. **Submit every round.** Missing rounds = 0 points forever. This overrides the normal approval requirement.
2. **Always --analyze previous round** before submitting next. Learn from ground truth.
3. **Experiment freely.** Try new approaches. If --preview shows improvement over the proven model, submit the improved version.
4. **Log everything** to MEMORY.md. Every experiment, every submission, every score.
5. **Commit to agent-ml branch** after every round: `git add -A && git commit -m "Round N: score X.XX" && git push origin agent-ml`
6. **Explore new options.** Research recent 2026 advances in stochastic prediction, spatial modeling, Bayesian inference. Apply "Explore Before You Build" principle.
7. **Safety net:** If something breaks, fall back to the proven transition model. Never submit predictions you haven't validated (probability floors, renormalization, all 5 seeds).
8. **Write a summary** to intelligence/for-overseer/ml-sleep-report.md when done or when context fills up.

### Communication Schedule (staggered, avoid inbox flooding)
- Check intelligence/for-ml-agent/ at :00 and :30 past each hour
- Write status to intelligence/for-overseer/ at :05 and :35 past each hour

### Current State
- Round 3: score 39.72 (rank 33)
- v5 script with learned transitions from rounds 1-2 ground truth
- Key insight: 97-99% of cells stay same, score is won on 1-3% dynamic cells
- Next round expected ~3h after Round 3 closed

### What To Improve
- Build round-specific transition models (not just aggregate from rounds 1-2)
- Better spatial modeling (neighboring cells influence each other)
- Explore: Gaussian processes, neural grid models, cellular automata parameter inference
- More strategic query placement based on error analysis
