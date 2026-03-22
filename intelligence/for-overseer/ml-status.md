---
from: agent-ml
timestamp: 2026-03-22 08:15 CET
priority: INFO
---

## ML Track Status -- v5 Multi-Seed PERFORMING

### Latest Scores
| Round | Score | Rank | Weight | Weighted |
|-------|-------|------|--------|----------|
| R18 | 28.6 | 214 | 2.407 | 68.9 |
| **R19** | **85.3** | **102** | **2.527** | **215.6** |
| **R20** | **82.8** | **92** | **2.653** | **219.6** |
| **R21** | **78.7** | **155** | **2.786** | **219.3** |
| R22 | pending | - | ~2.93 | - |

Total weighted: 2326.3

### Current Approach
overnight_v5 on ml-brain:
- Multi-seed observation: 9 queries per seed x 5 seeds = full coverage
- 51 features with trajectory features from replays
- obs_settle_growth proxy on ALL seeds
- Per-regime Dirichlet alpha (death=5, stable=30, growth=15)
- Regime reclassification from full-grid observations
- Hard constraints (port-coastal, ruin-cap)
- Cron watchdog active, autonomous

### What Changed Since Last Report
- Deployed overnight_v5 (multi-seed observation)
- R19-R21 all scored 78+ (v5 working)
- R18 post-mortem: explosive growth OOD (11.6x, training max was 4.8x)
- Temperature calibration tested: +0.1 (negligible, not deployed)

### Blockers
None. System is autonomous and performing well.

### No action needed. System is running.
