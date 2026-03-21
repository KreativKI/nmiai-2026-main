# Astar Island -- Plan

**Track:** ML | **Last updated:** 2026-03-21 10:50 UTC
**Best:** 82.6 (R9) | **Rank:** ~100/238 | **Deadline:** Sunday 15:00 CET (~27h left)

## Current State
- R14 active, closes ~12:59 CET, growth regime, all 5 seeds observed + submitted
- 13 rounds of ground truth cached (R1-R13, 104K cells)
- Brain V3 backtest: 72.86 (calibrated estimate: ~66)
- **GCP upgraded to v3:** overnight_v3 + churn_v3 running on ml-churn VM
- Three improvements deployed: dual V2+V3 blend, settlement stats, calibrated scoring

## Score History
| Round | Score | Rank | Regime | Chef | Notes |
|-------|-------|------|--------|------|-------|
| R3 | 39.7 | 33/100 | death | v3 | No observations |
| R4 | 71.8 | 49/86 | death | v6 | Deep stack seed 0 |
| R5 | 67.6 | 69/144 | stable | v6 | |
| R6 | 70.4 | 52/186 | growth | v6 | |
| R7 | 55.1 | 112/199 | growth | v6 | Hard round |
| R8 | 61.8 | 126/214 | death | v6 | |
| R9 | **82.6** | 93/221 | death | **v6** | **Best. Deep stack. V2 model.** |
| R10 | 50.2 | 166/238 | death | v7 | Wrong regime detected |
| R11 | 69.0 | 92/171 | growth | v8 | V3 regime model |
| R12 | 49.7 | 72/146 | growth | v8 | |
| R13 | 63.3 | 141/186 | death | v8 | |
| R14 | pending | - | growth | v8 (overnight) | V3+obs, submitted by overnight_v2 |

## V2 vs V3 Backtest (3-round LOO)
| Round | Regime | V2 | V3 | Winner |
|-------|--------|-----|-----|--------|
| R7 | growth | 53.2 | 62.5 | V3 |
| R8 | death | 62.2 | 83.9 | V3 |
| R9 | death | 81.4 | 61.3 | V2 |
| **Avg** | | **65.6** | **69.2** | **V3** |

Blend weights: V3=51% V2=49%. Neither model dominates. Blending hedges volatility.

## Key Lessons
A. R9 (best) used V2 global model + deep stack seed 0. Simple won.
B. V3 regime model wins on average (+3.6) but destroyed R9 (-29).
C. Backtest overshoots by +7. Death: +20. Growth: -5.
D. Observations are the #1 scoring lever, not model architecture.
E. Settlement stats (population, food, wealth, defense) available from /simulate but untapped.

---

## What's Running on GCP

### overnight_v3.py (PID 33715)
- Dual-track: generates BOTH V2 and V3 predictions, blends by model_weights.json
- Settlement stats: captures population/food/wealth/defense from /simulate
- Self-improvement: compares V2 vs V3 after each round, updates blend weights
- Calibrated scoring: regime-specific offsets in V2/V3 comparison

### churn_v3.py (PID 33755)
- Calibration-aware: optimizes for estimated real score (backtest - regime offset)
- Growth rounds weighted favorably (backtest undershoots by 5)
- Updates model_weights.json every 5 batches
- 1400+ experiments already run by v2, v3 continues from best params

### Cron (every 15 min)
- Restarts overnight_v3 if crashed
- Restarts churn_v3 if crashed

---

## Phase 1: DONE -- V3 Deployment
All three improvements deployed to GCP:
1. Dual V2+V3 blend (weighted prediction submission)
2. Settlement stats collection (regime detection enhancement)
3. Calibrated churn (regime-weighted optimization)

## Phase 2: Monitor R14 Score
After R14 closes (~12:59 CET):
1. overnight_v3 caches R14 ground truth
2. Self-improvement runs: retrains brain, compares V2 vs V3, sets blend weights
3. model_weights.json created with data-driven blend ratios
4. R15 starts with blended predictions

## Phase 3: Overnight Strategy (Saturday night -> Sunday)
- Both models run in blend mode
- Self-improvement updates weights after each round
- Settlement stats accumulate and improve regime detection
- Feature freeze Sunday 09:00 CET

## Phase 4: Final Submission (Sunday 15:00 CET)
- Submit with best calibrated blend
- Repo public at 14:45
