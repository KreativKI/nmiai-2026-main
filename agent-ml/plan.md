# Astar Island -- Final Plan

**Updated:** 2026-03-22 08:45 CET
**Deadline:** Sunday 2026-03-22 15:00 CET (6 hours remaining)
**NO FEATURE FREEZE.** We keep improving until competition ends.
**Current:** R22 active. Total weighted: 2326.3. R19-R21 avg: 82.3.

## System Status

overnight_v5 on ml-brain: RUNNING, autonomous, cron watchdog active.
Multi-seed observation (9 queries/seed, all 5 seeds mapped).
51 features, obs proxies, per-regime alpha, hard constraints.

## Persistent Auditor

audit.py provides a consistent unbiased auditor with:
- Fixed system prompt (no drift between audits)
- Audit history tracked in data/audit_history.json
- Always reads plan.md + CLAUDE.md + specified files
- Spawn with: feature-dev:code-architect using audit.build_prompt()

## Priority 1: OOD Growth Fix (NOW)

Two surgical changes to overnight_v5.py. Only affect extreme growth rounds.
Death and stable rounds (our 82.3 average) are untouched.

### Change A: Cap obs_settle_growth at training max
Current code passes raw obs values up to 9.7, but the model was trained
on values up to 4.8. Above 4.8 the model extrapolates badly. Above 9.7
the proxy is dropped entirely and defaults to 1.0 (signals "stable").

Fix: cap at 4.8 (training max). The model predicts as if growth is 4.8x.
Wrong, but the most informed wrong prediction the model can make.

```python
TRAIN_MAX_SETTLE_GROWTH = 4.8
traj["settle_growth_y25"] = min(obs_growth, TRAIN_MAX_SETTLE_GROWTH)
traj["settle_growth_y10"] = min(obs_growth, TRAIN_MAX_SETTLE_GROWTH)
```

### Change B: Dynamic alpha for extreme growth
When avg_growth > 5.0: alpha=3 (trust observations almost entirely).
The model is wrong for extreme growth. Observations show actual terrain.

```python
avg_growth = float(np.mean(growth_ratios)) if growth_ratios else 1.0
if regime == "growth" and avg_growth > 5.0:
    alpha = 3
elif regime == "growth":
    alpha = 15
elif regime == "death":
    alpha = 5
else:
    alpha = 30
```

### Expected impact
- Death/stable rounds: zero change (protected)
- Moderate growth rounds: zero change (obs_growth < 4.8)
- Extreme growth rounds (like R18): +10-20 points (trust obs over broken model)

## Priority 2: Per-Regime Models

Train 3 separate LightGBM model sets (death, stable, growth).
Each model specializes in its regime's dynamics.
Dispatch based on detected regime.

This eliminates the calibration compromise:
- Death: +15.6 point backtest offset (model too optimistic)
- Stable: +13.4
- Growth: +5.5

Separate models would calibrate each regime independently.

### Implementation
- Modify predict_and_submit_v2 to train 3 model sets
- Select model set after regime classification
- Backtest on 20 rounds before deploying

## Priority 3: Continued Improvements

### A. Log-transform settle_growth in training
Currently settle_growth_y25 ranges from 0.17 to 4.85 in training.
Log-transforming would make the feature distribution more uniform
and help the model handle the full range better.
Requires retraining with log-transformed feature + matching transform
at prediction time.

### B. More obs-derived features
obs_forest_ratio (R2=0.78) is computed but not injected.
obs_ruin_count could signal regime (should be near zero at year 50).

### C. Adaptive query strategy per regime
After the first 9 queries reveal regime:
- Death: remaining 5 extras spread across seeds (confirm all dying)
- Growth: remaining 5 on seed with most settlements (best obs signal)
- Stable: remaining 5 on seed 0 (deep stack for uncertain regime)

## Execution

```
NOW:      OOD growth fix (Priority 1, Change A+B)
          -> Boris review -> deploy -> verify on R22
THEN:     Per-regime models (Priority 2)
          -> Boris full cycle -> backtest -> deploy if better
ONGOING:  Monitor rounds, iterate improvements
          -> Each change through Boris + persistent auditor
```

No feature freeze. Each improvement deployed when validated.
overnight_v5 is the safety net throughout.
