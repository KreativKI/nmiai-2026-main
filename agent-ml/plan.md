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

## Priority 1: Deep Analysis on GCP — IMPLEMENTATION PLAN

### Goal
Validate 8 hypotheses from briefing using 75 replay files (16 rounds).
Output: actionable hard constraints and feature ideas for V4 model.

### Architecture
Single file `deep_analysis.py` that:
- Loads ALL replays from data/replays/
- Processes frame-by-frame transitions (year N -> year N+1)
- Groups results by regime (death/stable/growth, using classify_round)
- Prints structured findings per hypothesis
- Outputs JSON summary to data/deep_analysis_results.json

### Data flow
```
replays/*.json (75 files, 51 frames each)
    -> for each file: track cell transitions year-over-year
    -> aggregate into transition matrices per regime
    -> test each hypothesis
    -> print findings + save JSON
```

### Hypothesis tests (detailed)

H1: Empty->Forest transitions
- Count transitions where cell goes from Empty(0) to Forest(4) between any consecutive years
- Group by regime. If truly zero across ALL data, that's a hard constraint.

H2: Settlement expansion radius
- For each round/seed: find initial settlement positions (year 0)
- Find NEW settlements at year 50 (not in initial set)
- Measure Manhattan distance from each new settlement to nearest initial settlement
- Report min/median/max by regime

H3: Mountain adjacency kills settlements
- For each settlement at year 0: count adjacent mountains
- Track which settlements survive to year 50
- Report survival rate by mountain adjacency count (0, 1, 2+)

H4: Port formation rules
- Find all cells that become Port at any year
- Check if every port has ocean adjacency
- Measure what % of coastal settlements become ports

H5: Ruin lifecycle
- Track how long Ruin(3) cells persist before changing
- Measure transitions: Ruin->Forest, Ruin->Empty, Ruin->stays Ruin
- Report average ruin lifespan in years

H6: Winter detection from year-10 stats
- At year 10: count alive settlements per seed
- At year 50: classify regime (death/stable/growth)
- Test if year-10 survival rate predicts year-50 regime

H7: Faction dynamics
- Track owner_id persistence over time
- Count number of unique factions at year 0, 10, 25, 50
- Measure faction consolidation (do big factions absorb small ones?)

H8: Predictable vs chaotic rounds
- For each round: compute variance of year-50 settlement counts across 5 seeds
- Low variance = predictable. High variance = chaotic.
- Correlate with actual competition scores

### Dependencies
- json, numpy, pathlib (stdlib + numpy only)
- Uses classify_round from regime_model.py for regime labels
- Uses TERRAIN_TO_CLASS, STATIC_TERRAIN from backtest.py

### NOT in scope
- Modifying overnight_v4, churn_v4, or build_dataset
- Training any model
- Making API calls or submissions

## Priority 2: Apply Hard Constraints to overnight_v4 (CURRENT)

### Goal
Use deep analysis findings as post-processing hard constraints on predictions.
Resubmit R17 with improved predictions. Future rounds get them automatically.

### Changes to overnight_v4.py predict_and_submit()
After Dirichlet blending (line 309), before floor+renormalize (line 311):

```python
# Hard constraints from deep analysis
OCEAN_RAW = {10, 11}
for y in range(h):
    for x in range(w):
        if int(ig[y][x]) in STATIC_TERRAIN:
            continue
        # H4: Ports ONLY form on coastal cells
        has_ocean = any(
            int(ig[y+dy][x+dx]) in OCEAN_RAW
            for dy in (-1, 0, 1) for dx in (-1, 0, 1)
            if (dy, dx) != (0, 0) and 0 <= y+dy < h and 0 <= x+dx < w
        )
        if not has_ocean:
            pred[y, x, 2] = PROB_FLOOR  # Port
        # H5: Ruin never dominant at year 50 (avg lifespan 1 year)
        pred[y, x, 3] = min(pred[y, x, 3], 0.05)
```

### Deployment
1. Edit overnight_v4.py locally
2. Boris review/simplify/validate
3. SCP to ml-brain VM
4. Kill overnight_v4, restart it
5. Touch brain_v4_params.json to trigger resubmit of R17

### Risk
Low: only adds post-processing constraints. Prediction pipeline unchanged.
Resubmit uses existing obs data cached from initial R17 submission.

## Priority 3: Keep Autonomous System Running
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
