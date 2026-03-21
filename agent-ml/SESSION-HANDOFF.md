# ML Session Handoff — 2026-03-21 11:00 CET

## Critical Context
- Team: Kreativ KI, rank 171, weighted score 128.1
- Leaderboard = best (round_score x round_weight). NOT just best score.
- Later rounds worth MORE. R14 weight 1.98, R15 ~2.08.
- To beat current best: need 64.7 on R14 or 61.6 on R15.
- Top 10 teams at ~175 weighted. We need ~88 on R14 to match.
- Competition ends Sunday 15:00 CET (~28h left).

## R14 Status
- Active, closes 12:59 CET
- Growth regime, all 5 seeds observed (from overnight runner)
- Submitted with V3+obs+churned params. Calibrated estimate ~66.
- If actual score > 64.7, it becomes our new best weighted score.

## GCP (ml-churn VM, 35.187.42.205)
- overnight_v2.py: running, handles rounds automatically
- churn_v2.py: running, continuous param optimization
- Cron: every 15 min restarts crashed processes
- Brain V3 backtest: 72.86 (calibrated ~66)

## Automation Improvements Needed for Tonight
1. **Two-track comparison:** Run both V2 (deep stack) and V3 (regime) predictions for each round. Submit whichever has better calibrated score. Not yet implemented.
2. **Calibrated scoring:** Churn optimizes raw backtest score. Should optimize calibrated score (backtest - 7). Adjust churn_v2.py objective function.
3. **Settlement stats:** /simulate returns population, food, wealth, defense, owner_id. We're not using these. Low food = more likely to die. Could improve predictions.
4. **Deep stack vs spread:** V9 (deep stack seed 0) may score better for certain regime types. Run both strategies and compare.
5. **Leaderboard-aware submission:** Since later rounds have higher weight, optimize for maximum weighted_score not just score.

## Files
- astar_v9.py: Chef v9 (V2+smell test+deep stack). Built, not yet proven.
- overnight_v2.py: Current runner (V3 regime + churn params).
- churn_v2.py: Continuous optimizer. Finds better alphas/temps/collapse/sigma.
- brain_v3.py: Per-terrain alpha fitting with scipy.optimize.
- regime_model.py: Regime-specific transition tables.

## Calibration Data
Backtest overshoots by +7 avg (std 14.6).
Death rounds overshoot most (+15-27). Growth can undershoot (-5 to -10).
RULE: Never trust backtest improvement without actual round confirmation.

## What Worked (R9 = 82.6, our best raw score)
- V2 NeighborhoodModel (global, NO regime forcing)
- All 50 queries on seed 0 (deep stacking)
- Dirichlet blending ps=12
- T=1.12, collapse=0.016, sigma=0.3

## What V3 Regime Model Does Better
- Wins 10/13 rounds in simulation
- +5.6 avg over V2
- But destroyed R9 (-29 points) and is volatile

## Recommended Strategy
Run both V2 and V3 in parallel on GCP. After each round scores, compare actual performance. Submit whichever model type won the most recent rounds.
