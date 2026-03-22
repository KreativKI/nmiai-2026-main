# ML Session Handoff -- 2026-03-22 01:00 CET

## Score: R18=28.6 (WORST ROUND). R17=67.9. overnight_v5 running.

## R18 Post-Mortem (from actual data, not guessing)
R18 was explosive growth: 30-54 initial -> 386-720 at year 50 (12-15x).
Growth rate 11.6x from ground truth, highest ever seen.
Our training max was 4.8x. The model had no experience with this level
of growth and predicted wrong. Regime was correctly detected as growth.
Problem: out-of-distribution growth magnitude, not regime detection.

## What's Running
- ml-brain: overnight_v5 (MULTI-SEED observation, 9 queries per seed)
  - Cron watchdog active (~/start_v5.sh)
  - 51 features, obs proxies on ALL seeds, per-regime alpha
  - Catching up on caching old rounds (fresh state file)
- ml-churn: IDLE (available for temperature calibration)

## What Changed This Session
A. Hail Mary plan: 51 features, deep analysis, tournament (completed)
B. Observation Intelligence: proxy features from observations (R2 gate passed)
C. Multi-seed observation: 9 queries per seed, all 5 seeds get full coverage
D. Bug fixes: per-regime alpha, calibration regime tag, replay resubmission
E. Killed churn (zero improvement over defaults)
F. R18 post-mortem: explosive growth OOD, not regime misclassification

## In Progress
- Temperature calibration (temperature_calibration.py written, not yet run)
- Plan includes: per-regime models, physics prior, model ensemble

## Next Steps
1. Run temperature calibration (LOO-CV)
2. Deploy temperature + v5 multi-seed for R19
3. Investigate OOD handling for extreme growth rounds
4. Feature freeze Sunday 09:00 CET
5. Competition ends Sunday 15:00 CET
