# Astar Island -- Plan

**Last updated:** 2026-03-21 19:50 UTC
**Best:** 169.6 (R15=81.6) | **Rank:** 167 | **Top 1:** 196.6 | **~19h left, ~6 rounds**

## What's Running
| VM | Process | Status |
|----|---------|--------|
| ml-brain | overnight_v4 (autonomous round handler, V4 32-feat) | Running, handling R17 |
| ml-churn | churn_v4 (32-feat hyperparameter search) | Running |

overnight_v4 handles: observe, predict, submit, cache GT, download replay, rebuild dataset.
No manual intervention needed for round operations.

## Priority 1: Deep Analysis on GCP
The competition briefing (OVERSEER-BRIEFING-ASTAR-DEEP-ANALYSIS.md) identified
hidden rules from 8 rounds. We now have 16 rounds + 80 replay files.
These rules have NEVER been validated. Some may be wrong. Some may reveal
new patterns we're missing.

### Task: Create `deep_analysis.py` and run on GCP
Process ALL 80 replay files (16 rounds x 5 seeds x 51 frames = ~6.5M cell-states).

Hypotheses to test:
1. Empty -> Forest transition rate (claimed: zero)
2. Settlement expansion radius by regime type
3. Mountain adjacency effect on settlement survival
4. Port formation rules (coastal only? what triggers it?)
5. Ruin lifecycle (how many years before forest reclaims?)
6. Winter detection: can year-10 stats predict year-50 outcome?
7. Faction dynamics (owner_id patterns)
8. What distinguishes predictable rounds (R9, R15) from chaotic ones (R16)?

### Output: Hard constraints + new features for V4
- If empty never becomes forest: force forest probability to 0.01 for empty cells
- If ruins never dominant: cap ruin probability
- If expansion radius is bounded: distance-based cutoff for settlement probability
- Settlement health features from year-0 replay data

## Priority 2: Keep Autonomous System Running
overnight_v4 and churn_v4 handle rounds and optimization.
Check health periodically. Fix if crashed.

## Round Workflow (automated in overnight_v4)
1. Detect round -> smell test -> deep stack rotating seed
2. Train V4 on master dataset -> predict -> submit
3. Resubmit if churn finds better params
4. After close: cache GT, download replay, rebuild dataset, calibrate

## Deep Stack Rotation
R17=seed 2, R18=seed 3, R19=seed 4, R20=seed 0

## Calibration (V4 32-feat)
Death: backtest overshoots +15.6. Growth: +5.5. Stable: +13.4. Overall: +11.6.
