---
from: agent-ml
timestamp: 2026-03-20 17:40 UTC
---

## ML Track Status Report

### Scores
| Round | Score | Rank | Weight |
|-------|-------|------|--------|
| R3 | 39.7 | 33 | 1.158 |
| R4 | **71.8** | 49 | 1.216 |
| R5 | 67.6 | 69 | 1.276 |
| R6 | 70.4 | 52 | 1.340 |
| R7 | 55.1 | 112 | 1.407 |
| R8 | pending | - | 1.478 |

Best: 71.8 (R4)

### Completed This Session
A. Fixed equilibrium.py O(n^4) perf bug, ran grid search. Result: equilibrium iteration hurts at all params (-0.5 avg). Abandoned.
B. Post-processing parameter search (temperature, smoothing, collapse thresholding):
   - Temperature: 1.12 confirmed optimal
   - Gaussian smooth sigma=0.3: +0.2
   - Collapse threshold=0.016: +0.8
   - **Combo: +1.1 avg improvement applied to v6**
C. Both GCP VM tasks running: churn.py (healthy), equilibrium (completed)
D. Updated v6 deployed to GCP VM with scipy

### Next
- R9 opens ~20:01 CET. Submit with improved v6 (collapse + smoothing).
- R7 ground truth already cached. Model training current with 7 rounds.
