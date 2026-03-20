---
from: agent-ml
timestamp: 2026-03-20 20:36 UTC
priority: HIGH
---

## ML Track Status Report — Session 5

### Scores
| Round | Score | Rank | Weight |
|-------|-------|------|--------|
| R3 | 39.7 | 33/100 | 1.158 |
| R4 | **71.8** | 49/86 | 1.216 |
| R5 | 67.6 | 69/144 | 1.276 |
| R6 | 70.4 | 52/186 | 1.340 |
| R7 | 55.1 | 112/199 | 1.407 |
| R8 | 61.8 | 126/214 | 1.478 |
| R9 | pending | - | 1.551 |

Best: 71.8 (R4)

### Mistakes Made This Competition
A. **Rounds 1-2 missed entirely** — agent not running when competition started
B. **R3 scored 39.7** — all 50 queries on seed 0, seeds 1-4 pure guesswork
C. **R7-R8 regression** (55-62 vs 68-72 in R4-R6) — harder rounds, model didn't adapt
D. **80% of every submission was guesswork** — only observed seed 0, never seeds 1-4
E. **No regime detection** — treated death rounds and growth rounds identically

### Hidden Rules Discovered (see hidden-rules-discovery.md for full list)
A. Ground truth = 200 Monte Carlo runs (probability granularity 0.005)
B. Three round regimes: death (0% survival), quiet (60-88%), growth (2-3x)
C. Settlement spread has distance cutoff (3-12 Manhattan distance, varies per round)
D. Forests consumed by adjacent settlements (50-60% vs 97-99% when isolated)
E. Ports ONLY appear adjacent to ocean (100% rule)
F. Mountains kill adjacent settlements (15-37% survival vs 60%)
G. Ruins are background noise (<10% probability), never argmax
H. Cross-seed survival rates within a round: std dev only 0.3-2.5%

### V7 Built and Backtested (+2.7 avg)
**New approach:**
1. Query ALL 5 seeds (9 each = 45 queries for full map of every kitchen)
2. Detect death rounds from seed 0 observations
3. Apply death calibration to all seeds when detected
4. Use 5 remaining queries on seed 0 high-value cells
5. Port constraint: zero port probability on non-coastal cells

**Backtest results:**
- Death rounds: +34.6 (R3: 66.3 vs 31.7)
- Non-death rounds: -0.3 to -5.7 (1 sample per cell noisier than 6-13 stacked)
- Overall: +2.7 avg improvement

### R10 Plan
- R10 opens ~21:02 UTC (22:02 CET)
- Run v7: observe all 5 seeds, detect regime, stack 5 on seed 0, submit
- JC directing query strategy, will not auto-query without approval

### GCP VM
- churn.py: running (healthy, 9h uptime)
- equilibrium.py: completed (abandoned, -0.5 at all params)
