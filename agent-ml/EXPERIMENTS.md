# ML Track Experiments Log

All backtest and model experiments are logged here with results.
Format: timestamp, config, scores, verdict.

---

## BT-001: Baseline Backtest (default model params)
**Date:** 2026-03-20 11:10 UTC
**Tool:** backtest.py --cached-only --with-obs
**Config:** Default PredictionModel params (hist_blend=0.1, obs_weight_settle=0.95)

### Results Summary

| Mode | R1 | R2 | R3 | R4 | R5 | Avg | Best |
|------|-----|-----|-----|-----|-----|------|------|
| Hist only | 64.7 | 65.7 | 27.3 | 77.6 | 61.5 | 59.3 | 77.6 |
| Leave-one-out | 64.7 | 65.7 | 27.3 | 77.6 | 61.5 | 59.3 | 77.6 |
| Oracle (ceiling) | 69.9 | 75.9 | 41.8 | 78.2 | 67.0 | 66.6 | 78.2 |
| With real obs | 64.7 | 65.7 | 27.3 | 76.6 | 68.2 | 60.5 | 76.6 |

### Per-Class KL (avg across rounds, hist_only mode)
| Class | Avg KL | Avg Score | Entropy Share |
|-------|--------|-----------|---------------|
| Empty | 0.127 | 69.1 | 62-69% |
| Settlement | 0.594 | 19.2 | 5-27% |
| Port | 0.462 | 29.7 | 0.2-1.3% |
| Forest | 0.141 | 66.8 | 26-28% |
| Mountain | 0.051 | 85.7 | ~0% |

### Key Insights
A. Settlement KL dominates: 0.47-0.99 across rounds (scores 5-24)
B. Oracle barely helps settlements: same 8-24 score range as no-info mode
C. Real observations provide biggest boost on observed seeds (R5 seed 0: +12.1 points)
D. Round 3 is fundamentally hard (catastrophic die-off): 27-42 all modes
E. Hist-only and leave-one-out are identical (only 5 rounds, transitions stable)

### Verdict
Backtester validated against actual submissions. Settlement prediction is the #1 improvement target.
The model's structural approach to settlements (uniform transition by class + adjacency) cannot capture the per-cell heterogeneity. Observations are the only way to resolve this.

### Validated against actual scores
- R4 actual: 71.8, backtest with-obs: 76.6 (delta from param differences in v6 vs default)
- R5 seed 0 actual: 72.6, backtest: 72.6 (exact match)

## BT-002: New params (near 0.6/0.4/0.2, no forest bonus) with 6 rounds
**Date:** 2026-03-20 12:54 UTC
**Config:** near_dist 0.6/0.4/0.2, forest_bonus=0, 6 rounds including R6

| Mode | R1 | R2 | R3 | R4 | R5 | R6 | Avg | Best |
|------|-----|-----|-----|-----|-----|-----|------|------|
| Leave-one-out | 67.5 | 70.0 | 33.1 | 79.5 | 65.2 | 47.9 | 60.5 | 79.5 |
| With real obs | 67.5 | 70.0 | 33.1 | 77.9 | 68.1 | 69.9 | 64.4 | 77.9 |

### Key finding
R6 observations boost: 47.9 -> 69.9 (+22 points). Largest observation effect seen.
This confirms adaptive query targeting (hindsight stacking) has highest ROI.

## EXP-003: Adaptive stacking (hindsight-based query targeting)
**Date:** 2026-03-20 12:30 UTC
**Change:** Replace static stacking with adaptive batching (8 queries per batch,
compute per-cell surprise between batches, re-target next batch at high-surprise areas)
**Hypothesis:** Targeting queries where model is MOST wrong should improve observed-seed scores
**Cannot backtest offline:** Depends on live API responses (stochastic observations)
**Will test live:** Round 8 (weight ~1.48)
**Verdict:** Pending live results

## HINDSIGHT-001: Post-round query analysis (rounds 4-6)
**Date:** 2026-03-20 13:12 UTC
**Tool:** hindsight.py --cached-only

### Observation boost by seed
| Round | Seed 0 (deep stack) | Seed 1 (single cov) | Seed 2 (single cov) |
|-------|---------------------|----------------------|----------------------|
| R4 | +0.4 | **-5.6** | **-3.9** |
| R5 | +6.4 | +0.7 | n/a |
| R6 | +12.8 | +0.3 | n/a |
| **Avg** | **+6.5** | **-1.5** | **-3.9** |

### Settlement info gain on single-coverage seeds
R4 seed 1: -11.3, R4 seed 2: -7.1, R5 seed 1: -3.6, R6 seed 1: -6.8
**Single observation of settlements is WORSE than the transition model.**

### Query targeting
Only 12% of our queries hit the top-200 highest-error cells.
Adaptive stacking + hindsight re-targeting should improve this.

### Strategy change applied
- Skip seed 1/2 coverage entirely (default --max-secondary 0)
- All 41 remaining queries -> adaptive stacking on seed 0
- Expected: seed 0 gets ~50 queries (13+ samples/cell) instead of 32+9 split

## EQ-001: Equilibrium iteration grid search
**Date:** 2026-03-20 17:11 UTC
**Tool:** equilibrium.py --search (fixed O(n^4) -> O(n^2) perf bug, ran on GCP VM)
**Config:** Grid search: steps=[2,3,4,5,8] x damping=[0.3,0.5,0.7,0.8,0.9], T=1.12, V2 model

### Results
| Steps | d=0.3 | d=0.5 | d=0.7 | d=0.8 | d=0.9 |
|-------|-------|-------|-------|-------|-------|
| 2 | 57.3 | 61.0 | 63.1 | 63.6 | 64.0 |
| 3 | 50.8 | 56.1 | 60.9 | 62.6 | 63.7 |
| 4 | 47.9 | 52.2 | 58.3 | 61.2 | 63.3 |
| 5 | 46.9 | 49.6 | 55.8 | 59.6 | 62.7 |
| 8 | 46.5 | 46.9 | 50.5 | 55.0 | 60.7 |

**Best:** steps=2, damping=0.9, avg=64.0
**Baseline (single-step):** avg=64.5
**Delta:** -0.5
**Verdict:** Equilibrium iteration hurts at all parameters. The argmax-based virtual grid loses probability distribution information. More steps = worse. High damping (0.9) = nearly no iteration = closest to baseline. **Approach abandoned.**

