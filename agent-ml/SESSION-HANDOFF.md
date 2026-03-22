# ML Session Handoff -- 2026-03-22 09:15 CET

## CRITICAL: Competition ends 15:00 CET today. ~5.75 hours left.

## Current Score
Total weighted: 2326.3. R22 active (95 min left, already submitted).

| Round | Score | Rank | Model |
|-------|-------|------|-------|
| R17 | 67.9 | 179 | v4 32-feat |
| R18 | 28.6 | 214 | v4 51-feat (OOD growth 11.6x) |
| **R19** | **85.3** | **102** | **v5 multi-seed** |
| **R20** | **82.8** | **92** | **v5 multi-seed** |
| **R21** | **78.7** | **155** | **v5 multi-seed** |
| R22 | pending | - | v5 multi-seed + OOD fix |

## What's Running
- ml-brain: overnight_v5.py with cron watchdog (~/start_v5.sh)
- ml-churn: IDLE
- Cron: `*/15 * * * * pgrep -f overnight_v5.py > /dev/null || bash ~/start_v5.sh`

## overnight_v5 Features (deployed, working)
- Multi-seed observation: 9 queries/seed x 5 seeds = full grid coverage
- 51 features with trajectory proxies from observations
- obs_settle_growth on ALL seeds (not just deep seed)
- Per-regime Dirichlet alpha (death=5, stable=30, growth=15)
- Dynamic alpha=3 for extreme growth (avg_growth > 5.0)
- OOD cap: obs_settle_growth capped at training max (y25=4.846, y10=2.062)
- Regime reclassification from 5-seed average
- Hard constraints (port-coastal, ruin-cap)
- Replay resubmission when replay data appears
- All code in: agent-ml/solutions/overnight_v5.py

## Key Files on GCP (ml-brain)
- ~/solutions/overnight_v5.py (production)
- ~/solutions/build_dataset.py (51 features)
- ~/solutions/data/ground_truth_cache/ (20+ rounds)
- ~/solutions/data/replays/ (85+ replay files)
- ~/solutions/data/master_dataset.npz (122K+ rows x 51 features)
- ~/overnight_v5.log (production log)
- ~/start_v5.sh (startup script)
- ~/overnight_v5_state.json (state: submitted rounds, cached rounds)

## Key Files Local
- agent-ml/solutions/overnight_v5.py (production code)
- agent-ml/solutions/build_dataset.py (feature extraction, 51 features)
- agent-ml/solutions/evaluate.py (LOO-CV framework)
- agent-ml/solutions/deep_analysis.py (8 hypotheses validated)
- agent-ml/solutions/transition_model.py (1.77M transitions)
- agent-ml/solutions/observation_analysis.py (proxy correlation gate)
- agent-ml/solutions/feature_importance.py (51-feature breakdown)
- agent-ml/solutions/temperature_calibration.py (tested, negligible +0.1)
- agent-ml/solutions/audit.py (persistent unbiased auditor)
- agent-ml/plan.md (current plan)

## Critical Findings This Session

### Game is escalating growth rounds
Growth magnitude over time: R6=1.6x, R7=2.3x, R11=3.3x, R12=4.0x, R14=5.8x, R18=11.6x
Correlation R=-0.802: more growth = worse score.
OOD fix deployed: cap at training max + dynamic alpha.

### Multi-seed was the biggest win (+19 points)
Spreading 50 queries across all 5 seeds instead of deep-stacking 1 seed.
R19-R21 averaged 82.3, up from 63.4 pre-v5.

### What failed
- Multiclass LightGBM: 26.3 (argmax destroys probability info)
- CA-Markov: 19.0 (static neighborhoods, averaged transitions)
- Temperature calibration: +0.1 (negligible)

### What wasn't completed
- Per-regime specialized models (audit said too risky for final hours)
- Physics prior (transition model as Dirichlet base)
- Model ensemble
- Audit suggested: post-hoc bias correction per regime (simpler than per-regime models)

## Remaining Plan (from plan.md)
1. Monitor R22+ (v5 autonomous)
2. Per-regime bias correction (10 lines, quick win per audit #9)
3. Keep improving until 15:00 CET, no feature freeze

## GCP Access
```
gcloud compute ssh ml-brain --zone=europe-west1-b --project=ai-nm26osl-1779
gcloud compute ssh ml-churn --zone=europe-west1-b --project=ai-nm26osl-1779
```

## Git
Branch: agent-ml
Worktree: /Volumes/devdrive/github_dev/nmiai-worktree-ml/
All changes pushed to origin/agent-ml.
