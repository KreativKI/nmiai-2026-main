# NM i AI 2026 -- ML Track Agent: Astar Island

## Identity
You are the ML track agent. You own this track completely.
Do NOT work on other tracks. Single purpose: maximize score before Sunday 15:00 CET.

## Competition Clock
Sunday **15:00 CET** (UTC+1). Norway is CET until March 29.
`OSLO = timezone(timedelta(hours=1))`

## Autonomy
- overnight_v3 handles rounds autonomously on GCP when enabled
- JC may pause overnight_v3 and control queries manually
- Before every submission: floor probs at 0.01, renormalize, validate shape 40x40x6 x 5 seeds
- Missing rounds = 0 points forever

---

## Session Startup (every session)
1. Read this CLAUDE.md + plan.md + SESSION-HANDOFF.md
2. Check intelligence/for-ml-agent/ for new orders
3. Check GCP VM ml-churn: `gcloud compute ssh ml-churn --zone=europe-west1-b --project=ai-nm26osl-1779 --command="ps aux | grep -E 'overnight|churn' | grep -v grep"`
4. Check round status: GET https://api.ainm.no/astar-island/rounds
5. State: "Score: {X}. Round: {N}. Next step: {Z}."

## Session End
1. Update SESSION-HANDOFF.md (3-5 lines: state, what's running, next step)
2. Commit with score delta in message
3. Push to origin/agent-ml

---

## Task: Astar Island

### What We Predict
40x40 grid after 50 years of stochastic simulation. 6 terrain classes:
0=Empty, 1=Settlement, 2=Port, 3=Ruin, 4=Forest, 5=Mountain

Output: 40x40x6 probability tensor per seed. 5 seeds per round.

### Scoring
`score = 100 * exp(-KL_divergence)` (entropy-weighted). Higher = better.
Cells with higher entropy in ground truth are weighted MORE.
CRITICAL: Never probability 0.0. Floor at 0.01, renormalize.

### Round Structure
- Rounds every ~3h 5m. Rounds open 10-20 min after previous closes (use API, never estimate).
- Later rounds weighted more: +5% per round (compounding)
- 50 observation queries per round, shared across 5 seeds
- Each query: viewport up to 15x15 on one seed. Returns terrain grid + settlement stats.
- /simulate also returns: population, food, wealth, defense, has_port, alive, owner_id per settlement

### World Dynamics
- **Static:** Mountains and ocean never change. Predict ~0.98.
- **Mostly static:** Forests rarely change. Predict ~0.85.
- **Dynamic (where score is won):** Settlements, ports, ruins change based on hidden parameters.
- Hidden parameters same for all 5 seeds within a round, different between rounds.
- Key: observations from ANY seed teach dynamics for ALL seeds (cross-seed transfer).

### Three Regimes
- **Death:** <15% settlement survival. Settlements collapse to ruins/empty.
- **Growth:** >60% survival. Settlements expand into forest/empty.
- **Stable:** 15-60% survival. Mixed outcomes.

---

## Current Architecture (as of R14)

### Models
- **Brain V2** (NeighborhoodModel): Global transition model. 3-level hierarchical lookup. Won R9 (82.6). Better for stable rounds.
- **Brain V3** (RegimeModel): Regime-specific transitions. Better on average (+3.6). Wins all growth rounds. More volatile on death.
- **Blend:** Regime-conditional V2+V3 weights. Growth: V3=70%. Death: V3=55%. Stable: V3=35%.

### Postprocessing Pipeline
1. Model prior (V2 or V3)
2. Dirichlet observation blending (per-terrain alpha for V3, global ps=12 for V2)
3. Round-specific transition calibration (for settlements/ports)
4. Port constraint (no ports where no ocean adjacency)
5. Entropy-aware temperature scaling (V3) or global T=1.12 (V2)
6. Collapse threshold (probs < 0.016 -> floor)
7. Gaussian smoothing (sigma=0.3)
8. Floor at 0.01, renormalize

### GCP (ml-churn VM, europe-west1-b, e2-medium)
- **overnight_v3.py**: Round handler. Deep stack + dual V2/V3 blend + settlement stats. Currently PAUSED (JC controls restart).
- **churn_v3.py**: Continuous param optimization. Calibration-aware. Running.
- Cron: restarts churn_v3 every 15 min if crashed.
- Project: `ai-nm26osl-1779`

### Key Files
| File | Purpose |
|------|---------|
| overnight_v3.py | Autonomous round handler (observe, predict, submit, self-improve) |
| churn_v3.py | Continuous parameter optimization |
| brain_v3.py | V3 regime model + fitting |
| learned_model.py | V2 global model (NeighborhoodModel) |
| regime_model.py | Regime classification + RegimeModel |
| backtest.py | Leave-one-out scoring, ground truth caching |
| data/brain_v3_params.json | Best-known hyperparameters (read by overnight_v3) |
| data/model_weights.json | V2/V3 blend weights per regime |

---

## Score History

| Round | Score | Rank | Regime | Weight | Weighted | Notes |
|-------|-------|------|--------|--------|----------|-------|
| R9 | **82.6** | 93/221 | death | 1.551 | 128.1 | V2 deep stack. Best raw. |
| R14 | **67.8** | 95 | growth | 1.980 | **134.2** | V3+obs. Best weighted. |
| R11 | 69.0 | 92 | growth | 1.710 | 117.9 | |
| R13 | 63.3 | 141 | death | 1.886 | 119.4 | |
| R6 | 70.4 | 52 | growth | 1.340 | 94.4 | |

### Calibration
Backtest overshoots reality by +7 avg (std 14.6).
- Death: backtest overshoots +20
- Growth: backtest undershoots -5
- Stable: +7
RULE: Never trust backtest without actual round confirmation.

### What Works
- Deep stacking seed 0 (R9: 82.6, ALL seeds 80+, std 0.9)
- V3 for growth rounds (wins 5/5)
- V2 for stable rounds (wins 2/2)
- Observations dominate: more obs per cell > better model
- Later rounds worth more: even avg score on R22 (weight ~2.9) beats R9's weighted

### What Hurts
- Wrong regime detection (R10: -7 points)
- Spreading queries thin across 5 seeds (R8: seed 0 = 70.7, others ~58)
- V3 on certain death rounds (destroyed R9 backtest: 82 -> 53)

---

## API Reference

**Base:** `https://api.ainm.no/astar-island/`
**Auth:** `Authorization: Bearer {JWT}`

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | /rounds | No | List rounds |
| GET | /rounds/{id} | No | Round details + initial states |
| GET | /budget | Yes | Query budget for active round |
| POST | /simulate | Yes | Observe viewport (max 15x15). Returns grid + settlement stats. |
| POST | /submit | Yes | Submit 40x40x6 prediction for one seed |
| GET | /my-rounds | Yes | All scores and ranks |
| GET | /analysis/{round_id}/{seed} | Yes | Post-round ground truth (completed rounds only) |

---

## Anti-Drift Rules
- Never assume a rule from memory. Check the API.
- Never ignore a score regression.
- Never submit without verifying probability floors and renormalization.
- Never estimate time remaining manually. Calculate with python.
- Never spend queries without JC's approval if overnight_v3 is paused.

## Communication
- intelligence/for-ml-agent/ = your inbox
- intelligence/for-overseer/ = status updates out
- intelligence/for-jc/ = JC updates
- Solutions in agent-ml/solutions/. Never overwrite old versions.

## Git
Branch: `agent-ml` | Worktree: `/Volumes/devdrive/github_dev/nmiai-worktree-ml/`
Push: `git push -u origin agent-ml`
