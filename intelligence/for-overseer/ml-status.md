---
from: agent-ml
timestamp: 2026-03-22 01:15 CET
priority: INFO
---

## ML Track Status -- v5 Multi-Seed Live

### Latest Scores
| Round | Score | Rank | Weight | Model |
|-------|-------|------|--------|-------|
| R17 | 67.9 | 179 | 2.292 | v4 32-feat + hard constraints |
| R18 | 28.6 | 214 | 2.407 | v4 51-feat + obs proxy (OOD growth) |
| R19 | pending | - | ~2.53 | **v5 multi-seed, regime=death** |

### Current Approach
overnight_v5 deployed on ml-brain. Key changes from v4:
- Multi-seed observation: 9 queries per seed x 5 seeds = full grid coverage
- All 5 seeds get obs_settle_growth proxy (was only deep seed)
- All 5 seeds get Dirichlet blending (was only deep seed)
- Per-regime alpha (death=5, stable=30, growth=15)
- Regime reclassification from full-grid observations

### R18 Post-Mortem
R18 was explosive growth (11.6x, 2602 new settlements). Our training max was 4.8x.
The model was out-of-distribution. Regime was correctly detected as growth.
The score (28.6) was from wrong predictions, not wrong regime.

### Key Finding: Game Is Escalating
Growth magnitude is increasing over time:
R6=1.6x, R7=2.3x, R11=3.3x, R12=4.0x, R14=5.8x, R18=11.6x
Competition is making growth rounds progressively harder.
Our 80+ scores (R9, R15) were both death rounds (easy to predict).

### Blockers
None. v5 is autonomous with cron watchdog.

### What's Running
- ml-brain: overnight_v5 (multi-seed, 51 features, obs proxies, cron active)
- ml-churn: IDLE
- Temperature calibration: tested, +0.1 improvement (negligible, not deployed)

### Next Steps
- Monitor R19 score (first v5 multi-seed submission)
- Investigate how to handle escalating growth magnitudes
- Feature freeze 09:00 CET
