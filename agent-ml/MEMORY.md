# ML Track Memory

## Session 3: 2026-03-20 02:00-02:15 UTC

### State
- Round 3 active, closes 02:53 UTC. Weight: 1.1576
- All 5 seeds submitted (twice: first v3 at 00:08, then v4 at 02:12)
- 50/50 queries used (37 from v3, 13 from v4)
- Rounds 1-2: MISSED (0 seeds submitted, no scores)
- No score yet (round 3 not yet scored)

### Experiment 1: v4 observation + resubmit
**Date:** 2026-03-20 02:10 UTC
**Round:** 3
**Approach:** v4 (learned transitions + 13 targeted observations on seed 0)
**Change:** Used 13 remaining queries on seed 0 dynamic regions, tried to blend observations
**Hypothesis:** Round-specific observations should improve predictions vs transition-only model
**Score before:** unknown (round 3 first submission)
**Score after:** pending (round not yet scored)
**Delta:** unknown
**Kept/Reverted:** kept (submitted)
**Time spent:** 0.25h
**Notes:** Broadcasting bug (obs_total shape 40x40 vs obs_counts 40x40x6) crashed script after queries were spent. Observations LOST. Fixed bug, resubmitted with transition model only. Lesson: ALWAYS dry-run with synthetic observation data before spending real queries.

### Experiment 2: v4 transition-only resubmit
**Date:** 2026-03-20 02:12 UTC
**Round:** 3
**Change:** Resubmitted all 5 seeds with learned transition model (no observations)
**Notes:** Predictions are from rounds 1-2 ground truth transitions. Neighborhood-aware (near/far settlement context). Avg confidence ~77%.

### Learned Transitions (from rounds 1-2 ground truth)
- Empty -> Empty 79%, Settlement 14%
- Settlement -> Settlement 40%, Empty 37%
- Port -> Empty 37%, Port 30%
- Forest -> Forest 70%, Settlement 18%
- Mountain -> Mountain 95%
- Near settlements: Empty -> Settlement 21% (higher than far: 12%)

### Key Issues
- Ruin/Port/Settlement "near" transitions show 16.7% uniform (Laplace smoothing default due to few samples)
- Round 2 seed 1 had 23 settlements -> empty (mass die-off). Hidden params vary significantly between rounds.
- Without round-specific observations, our predictions may not match round 3's dynamics well.

### Round 4 Plan
1. Fix the broadcasting bug (DONE in v4.py)
2. When round 4 opens: use ALL 50 queries strategically
   - Concentrate on seed 0: 20 queries (multiple samples per area for probability estimates)
   - Seed 1: 15 queries
   - Seed 2: 10 queries
   - Seeds 3-4: 5 queries combined (rely on cross-seed transfer)
3. Build round-4-specific transition model from observations
4. Blend with rounds 1-2 learned model (lower weight as we get round-specific data)
5. After round 3 scores: analyze ground truth, identify error patterns

### Rules re-read at 2026-03-20T02:00:00Z. No violations found.

### Ground Truth Analysis (rounds 1-2)
- Only 10-40 out of 1600 cells change dominant class (97-99% stay same)
- Round 1: 18-40 changes per seed (avg ~29)
- Round 2: 10-28 changes per seed (avg ~21)
- Most changes: settlements dying (-> empty), settlements growing (empty -> settlement)
- Scoring is on probability distributions, not argmax. Must match distribution shape.
- High-entropy (uncertain) cells weighted more in scoring.

