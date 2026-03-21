# Astar Island — Plan

**Track:** ML | **Task:** Norse World Prediction | **Weight:** 33.33%
**Last updated:** 2026-03-21 00:05 UTC
**Rank:** ~166/238 | **Best:** 82.6 (R9) | **Target:** 90+

## Architecture
- **Chef** = pipeline script (v7 current, v8 building). Observes, detects regime, predicts, submits.
- **Brain** = prediction model (V2 current, V3 building). Transition lookup table.
- **overnight_runner.py** = autonomous line cook on GCP. Runs Chef every round.

## Score History
| Round | Score | Rank | Regime | Notes |
|-------|-------|------|--------|-------|
| R3 | 39.7 | 33/100 | death | No regime detection |
| R4 | 71.8 | 49/86 | death | Best until R9 |
| R5 | 67.6 | 69/144 | stable | |
| R6 | 70.4 | 52/186 | growth | |
| R7 | 55.1 | 112/199 | growth | Hard round |
| R8 | 61.8 | 126/214 | death | |
| R9 | 82.6 | 93/221 | death | Best round |
| R10 | 50.2 | 166/238 | death | Wrong regime detected! |

---

## Root Cause: R10 Failure
We detected "growth" when the actual regime was "death" (0% survival).
With 1 sample per cell, there's a 52% chance of false positive in death rounds.
Wrong regime = wrong predictions on settlement cells = 7 point penalty.

## What We Learned (from GCP experiments)

| Experiment | Result | Action |
|-----------|--------|--------|
| Query Sim | All strategies within 0.4 pts | Keep current (all 5 seeds) |
| Weighted Model | decay=0.7 boost=5 -> 66.97 (+1.6) | Integrate into Brain V3 |
| Regime Model | +3.37 avg, growth +8.8 | Integrate into Brain V3 |
| Grid Search | T=1.0 sigma=0.3 marginally better | Minor param tweak |
| Brain V3 fit | Initial 68.29, fitting in progress | Deploy when ready |
| Collapse bug | Was no-op, now fixed | Already deployed |
| Research agent | Per-terrain alpha, entropy-aware T | Integrate into Brain V3 |

---

## Phase 1: Chef v8 + Brain V3 (NOW)

### A. Chef v8 — Smell Test Protocol
1. 5 queries: sample 5 settlement cells on seed 0
2. Count alive: 0/5 = death (96% conf), 5/5 = growth (84% conf)
3. If uncertain (1-4/5): 5 more queries re-sampling SAME cells
4. With 2 samples: false positive drops from 52% to <5%
5. Remaining (40-45): Option B, spread across all 5 seeds

### B. Brain V3 — Three improvements stacked
1. Regime-specific transition tables (death/stable/growth)
2. Per-terrain Dirichlet alpha (fit from backtest data on GCP)
3. Entropy-aware temperature (different T for confident vs uncertain cells)
4. Reinforcement weighting (recent rounds + regime-match boost)
5. Fixed collapse thresholding (was no-op in v7)

### C. Brain Enhancement on GCP
Run continuous improvement loop between rounds:
1. After round closes: cache ground truth
2. Retrain Brain on ALL rounds (now 10)
3. Re-fit alphas and temperatures (scipy.optimize on backtest)
4. Score previous prediction vs ground truth (find error patterns)
5. Deploy improved Brain for next round
6. Log results for morning review

## Phase 2: Deploy Self-Improving Runner
Upgrade overnight_runner.py to use Chef v8 + Brain V3 + self-improvement loop.
Deploy to GCP VM. Test with R10 data before R11 opens.

## Phase 3: Overnight Autonomous
Runner handles R11+ with self-improving loop. Every round it gets smarter.

## Phase 4: Morning Review (Sunday ~09:00 CET)
Check scores, deploy final improvements, feature freeze.

## Phase 5: Competition Close (Sunday 15:00 CET)
Final submission, repo public at 14:45.
