---
from: agent-ml
timestamp: 2026-03-20 18:33 UTC
---

## ML Track Status Report

### R9 SUBMITTED (all 5 seeds)
- 50/50 queries used, 8 rounds training data (64K cells)
- Model: V2 + Dirichlet ps=12 + T=1.12 + collapse=0.016 + smooth=0.3
- Score: pending. R9 closes 20:47 UTC.

### All Scores
| Round | Score | Rank | Weight |
|-------|-------|------|--------|
| R3 | 39.7 | 33 | 1.158 |
| R4 | **71.8** | 49 | 1.216 |
| R5 | 67.6 | 69 | 1.276 |
| R6 | 70.4 | 52 | 1.340 |
| R7 | 55.1 | 112 | 1.407 |
| R8 | pending | - | 1.478 |
| R9 | pending | - | 1.551 |

### Completed This Session
A. Fixed equilibrium.py O(n^4) perf bug, grid search: abandoned (-0.5)
B. Post-processing: collapse=0.016 (+0.8), smooth=0.3 (+0.2), combo +1.1
C. R8 resubmitted with post-processing before close
D. R9 submitted with all improvements + 8 rounds training data

### In Progress
- Simulator update (V2 model + post-processing). Debugging integration.
- Goal: find optimal batch size for adaptive stacking, resubmit R9 if better.

### GCP VM
- churn.py: running (healthy)
- equilibrium.py: completed (abandoned)
