# ML Session Handoff -- 2026-03-21 23:50 CET

## Score: R17=67.9. R18 pending (51-feat + obs proxies + regime reclassification).

## What's Running
- ml-brain: overnight_v4 with full pipeline (51 features, obs proxies, regime reclassification)
- churn: KILLED (produced zero improvement over defaults, wasted compute)
- Cron watchdog still active for overnight_v4

## What Happened This Session

### Hail Mary Plan (4 audit rounds, approved)
A. Extended build_dataset.py from 32 to 51 features
   - Year-10 wealth/defense, Year-25 full stats, survival tracking
   - Round-level trajectory features (growth rates, wealth decay, factions)
   - All features have prediction-time defaults

B. Built evaluation framework (evaluate.py)
   - Leave-one-round-out CV: baseline scores 78.1

C. Tested 3 model approaches:
   - 51-feat regressors: 78.1 (WINNER)
   - Multiclass LightGBM: 26.3 (FAILED, argmax destroys probability info)
   - CA-Markov: 19.0 (FAILED, static neighborhoods)

D. Feature importance analysis: top features are ALL trajectory-based
   - 61% of importance is replay-only (defaults to 1.0 at prediction time)
   - This is the architectural ceiling

### Observation Intelligence Plan (2 audit rounds, approved)
E. Correlation analysis: 4 observation proxies passed R2 >= 0.5 gate
   - obs_settle_growth vs settle_growth_y25: R2=0.807
   - obs_settle_growth vs settle_growth_y10: R2=0.660
   - obs_settle_growth vs faction_consol_y10: R2=0.576
   - obs_forest_ratio vs settle_growth_y25: R2=0.775

F. Implemented obs proxies in overnight_v4.py
   - Counts observed settlements from deep-stacked observations
   - Computes obs_settle_growth and injects into trajectory features
   - OOD guard: falls back to default if > 2x training max

G. Regime reclassification from full-grid observations
   - Uses calibrated thresholds (death<0.9, growth>1.4) instead of 5-cell smell test
   - Already corrected R18: smell test said "stable", obs said "growth" (6.25x)

### Infrastructure
H. deep_analysis.py: 8 hypotheses validated on 80 replays
I. transition_model.py: 1.77M transitions, 4-level hierarchical fallback
J. observation_analysis.py: correlation gate for proxy validation
K. feature_importance.py: 51-feature importance breakdown
L. All data complete: 17 rounds GT, 85 replays

## Key Learnings
- Multiclass LightGBM is WRONG for probabilistic prediction with KL scoring
- CA-Markov can't compete with discriminative models
- 61% of model importance is replay-only features (architectural ceiling)
- Observation-derived proxies can fill ~24% of the gap (settle_growth features)
- Regime reclassification from full-grid obs is better than 5-cell smell test
- Churn produced zero improvement over defaults (killed)

## Data on GCP
- 17 rounds GT + 85 replays (all complete)
- 51-feature master dataset (115K rows)
- Obs data saved for R16-R18

## Next Session
- Check R18 score (first round with obs proxies + regime reclassification)
- If obs proxies helped: the approach is validated
- If not: check if OOD guard triggered or regime was already correct
- Feature freeze Sunday 09:00 CET
- Competition ends Sunday 15:00 CET
