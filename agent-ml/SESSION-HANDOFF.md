# ML Session Handoff -- 2026-03-21 17:30 CET

## Score: 169.6 weighted (R15=81.6). Rank 141. Top 1 is 196.6.

## What's Submitted
- R16 active (closes 18:46 CET). V4 + 50 trees + alpha=20 + deep stack seed 1. Death regime.

## What's Running
- ml-churn: churn_v4 optimizing LightGBM hyperparams (found 50 trees > 200 trees)
- ml-brain: idle (V5 comparison finished, failed)
- overnight_v3: PAUSED (manual control)

## Key Finding This Session
- Brain V4 (LightGBM) = +6.2 points over V3 on R14 real data
- 50 trees = +5.5 points over 200 trees on R15 real data
- Deep stack all seeds 80+ (R15: 82.4, 80.1, 82.3, 80.9, 82.2)
- V4-R (replay-trained) and V5 (stepper) both FAILED (-41, -43). Dead approaches.
- Replay API discovered: FREE year-by-year data, 69/70 cached

## Round Workflow Checklist (DO THIS EVERY ROUND)
1. Cache previous round ground truth + replay
2. Run hindsight on previous round
3. Sync new data to GCP
4. Check churn_v4 for better params
5. Smell test new round (5 queries)
6. Deep stack rotating seed (R17=seed 2)
7. Test variants against most recent real data
8. Submit winner
9. Resubmit if churn finds better during window

## Next: R17
- Deep stack seed 2
- Use churn_v4 best params (currently n_est=50, leaves=31, lr=0.05, alpha=20)
- Test against R16 ground truth before submitting
