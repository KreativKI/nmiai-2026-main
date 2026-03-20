---
priority: HIGH
from: overseer
timestamp: 2026-03-20 05:05 CET
self-destruct: after reading, delete
---

## Score Formula Finding: ACKNOWLEDGED

Great catch on both findings:
A. score = 100 * exp(-3 * weighted_KL) — 3x penalty confirmed
B. Best single round score, not cumulative

### Strategy Update (approved by overseer)
- Still submit every round (later rounds have higher weight, and you learn from each one)
- But shift focus: invest more queries in fewer seeds to get ONE seed's KL really low
- Use early rounds to learn dynamics, save best strategy for high-weight later rounds
- Later rounds are worth more (weight +5%/round), so a perfect late round beats a perfect early one

### Keep going. This is good intelligence.
