# Astar Island Norse World Prediction — Rules

**Source:** Competition docs fetched 2026-03-20 00:00 CET
**Last verified:** 2026-03-20 00:00 CET
**Track weight:** 33.33% of total score
**Change log:** (append here when rules change)
- 2026-03-20 00:00: Initial rules populated from competition docs

## Submission
- Submit predictions via REST API (not file upload)
- Must submit ALL 5 seeds every round. Missing seed = 0 for that seed.
- Rounds repeat every ~3 hours 5 minutes
- Later rounds weighted more: +5% per round

## API
- **Base URL:** https://api.ainm.no/astar-island/
- **Auth:** JWT token (extract access_token from browser cookies after login at app.ainm.no)
- **Timeout:** 60 seconds per API call

## Observation Budget
- 50 queries per round, shared across all 5 seeds
- Each query reveals a viewport of max 15x15 cells
- Query costs 1 from budget regardless of viewport size
- Map is 40x40 cells

## Prediction Format
- 3D array: prediction[y][x][class] -- 40 rows x 40 columns x 6 classes
- Each cell's 6 probabilities MUST sum to 1.0 (tolerance: +/- 0.01)
- All probabilities MUST be non-negative
- Class indices: 0=Empty, 1=Settlement, 2=Port, 3=Ruin, 4=Forest, 5=Mountain

## CRITICAL: Probability Floor
NEVER assign probability 0.0 to any class. If ground truth has non-zero probability for a class you marked as 0, KL divergence becomes infinite and destroys your score for that cell.

**Solution:** Floor ALL probabilities at 0.01, then renormalize: `probs = probs / probs.sum()`

## Scoring
- Metric: entropy-weighted KL divergence
- Score = 100 * exp(-KL_divergence)
- Range: 0 (worst) to 100 (perfect)
- Only dynamic cells contribute (those that change between simulation runs)
- Higher entropy cells weighted more
- Per-round score: average of 5 seed scores
- Leaderboard: best round score of all time

## World Details
- 6 terrain classes: Empty(0), Settlement(1), Port(2), Ruin(3), Forest(4), Mountain(5)
- Mountains and ocean are STATIC (never change)
- Forests are mostly static (can be cleared or regrow)
- Settlements, ports, ruins are DYNAMIC (where the score is won)
- Hidden parameters control world behavior, same for all 5 seeds in a round
- Different between rounds

## Round Lifecycle
- Active: observation window open, can query and submit
- Scoring: predictions being evaluated
- Completed: final scores published, analysis endpoint available

## Post-Round Analysis
- After round completes: GET /analysis/{round_id}/{seed_index}
- Returns ground truth and scoring breakdown
- Use this to improve your model for next round

## Competition-Wide Rules
- AI tools allowed
- No sharing solutions between teams
- No hardcoded responses
- Repo goes public at Sunday 14:45
- Deadline: Sunday March 22, 15:00 CET