### Experiment 3a: v6 phased observation (round 4, first submit)
**Score after:** 71.77 (rank #49)
**Seeds:** 0:68.8, 1:62.0, 2:66.2, 3:78.1, 4:83.7
**Key insight:** Seeds 3-4 (zero observations) scored HIGHEST. Cross-seed transfer works.
**Delta:** +32 vs round 3

### Experiment 4: v6 round 5 (deeper stacking + terrain-aware blending)
**Date:** 2026-03-20 06:04 UTC
**Round:** 5
**Score after:** 67.56 (rank #69)
**Seeds:** 0:72.6, 1:65.5, 2:67.5, 3:66.8, 4:65.4
**Key:** Seed 0 improved (72.6 vs 68.8 in R4) thanks to deeper stacking.
But unobserved seeds worse (65-67 vs 78-84), round had higher entropy (harder).
**Notes:** Terrain-aware blending helped observed seed but round variance dominates.

### Experiment 5: v6 round 6
**Date:** 2026-03-20 09:09 UTC
**Round:** 6
**Score after:** pending
**Notes:** Most dynamic round yet: 496 terrain changes, 356 settlements, 28 factions.
Empty->Settlement at 19.3% (highest ever). Forest->Settlement at 26.3%.

### Experiment 3 (original entry, kept for context):
**Date:** 2026-03-20 03:36 UTC
**Round:** 4
**Approach:** v6 phased (overview -> analyze -> stack -> secondary -> submit)
**Change:** Full phased strategy. 9 queries overview, 22 stacking on dynamic zones, 18 secondary (seeds 1-2 full coverage). 49/50 queries used.
**Hypothesis:** Round-specific observations + multi-sample stacking should give much better predictions than historical transitions alone. Round 4 is MUCH more dynamic (249 terrain changes vs 37-60 in round 3).
**Score before:** 39.7 (round 3)
**Score after:** pending
**Delta:** pending
**Kept/Reverted:** kept
**Time spent:** 0.5h
**Notes:** Round 4 hidden params favor settlement growth (82 empty->settlement). Settlement survival only 36% (vs 40% historical). Forest more stable at 80% (vs 70% historical). 1323 cells on seed 0 have 2+ samples. Seeds 3-4 use cross-seed transfer only.

### Round 4 Dynamics (very different from rounds 1-3)
- 249 terrain changes (vs 37-60 in round 3, 10-40 in rounds 1-2)
- Empty -> Settlement: 82 (major growth wave)
- Empty -> Forest: 45 (reforestation)
- Forest -> Settlement: 32 (settlements clearing forest)
- Settlement -> Empty: 19 (some die-offs)
- Ports appearing (10 from empty, 6 from forest)
- Ruins appearing (8 from empty, 5 from forest)

### Deep Error Analysis (round 3 seed 0)
- Score 39.68 per API, effective KL ~0.924
- Settlement cells are #1 error: KL=0.52, entropy=0.72 -> highest weighted contribution
- In round 3, most settlements became Empty(70%)/Forest(30%) but we predicted Settlement(40%)
- Port cells equally bad: KL=0.53
- Plains/Empty cells: KL=0.21 (acceptable, low entropy so low weight)
- Forest cells: KL=0.31 (medium, moderate entropy)
- Mountain/Ocean: KL=0.05/0.23 but entropy=0 so they don't affect score
- KEY INSIGHT: scoring is entropy-weighted so settlement/port cells dominate despite being few (33+4 cells)
- FIX: higher trust in round-specific observations (empirical weight increased to 95% max in v6)

### Rules re-read at 2026-03-20T03:04:00Z. No violations found.

### CRITICAL: Scoring Formula Correction (from official MCP docs)
- **Actual formula:** score = 100 * exp(-3 * weighted_kl)
- We had: score = 100 * exp(-weighted_kl) — WRONG, missing the 3x multiplier
- This means: weighted_kl of 0.3 -> score 40.7 (matches our 39.7!)
- Implication: even small KL improvements yield big score gains
  - weighted_kl 0.3 -> score 41
  - weighted_kl 0.2 -> score 55
  - weighted_kl 0.1 -> score 74
  - weighted_kl 0.05 -> score 86
- **Leaderboard = BEST round score** (not cumulative!)
- Hot streak = avg of last 3 rounds
- Strategy shift: we need ONE great round, not consistent mediocre ones

### Simulation Mechanics (from official docs)
- Ground truth computed from HUNDREDS of simulation runs (not one)
- Settlements have: population, food, wealth, defense, tech, faction
- Growth: settlements produce food from adjacent terrain, expand when prosperous
- Conflict: settlements raid each other, longships extend range
- Trade: ports trade when not at war, generates wealth + food
- Winter: severity varies, can destroy isolated/starving settlements -> ruins
- Environment: ruins can be reclaimed by nearby settlements OR overgrown by forest
- Key: settlement survival depends on food (adjacent forests!), defense, faction size

### Settlement Analysis (all 3 completed rounds)
- Adjacent settlements: almost always 0 (settlements are spaced apart at init)
- Settlement survival varies MASSIVELY by round:
  - Round 1: 41% survival, 37% -> empty
  - Round 2: 41% survival, 38% -> empty
  - Round 3: 1.8% survival, 68% -> empty (catastrophic winter?)
- Historical average (28% survival) is USELESS for predicting any specific round
- Only round-specific observations can capture this. THIS is why observations matter.
- Ports: 21% stay port, 47% -> empty, 9% -> settlement
- Forest adjacency has small effect (26% to 33% survival range)
- The DOMINANT factor is the round's hidden parameters, not local features

### Strategy Implication
- The historical transition model should get VERY low weight (10% max)
- Round-specific observations are the #1 priority
- For unobserved seeds: use transition model from observed seeds (same hidden params)
- Every query on dynamic cells is high-value

### Rules re-read at 2026-03-20T04:00:00Z. FOUND: scoring formula was wrong. Fixed in rules.md.

## Session 4: 2026-03-20 11:00-16:00 UTC

### State at session end
- **R7:** Scored 55.1 avg (learned model +8.0 vs heuristic 47.1). Hard round (massive settlement growth).
- **R8:** Submitted with V2 features + Dirichlet ps=12 + T=1.12. Score pending. Closes ~17:45 UTC.
- **R9:** Opens ~17:50 UTC.
- **Best score:** 71.77 (R4, leaderboard 87.3)
- **GCP VM:** ml-churn (europe-west1-b) running continuous churn loop. May have stopped if nohup failed.

### What was built this session
- `backtest.py` — offline QC gate, 4 scoring modes
- `hindsight.py` — post-round query analysis, replays for dashboard
- `simulate.py` — Monte Carlo strategy tournament (8 strategies, 30 trials each)
- `learned_model.py` — neighborhood lookup table (V1: 278 configs, V2: 1102 configs)
- `churn.py` — continuous improvement loop (grid search + hindsight + feature variants)
- `equilibrium.py` — WIP, iteration hurts (-7.9), needs rethinking
- Adaptive stacking with hindsight in astar_v6.py

### Current model stack (what v6 uses for submission)
1. V2 NeighborhoodModel (from churn.py) — 1102 configs, distance-to-settlement features
2. Dirichlet-Categorical Bayesian observation blending (prior_strength=12)
3. Temperature scaling T=1.12
4. Probability floor 0.01
5. Adaptive stacking: 9 overview + 41 queries all seed 0, hindsight between batches

### Backtest scores (leave-one-out, with obs, 7 rounds)
- Heuristic (old): avg 60.9
- V1 learned: avg 64.3
- V2 + Dirichlet ps=12 + T=1.12: avg 64.5

### Key findings
- Settlement cells are #1 bottleneck (KL 0.08-0.44 with learned model, was 0.37-0.99)
- Single-obs seeds hurt settlements (hindsight: seed 1 avg -1.5 boost)
- Adaptive stacking beats blind by +1.5 (simulation engine, 30 MC trials)
- Temperature scaling T=1.12 optimal (+1.2 vs no scaling)
- Dirichlet Bayesian replaces hard blend (+1.1 vs hard obs_weight=0.70)
- Equilibrium iteration hurts with argmax approach (-7.9)
- Competitor at 91.49 uses equilibrium models we haven't cracked yet

### Research agent findings (top 3 priorities)
1. Dirichlet-Categorical Bayesian — IMPLEMENTED, +1.1
2. Per-class temperature — TESTED, doesn't help over global T=1.12
3. Information-directed query allocation — NOT YET IMPLEMENTED

### Next steps for R9
1. Execute R9 when it opens (~17:50 UTC): overview + adaptive stack + submit
2. Cache R8 ground truth when available, retrain model (64K cells from 8 rounds)
3. Consider: pair approximation (spatial correlation correction), information-directed queries
4. GCP VM: verify churn loop is running, redeploy if needed

### JC Reminder for next round
Consider more weighting on positive and negative enforcement in the model.
Positive: reward correct predictions more strongly. Negative: penalize wrong predictions more.
This could apply to observation blending, transition model training, or post-processing.

### API Discovery: simulate returns settlement STATS
- The /simulate endpoint returns NOT just the grid but also settlement objects with:
  population, food, wealth, defense, has_port, alive, owner_id
- We are NOT currently capturing this data from our observations!
- Low food/population settlements are more likely to die
- owner_id reveals faction structure (same faction = allies, different = enemies)
- This could be used to build per-settlement survival predictions
- FIX: capture settlement stats during observation phases

### Leaderboard: weighted_score = round_score * round_weight
- Not just best round_score, but score multiplied by round weight
- Higher-weight rounds matter more (later rounds have 5% compounding weight)
- Round 5 weight ~1.28, round 10 weight ~1.63

### Session 3 End: 2026-03-20 10:35 UTC (11:35 CET)
**State:** Round 6 active (closes 12:53 CET), all 5 seeds submitted, 50/50 queries used.
**Best score:** 71.8 (round 4, leaderboard 87.3)
**Next:** Round 7 monitor set for 11:50 UTC. Build backtester before next round.
**JC directive:** Build analysis/backtesting tools to improve submissions.

## Auth Note
API uses cookie auth: `access_token` cookie. Bearer header returns "Missing token" in curl.

## Session 6: 2026-03-20 21:37-21:55 UTC

### Phase 1: R10 Improvement
- Cached R8+R9 ground truth (were missing from local cache)
- Retrained V2 model: 9 rounds, 72K cells, backtest avg 65.6 (was 64.5 with 7 rounds)
- R9 backtest matches reality: 83.0 vs 82.6 actual
- Resubmitted R10 with retrained model + all 5 seeds observed

### Phase 2: Overnight Automation
- Built overnight_runner.py: autonomous round handler
- Deployed to GCP VM ml-churn (PID 8653, 5-min interval)
- State file tracks submitted rounds and cached data

### Incident: False Extinction Detection
- VM started and tried to submit R10 as new round
- Budget was 50/50 used, so observe_all_seeds tried to query but got 429
- With 0 observations: survival=0%, detected "extinction", applied death calibration
- Submitted very bad model-only + extinction predictions
- FIXED: resubmitted from local with correct observations
- FIXED: patched overnight_runner.py to check budget before attempting observations

### Experiment 6: R10 resubmit with 9-round model
**Date:** 2026-03-20 21:44 UTC
**Round:** 10 (active, weight 1.6289)
**Change:** Retrained V2 model with 9 rounds instead of 7
**Hypothesis:** 2 extra rounds of training data should improve model accuracy
**Score before:** pending (original v7 submission)
**Score after:** pending
**Kept/Reverted:** kept
**Notes:** Backtest improved from 64.5 to 65.6 avg. R9 backtest 83.0 matches 82.6 actual.

### Rules re-read at 2026-03-20T21:37:00Z. No violations found.
