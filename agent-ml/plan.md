# Astar Island — Plan

**Track:** ML | **Last updated:** 2026-03-21 10:15 UTC
**Best:** 82.6 (R9) | **Rank:** ~100/238 | **Deadline:** Sunday 15:00 CET (~28h left)

## Current State
- R14 active, closes ~12:59 CET, growth regime, all 5 seeds observed
- 13 rounds of ground truth cached (R1-R13, 104K cells)
- Brain V3 backtest: 72.86 (calibrated estimate: ~66)
- Backtest overshoots reality by +7 on average (std 14.6)
- GCP: overnight_v2 + churn_v2 running on ml-churn VM

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
| R14 | pending | - | growth | v9* | *Submitted V2 no-obs (mistake) |

## Key Lessons
A. R9 (best) used V2 global model + deep stack seed 0. Simple won.
B. V3 regime model wins 10/13 rounds on average but destroyed R9 (-29).
C. Backtest overshoots by +7. Never trust backtest without real confirmation.
D. Deep stacking (40+ queries on 1 seed) > thin coverage (8 per seed).
E. Observations are the #1 scoring lever, not model architecture.

---

## Phase 1: Fix R14 NOW
1. Resubmit R14 with V3+observations (overnight runner's version was better than V9 no-obs)
2. Both V2 and V3 predictions use the same R14 observations
3. Log calibrated estimate for R14

## Phase 2: Two-Track GCP Setup
Run both approaches in parallel on GCP:
- **Track A (ml-churn VM):** V3 regime model + churn optimization (already running)
- **Track B (new process on ml-churn):** V2 global model + deep stack strategy
After each round: compare both predictions against ground truth, submit the winner next round.

## Phase 3: Calibration Loop
After R14 scores:
1. Compare R14 actual vs our calibrated estimate
2. Update calibration factor
3. Adjust churn to optimize for calibrated score, not raw backtest

## Phase 4: Overnight Strategy (Saturday night -> Sunday)
- Both tracks run autonomously
- Each round: submit whichever model has better calibrated estimate
- Self-improvement continues between rounds
- Feature freeze Sunday 09:00 CET

## Phase 5: Final Submission (Sunday 15:00 CET)
- Submit with best calibrated model
- Repo public at 14:45
