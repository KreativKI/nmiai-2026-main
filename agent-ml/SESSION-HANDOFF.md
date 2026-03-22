# ML Session Handoff -- 2026-03-22 01:30 CET

## Score: R18=28.6 (worst). R19 pending (v5 multi-seed, death regime).
## Total weighted: ~1603 + R18(68.9) = ~1672

## What's Running
- ml-brain: overnight_v5 (multi-seed observation, cron watchdog active)
- ml-churn: IDLE
- R19 submitted at 00:09 UTC with death regime classification

## Critical Finding: Game Progression (JC's hypothesis CONFIRMED)

Growth rounds are escalating in magnitude over time:
```
R6:  1.6x growth    score=70
R7:  2.3x           score=55
R11: 3.3x           score=69
R12: 4.0x           score=50
R14: 5.8x           score=68
R18: 11.6x          score=29   <-- all-time low
```

Correlation: R=-0.802 between growth_rate and our score.
Our 80+ scores (R9=82.6, R15=81.6) were both death rounds.
Death = predictable. Growth = escalating challenge.

## R18 Post-Mortem (from actual data)
- Regime: growth (correctly classified)
- Growth: 11.6x (2602 new settlements). Training max was 4.8x.
- All 5 seeds showed 12-15x growth in replays
- Model was out-of-distribution by 2.4x
- Problem: model can't extrapolate to unseen growth magnitudes

## Temperature Calibration Result
- T=1.05 optimal, +0.1 improvement (negligible)
- NOT the fix needed. The model is well-calibrated for seen data.

## What Was Built This Session
- overnight_v5.py: multi-seed observation (all 5 seeds get full maps)
- deep_analysis.py: 8 hypotheses validated on 80 replays
- build_dataset.py: 51 features (up from 32)
- evaluate.py: LOO-CV framework
- transition_model.py: 1.77M transition tables
- observation_analysis.py: proxy correlation gate
- feature_importance.py: 51-feature breakdown
- temperature_calibration.py: per-regime T search
- model_a_lgbm.py: multiclass attempt (failed, 26.3)
- model_c_camarkov.py: CA-Markov attempt (failed, 19.0)

## Open Questions for Next Session
1. How to handle escalating growth? The model can't extrapolate.
   Options: log-transform obs_settle_growth, dynamic alpha based on magnitude,
   or direct use of observed terrain as stronger signal.
2. R19 score will test multi-seed observation (first v5 round)
3. Should we pivot strategy based on game progression?
4. Competition ends 15:00 CET. Feature freeze 09:00 CET.
