# ML Session Handoff -- 2026-03-21 19:50 CET

## Score: 169.6 weighted (R15=81.6). Rank 167. Top 1: 196.6.

## What's Running (DON'T TOUCH, both autonomous)
- ml-brain: overnight_v4 (V4 32-feat, handles rounds, caches data, rebuilds dataset)
- ml-churn: churn_v4 (32-feat hyperparameter search)
- Both have cron watchdogs. Both use reviewed + simplified code.

## What Happened This Session
- Built Brain V4 (LightGBM, 32 features from replay data). +6.2 over V3 on real data.
- Discovered /replay API: FREE year-by-year simulation data. 80 replays cached.
- Built master dataset (102K rows x 32 features).
- R15: 81.6 (V4 + deep stack). R16: 57.0 (chaotic round, model struggled).
- Audit scored operations 3/10. Fixed: deployed overnight_v4 + updated churn_v4.
- Full Boris workflow on all 3 core files (review + simplify + validate).

## NEXT SESSION PRIORITY: Deep Analysis
The competition briefing identified hidden rules from 8 rounds.
We have 16 rounds of replays now. These rules are UNVALIDATED.

File: /Users/jcfrugaard/Downloads/OVERSEER-BRIEFING-ASTAR-DEEP-ANALYSIS.md

Task: write deep_analysis.py, run on GCP, validate all hypotheses.
Results feed into V4 hard constraints and feature engineering.
See plan.md for the 8 hypotheses.

## Key Learnings
- R9 and R15 scored 80+ because dynamics were PREDICTABLE (clear growth)
- R16 scored 57 because dynamics were CHAOTIC (ambiguous, mixed outcomes)
- Score depends more on hidden parameters than model quality
- Deep-stacked seed can score WORSE than model-only on chaotic rounds (R16)
- 50 trees beats 200 trees (less overfitting with small training data)
