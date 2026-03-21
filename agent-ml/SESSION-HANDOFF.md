# ML Session Handoff -- 2026-03-21 22:15 CET

## Score: R17=67.9 (weighted 155.7). R18 submitted (pending).

## What's Running
- ml-brain: overnight_v4 restarting via cron with 51-feature build_dataset.py
- Will resubmit R18 with 51 features when it restarts
- Hard constraints (port-coastal, ruin-cap) already in overnight_v4

## What Happened This Session
- Built deep_analysis.py: validated 8 hypotheses on 80 replays
  - Empty never becomes Forest, Ports 100% coastal, Ruins 1yr lifespan
  - Transition matrix reveals Settlement->Ruin->Forest/Empty/Settlement lifecycle
- Extended build_dataset.py: 32 -> 51 features
  - Year-10 wealth/defense, Year-25 full stats, survival tracking
  - Round-level trajectory features (growth rates, wealth decay, faction consolidation)
- Built evaluation framework (evaluate.py): leave-one-round-out CV
- Built transition_model.py: 1.77M transitions, 4-level hierarchical fallback
- Tested 3 models in tournament:
  - 51-feat regressors: 78.1 (WINNER)
  - Multiclass LightGBM: 26.3 (FAILED - argmax destroys probability info)
  - CA-Markov: 19.0 (FAILED - static neighborhoods, averaged transitions)
- Deployed 51-feature build_dataset.py to GCP
- Plan went through 4 audit rounds before approval

## Key Learning
Multiclass classification is WRONG for probabilistic prediction with KL scoring.
The ground truth is a probability distribution, not a hard class. Regressing
each class probability independently (6 regressors) then floor+renormalize
preserves the distribution information that the scoring formula rewards.

## Data Status
- 85 replays locally (17 rounds, R17 seed4 missing)
- 17 ground truth files
- All synced to GCP

## Next Session
- Verify R18 resubmission with 51 features worked
- Check churn_v4 compatibility with 51 features (may need update)
- Consider: can we improve further? Feature importance analysis would show
  which of the 51 features actually matter
- Feature freeze Sunday 09:00 CET
