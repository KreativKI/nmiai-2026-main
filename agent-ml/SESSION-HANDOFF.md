# ML Session Handoff -- 2026-03-21 11:50 CET

## Critical Context
- Team: Kreativ KI, rank 171, weighted score 128.1
- Best: R9 = 82.6 (weighted 128.1). Later rounds worth more.
- To beat R9 weighted: need 64.7 on R14 or 61.6 on R15.
- Competition ends Sunday 15:00 CET (~27h left).

## What Just Got Deployed (v3 upgrade)
Three improvements running in parallel on GCP ml-churn VM:

1. **Dual V2+V3 blend:** overnight_v3 generates BOTH V2 (global, won R9) and V3 (regime) predictions, blends them weighted by backtest. Currently V3=70%/V2=30% (default). After R14 scores, self-improvement will set data-driven weights. Local test shows V3=51%/V2=49% -- blend hedges V3 volatility.

2. **Settlement stats:** /simulate returns population, food, wealth, defense per settlement. overnight_v3 saves these during observation. Used to cross-check regime detection. Stats accumulate over rounds.

3. **Calibrated churn:** churn_v3 optimizes for estimated REAL score, not raw backtest. Death rounds penalized (backtest overshoots +20), growth rounds boosted (backtest undershoots -5).

## R14 Status
- Active, closes 12:59 CET
- Growth regime, all 5 seeds observed (48/50 queries)
- Submitted by overnight_v2 (before swap to v3). V3 regime model.
- When R14 closes: overnight_v3 will cache ground truth, run self-improvement (which compares V2 vs V3 and sets blend weights), prepare for R15.

## GCP (ml-churn VM, 35.187.42.205)
- overnight_v3.py: PID 33715, --continuous --interval 300
- churn_v3.py: PID 33755, continuous
- Cron: every 15 min restarts crashed processes
- Log files: ~/overnight_v3.log, ~/churn_v3.log

## Files (new in v3)
- overnight_v3.py: Dual-track + settlement stats + calibrated self-improvement
- churn_v3.py: Calibration-aware parameter optimization
- data/model_weights.json: V2/V3 blend weights (created after first self-improvement)
- data/settlement_stats/: Per-round settlement health data

## Calibration Data
Backtest overshoots by +7 avg (std 14.6).
Death: +20. Growth: -5. Stable: +7.
RULE: Never trust backtest improvement without actual round confirmation.

## What Worked (R9 = 82.6, our best raw score)
- V2 NeighborhoodModel (global, NO regime forcing)
- All 50 queries on seed 0 (deep stacking)
- Dirichlet blending ps=12, T=1.12, collapse=0.016, sigma=0.3

## Next Steps
1. Monitor R14 score (closes 12:59 CET)
2. Verify overnight_v3 self-improvement creates model_weights.json
3. Check R15 submission uses blended V2+V3
4. Watch churn_v3 for calibrated score improvements
