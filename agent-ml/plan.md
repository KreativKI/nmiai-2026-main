# Astar Island -- Final Hours Plan

**Created:** 2026-03-22 08:30 CET
**Deadline:** Sunday 2026-03-22 15:00 CET (6.5 hours remaining)
**Feature freeze:** 09:00 CET (30 min from now)
**Current score:** 2326.3 total weighted | R19=85.3, R20=82.8, R21=78.7
**R22:** Active, ~100 min left

## What's Working (don't break)

overnight_v5 on ml-brain:
- Multi-seed observation (9 queries/seed, all 5 seeds mapped)
- 51 features with trajectory proxies from observations
- Per-regime Dirichlet alpha (death=5, stable=30, growth=15)
- Regime reclassification from 5-seed average obs_settle_growth
- Hard constraints (port-coastal, ruin-cap)
- Replay resubmission when replay data appears
- Cron watchdog active

R19-R21 averaged 82.3 (up from 63.4 pre-v5). The multi-seed change
gave us +19 points. This is working. Protect it.

## What Was Completed

| Item | Status | Result |
|------|--------|--------|
| 51-feature extension | Done | 32 -> 51 features |
| Multi-seed observation (v5) | Done | +19 point average lift |
| Obs proxy (settle_growth) | Done | R2=0.81, deployed |
| Per-regime Dirichlet alpha | Done | death=5, stable=30, growth=15 |
| Regime reclassification | Done | From full-grid obs, 77% accuracy |
| Hard constraints | Done | Port-coastal, ruin-cap |
| Replay resubmission | Done | Resubmit with 100% features after round closes |
| Deep analysis (8 hypotheses) | Done | Transition matrices, hidden rules |
| Evaluation framework | Done | LOO-CV, baseline 78.1 |
| Temperature calibration | Tested | +0.1, negligible, NOT deployed |
| Model A (multiclass) | Tested | 26.3, FAILED |
| Model C (CA-Markov) | Tested | 19.0, FAILED |
| Game progression analysis | Done | Growth escalating: R=-0.802 |
| R18 post-mortem | Done | OOD growth 11.6x, training max 4.8x |

## What Was NOT Completed

| Item | Why | Impact |
|------|-----|--------|
| Physics prior (transition model as Dirichlet base) | Deprioritized for multi-seed | Medium |
| Per-regime specialized models | Not implemented | Medium |
| Model ensemble | Only one model type works (LightGBM regressors) | Low |
| Backtest of v5 vs v4 | Went live directly, validated by R19-R21 scores | N/A (validated live) |
| OOD growth handling | Identified problem, no fix deployed | High for growth rounds |

## Known Weaknesses (from data, not guessing)

### A. Growth rounds score worse as magnitude increases
```
R6:  1.6x growth  score=70
R7:  2.3x         score=55
R11: 3.3x         score=69
R12: 4.0x         score=50
R14: 5.8x         score=68
R18: 11.6x        score=29
```
Correlation R=-0.802. The game is escalating growth magnitude.
Our model can't extrapolate beyond its training range (max 4.8x).

### B. obs_settle_growth is noisy for extreme rounds
R18 seed 3: we measured 6.25x from observations, actual was 12.87x.
Single Monte Carlo samples underestimate extreme growth because
the average of hundreds of simulations shows more growth than any
single simulation.

### C. 4 trajectory features still default to 1.0 for all seeds
wealth_decay, faction_consol, pop_trend, food_trend cannot be
computed from terrain observations. Combined 24.3% importance.
No fix possible without observing settlement stats (not in API).

## Remaining Improvements (prioritized by expected impact)

### 1. Per-regime models (estimated +3-5 points)
Train separate LightGBM model sets per regime.
Death model only sees death training data.
Growth model only sees growth training data.
Eliminates the compromise in calibration offsets.
Risk: small per-regime datasets (20-30K rows each).

### 2. OOD growth handling (estimated +5-10 on growth rounds)
When obs_settle_growth > training max (4.8), the model receives
an out-of-distribution input and produces wrong predictions.
Options:
- Log-transform obs_settle_growth before injecting (compresses extremes)
- Cap at training max (loses extreme signal)
- Dynamic alpha: lower alpha when growth is extreme (trust obs more)
- Use observed terrain directly for cells with clear observations

### 3. Physics prior for non-observed cells
Use transition_model.py predictions as Dirichlet prior instead of
LightGBM for cells where observations are sparse or zero.
The transition model knows spatial mechanics (settlements expand
into forests, ports only coastal, ruins transitional).

### 4. Feature pruning
Remove zero-importance features (n_ruin, is_coastal, survived_y25).
Reduces noise without losing signal.

## What Stays Running

overnight_v5 on ml-brain handles all rounds autonomously.
Any new code deploys alongside v5, not replacing it, until validated.
Feature freeze at 09:00 means no new features after that, only
parameter tuning and hard constraint adjustments.

## Execution

Each improvement follows Boris workflow.
Audit gate before any deployment to ml-brain.
overnight_v5 is the safety net throughout.
