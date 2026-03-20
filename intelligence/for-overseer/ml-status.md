---
from: agent-ml
timestamp: 2026-03-20 21:55 UTC
priority: INFO
---

## ML Track Status — Session 6 (Overnight Deployment)

### Scores
| Round | Score | Rank | Weight |
|-------|-------|------|--------|
| R3 | 39.7 | 33/100 | 1.158 |
| R4 | 71.8 | 49/86 | 1.216 |
| R5 | 67.6 | 69/144 | 1.276 |
| R6 | 70.4 | 52/186 | 1.340 |
| R7 | 55.1 | 112/199 | 1.407 |
| R8 | 61.8 | 126/214 | 1.478 |
| R9 | **82.6** | 93/221 | 1.551 |
| R10 | pending | - | 1.629 |

Best: 82.6 (R9, rank 93/221)

### What was done
A. Cached R8+R9 ground truth (were missing)
B. Retrained V2 model: 72K cells from 9 rounds, backtest avg 65.6 (was 64.5 with 7 rounds)
C. Resubmitted R10 with retrained model + observations for all 5 seeds
D. Built overnight_runner.py: autonomous round handler with full lifecycle management
E. Deployed to GCP VM (PID 8653, 5-min interval)

### Incident
VM initially submitted bad model-only predictions with false extinction calibration for R10 (budget was exhausted, couldn't query, so 0 observations = 0% survival = false extinction). Fixed by:
1. Resubmitting from local with correct observations
2. Patching overnight_runner.py to check budget before attempting observations
3. Added disk fallback for observations and regime data

### GCP VM overnight_runner.py
- Running: PID 8653, 5-min cycle
- Will auto-submit R11+ rounds (observe all seeds, detect regime, submit)
- Will auto-cache ground truth and retrain model after each round closes
- State: knows R10 submitted, 9 rounds cached

### No action needed until morning review (Sunday ~09:00 CET)
