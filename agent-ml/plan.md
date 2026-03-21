# Astar Island -- Plan

**Track:** ML | **Last updated:** 2026-03-21 14:40 UTC
**Best weighted:** 134.2 (R14) | **Rank:** 162 | **Top 3:** 177 | **Deadline:** Sunday 15:00 CET

## Current State
- R15 submitted with Brain V4 (LightGBM) + calibrated alpha=20 + deep stack seed 0
- 14 rounds ground truth cached (R1-R14, 95K training cells)
- Brain V4 backtests +6.2 points over V3 on R14 real data
- GCP: churn_v3 running on ml-churn, overnight_v3 paused (manual control)

## Pipeline Rules (mandatory every round)

### Rule 1: Test Before Submit
Before every submission or resubmission:
1. Generate predictions with ALL variant models
2. Score each variant against most recent completed round using REAL observations
3. Pick the winner based on actual scored data, not estimates
4. Submit the winner

### Rule 2: Rotate Deep Stack Seed
Cycle which seed gets all 50 queries:
- R15: seed 0 (done)
- R16: seed 1
- R17: seed 2
- R18: seed 3
- R19: seed 4
- R20: seed 0 (restart cycle)

### Rule 3: Calibrate Weights
Test Dirichlet alpha values (2, 4, 8, 12, 16, 20, 30, 50) against real data before each round. Currently alpha=20 is optimal for V4.

## Models

| Model | Type | Avg Backtest | Status |
|-------|------|-------------|--------|
| Brain V4 | LightGBM (13 features, 95K cells) | 74.0 | **Active. Primary model.** |
| Brain V3 | Regime lookup table | 69.2 | Retired. V4 beats it 12/14 rounds. |
| Brain V2 | Global lookup table | 65.6 | Available for blend if needed. |

## Score History
| Round | Score | Rank | Weight | Weighted | Model |
|-------|-------|------|--------|----------|-------|
| R14 | 67.8 | 95 | 1.980 | **134.2** | V3+V2 blend |
| R9 | 82.6 | 93 | 1.551 | 128.1 | V2 deep stack |
| R15 | pending | - | 2.079 | - | **V4 + alpha=20** |

## Targets (leaderboard = best round_score x weight)
| Target | R16 (2.18) | R17 (2.29) | R18 (2.41) |
|--------|-----------|-----------|-----------|
| Top 50 (166) | 76.1 | 72.5 | 69.0 |
| Top 20 (173) | 79.3 | 75.5 | 71.9 |
| Top 3 (177) | 80.9 | 77.1 | 73.4 |

## Next Steps
1. Wait for R15 score (closes ~15:52 CET)
2. Cache R15 ground truth
3. Recalibrate V4 alpha with R15 real data
4. R16: deep stack seed 1, test variants, submit best
5. Before sleep: integrate V4 into overnight_v3, re-enable autonomous mode
