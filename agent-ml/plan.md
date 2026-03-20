# Astar Island — Plan

**Track:** ML | **Task:** Norse World Prediction | **Weight:** 33.33%
**Last updated:** 2026-03-20 18:20 UTC

## Current State
- **Best score:** 71.77 (R4, leaderboard 87.3)
- **Rounds submitted:** 8 (R3-R8, R1-R2 missed)
- **R8 scores:** pending (resubmitted with collapse+smoothing)
- **R9:** active, closes 20:47 UTC (21:47 CET), 150 min remaining
- **Script:** `solutions/astar_v6.py` with V2 model + Dirichlet + collapse + smoothing
- **Simulator:** `solutions/simulate.py` (needs update to V2 model + post-processing)

## Active Phase: Simulator Update + Strategy Optimization

### Goal
Use Monte Carlo simulation to find the optimal query batch size before R9.
Currently using batches of 8 (strategy G). Is 5, 8, or 10 better with the new model?

### Why This Matters
- Each query is precious (50 total per round)
- Smaller batches = more hindsight re-targeting = better query placement
- But: smaller batches = less data per hindsight step = noisier surprise estimates
- The simulator can answer this definitively with 7 rounds of ground truth data

### Plan
1. **Update simulate.py** to use NeighborhoodModelV2 (was using old PredictionModel)
2. **Add post-processing** to execute_strategy (collapse=0.016, smooth=0.3, T=1.12)
3. **Deploy to GCP VM** and run tournament (8 strategies x 30 trials x 7 rounds)
4. **Read results** and configure v6 with winning strategy
5. **Submit R9** with optimized strategy at 20:00 CET or when ready

### Time Budget
- Build + deploy: ~15 min
- GCP run (8 strats x 30 trials x 7 rounds): ~15-20 min
- Analyze + configure: ~10 min
- R9 execution (queries + submit): ~10 min
- Buffer: 90+ min

---

## Model Stack (current, applied to v6)
1. V2 NeighborhoodModel (1102 configs, distance-to-settlement features)
2. Dirichlet-Categorical Bayesian observation blending (prior_strength=12)
3. Temperature scaling T=1.12
4. Collapse thresholding at 0.016 (+0.8 avg)
5. Gaussian spatial smoothing sigma=0.3 (+0.2 avg)
6. Probability floor 0.01 + renormalization

## Proven Results
| Technique | Delta | Source |
|-----------|-------|--------|
| V2 neighborhood model | +3.4 vs V1 | BT-002 |
| Dirichlet Bayesian blend | +1.1 vs hard blend | session 4 |
| Temperature T=1.12 | +1.2 vs no scaling | churn.py |
| Collapse threshold 0.016 | +0.8 | PP-001 |
| Gaussian smooth 0.3 | +0.2 | PP-001 |
| Combo (all above) | backtest avg 64.5 | PP-001 |

## Disproven
| Technique | Delta | Source |
|-----------|-------|--------|
| Equilibrium iteration | -0.5 best case | EQ-001 |
| Per-class temperature | 0 vs global | session 4 |
| Single-obs secondary seeds | -1.5 avg | HINDSIGHT-001 |

## Key Learnings (rounds 1-8)
- Settlement/Port cells dominate scoring (high entropy, high weight)
- Hidden params vary hugely between rounds (round 4: 249 changes vs 37 in round 3)
- Stacking wins massively: N=1 score ~2, N=7 score ~58 for settlements
- Cross-seed transfer is nearly optimal (0.7 point gap)
- Single-obs on secondary seeds HURTS settlements (-3.6 to -11.3)
- Leaderboard = BEST round score (not cumulative)

## Scoring Math
```
score = 100 * exp(-3 * weighted_kl)
```
- weighted_kl 0.30 -> score 41
- weighted_kl 0.20 -> score 55
- weighted_kl 0.10 -> score 74
- weighted_kl 0.05 -> score 86

## Remaining Questions
- Which batch size is optimal for adaptive stacking? (this session's focus)
- Can settlement stats (food, pop) predict per-cell survival?
- What's the theoretical max score with 50 queries?
