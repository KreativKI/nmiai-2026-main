# ML Session Handoff -- 2026-03-22 15:00 CET (COMPETITION ENDED)

## Final Score
R23: 61.8 (growth regime, alpha=6). Our worst round.
Total weighted: ~234 + R23 contribution. Rank: ~#150 range.

## Score History (all rounds)

| Round | Score | Rank | Model | Notes |
|-------|-------|------|-------|-------|
| R9 | 82.6 | 93 | V2 deep stack | |
| R14 | 67.8 | 95 | V3+V2 blend | |
| R15 | 81.6 | 137 | V4 32-feat | |
| R16 | 57.0 | 203 | V4 32-feat | |
| R17 | 67.9 | 179 | V4 32-feat | |
| R18 | 28.6 | 214 | V4 51-feat | OOD growth 11.6x |
| R19 | 85.3 | 102 | V5 multi-seed | |
| R20 | 82.8 | 92 | V5 multi-seed | |
| R21 | 78.7 | 155 | V5 multi-seed | |
| R22 | 80.0 | 104 | V5 multi-seed | |
| R23 | 61.8 | ? | V5 + alpha=6 | RESUBMITTED with wrong alpha |

## What Happened in Final Session

### What we built
- overnight_v6.py: MLP ensemble + RegimeModel + spatial features + cross-seed stats + alpha tuning
- Backtest showed V6 was -0.2 vs V5. Not deployed.
- Tested 3 patches (obs proxies +0.2, temperature -12.6, blur -0.5). Not deployed.
- Alpha brute-force search: found death=15, stable=12, growth=6 as "optimal"
- Resubmitted R23 with alpha=6 (was 15)

### The Critical Mistake
Alpha search ran LOCALLY with simulated observations (ground truth argmax).
Perfect observations make low alpha look good (trust obs more).
Real observations are NOISY (single Monte Carlo sample) and need HIGHER alpha.

When we ran the same search on GCP with REAL observation files (R19-R22):
- Death optimal: alpha=25 (not 15)
- Pattern: noisy obs need MORE model trust, not less

We lowered growth alpha from 15 to 6 (trusting noisy observations more).
We should have RAISED it. R23 likely scored worse because of our resubmission.

The original V5 submission with alpha=15 would have scored ~80+ based on R19-R21 pattern.

### Root Causes
1. Ran alpha search on wrong machine (local with 18 rounds, not GCP with 22 rounds)
2. Used simulated observations (GT argmax) instead of real saved observations
3. Didn't validate the direction of the finding (lower alpha = trust obs more, but obs are noisy)
4. Time pressure led to deploying without cross-checking the logic
5. ml-churn VM sat idle the entire session

### Key Learnings for Post-Mortem
- The gap between "simulated backtest" and "real production" is where mistakes hide
- Always run optimization on the SAME data source as production
- Question the direction of findings, not just the magnitude
- Use ALL available compute (ml-churn was idle for 4 hours)
- The boring infrastructure work (syncing data between machines) matters more than fancy models
