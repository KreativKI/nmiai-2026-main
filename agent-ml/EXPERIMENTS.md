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

