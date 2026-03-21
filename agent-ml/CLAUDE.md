# NM i AI 2026 -- ML Track Agent: Astar Island

## Identity
You are the ML track agent. Single purpose: maximize score before Sunday 15:00 CET.

## Competition Clock
Sunday **15:00 CET** (UTC+1). `OSLO = timezone(timedelta(hours=1))`

## Autonomy
- overnight_v4 handles rounds autonomously on GCP ml-brain VM
- JC may pause overnight_v4 and control queries manually
- Before every submission: floor probs at 0.01, renormalize, validate shape 40x40x6 x 5 seeds
- Missing rounds = 0 points forever

## Boris Workflow (mandatory, every code change, NO EXCEPTIONS)

The full pipeline, every step sequential, one at a time:

1. **EXPLORE** — launch `feature-dev:code-explorer` agent (fresh context)
2. **PLAN** — plan mode. Write plan in plan.md before coding.
3. **CODE** — implement the approved plan
4. **REVIEW** — launch `feature-dev:code-reviewer` agent (fresh context). Fix any bugs found BEFORE moving on.
5. **SIMPLIFY** — launch `code-simplifier:code-simplifier` agent (fresh context). Apply changes BEFORE moving on.
6. **VALIDATE** — launch `build-validator` agent (fresh context). Must pass BEFORE committing.
7. **COMMIT** — only after all three agents pass sequentially.

**NEVER run steps 4, 5, 6 in parallel.** They are SEQUENTIAL: review first, fix issues, THEN simplify, THEN validate. Each is a separate Agent call with its own fresh context.
There is no "boris-workflow" subagent. Boris is a workflow using separate tools.
"Too small to bother" and "time pressure" are not valid reasons to skip.

---

## Session Startup (every session)
1. Read this CLAUDE.md + plan.md + SESSION-HANDOFF.md
2. Check intelligence/for-ml-agent/ for new orders
3. Check GCP VMs: `gcloud compute ssh ml-brain/ml-churn --zone=europe-west1-b --project=ai-nm26osl-1779 --command="ps aux | grep -E 'overnight|churn' | grep -v grep"`
4. Check round status: GET https://api.ainm.no/astar-island/rounds
5. State: "Score: {X}. Round: {N}. Next step: {Z}."

## Session End
1. Update SESSION-HANDOFF.md
2. Commit with score delta in message
3. Push to origin/agent-ml

---

## Task: Astar Island

40x40 grid, 6 terrain classes (Empty, Settlement, Port, Ruin, Forest, Mountain).
Predict probability distribution per cell after 50 years of stochastic simulation.
Score: `100 * exp(-KL_divergence)` entropy-weighted. Higher = better.
5 seeds per round, same hidden params. 50 queries shared across seeds.

### World Mechanics (from competition audio transcript)
- Settlements grow by harvesting forests
- Ports form on coast (ocean adjacency)
- Factions clash: raids loot food/wealth, desperate fight harder
- Conquered settlements can join conqueror
- Trade alliances form through ports, tech spreads
- Winter kills settlements annually (hidden severity parameter)
- Ruins left behind, forest slowly reclaims
- Ground truth = average of HUNDREDS of Monte Carlo simulations
- Three hidden params per round: growth_rate, raid_severity, winter_harshness

### Three Regimes
- **Extinction:** All settlements die. Predict empty/forest. (R3, R4, R8)
- **Growth:** Settlements multiply 2-4x. Forests consumed. (R6, R7, R15)
- **Stable:** Mixed outcomes, hardest to predict. (R1, R2, R5)

### Key Rules (from 8-round analysis, NEEDS REVALIDATION with 16 rounds)
- Mountains never change
- Ports ONLY form adjacent to ocean
- Empty never becomes forest
- Ruins never dominant (transitional: ruins -> forest over time)
- Settlement expansion radius: 3-12 Manhattan distance
- Mountains kill adjacent settlements (survival 15-37% with 2+ adj)
- Source: intelligence/for-overseer/hidden-rules-discovery.md
- Full briefing: /Users/jcfrugaard/Downloads/OVERSEER-BRIEFING-ASTAR-DEEP-ANALYSIS.md

---

## Current Architecture (as of R17)

### Model: Brain V4 (LightGBM, 32 features)
- Trained on master dataset: 102K cells from 15 rounds + replay features
- 50 trees (churn-optimized), 32 features including settlement stats + temporal
- Dirichlet observation blending (alpha=20, tunable by churn)
- Features from build_dataset.py: spatial (13) + settlement stats (6) + temporal (8) + round-level (5)

### GCP VMs
| VM | Process | Purpose |
|----|---------|---------|
| ml-brain | overnight_v4.py | Autonomous round handler (V4 32-feat, deep stack, data pipeline) |
| ml-churn | churn_v4.py | Continuous LightGBM hyperparam optimization (32-feat) |

### Key Files
| File | Purpose |
|------|---------|
| overnight_v4.py | Autonomous: observe, predict, submit, cache GT, download replay, rebuild dataset |
| churn_v4.py | Continuous hyperparameter search on 32-feature dataset |
| build_dataset.py | Master dataset builder (32 features from replays + ground truth) |
| brain_v4.py | Original 13-feature model (superseded by build_dataset 32-feat) |
| data_pipeline.py | Manual round processing (automated in overnight_v4) |
| backtest.py | Scoring, ground truth caching, API helpers |
| ML-TRACK-RECIPE.md | Complete operational runbook for any AI agent |

### Data
| Source | Volume | Location |
|--------|--------|----------|
| Ground truth | 16 rounds cached | data/ground_truth_cache/ |
| Replays | ~80 files (16 rounds x 5 seeds, 51 frames each) | data/replays/ |
| Master dataset | 102K rows x 32 features | data/master_dataset.npz |
| Calibration | V4 32-feat offsets per regime | data/calibration_v4_32feat.json |

### Replay API (FREE, no query cost)
`POST /astar-island/replay` with `{round_id, seed_index}` returns 51 frames (year 0-50).
Each frame: full terrain grid + per-settlement stats (population, food, wealth, defense).
Available for completed rounds only.

---

## Score History

| Round | Score | Rank | Weight | Weighted | Model |
|-------|-------|------|--------|----------|-------|
| R15 | **81.6** | 137 | 2.079 | **169.6** | V4 32-feat deep stack seed 0 |
| R9 | **82.6** | 93 | 1.551 | 128.1 | V2 deep stack seed 0 |
| R14 | 67.8 | 95 | 1.980 | 134.2 | V3+V2 blend spread |
| R16 | 57.0 | 203 | 2.183 | 124.5 | V4 32-feat deep stack seed 1 |
| R17 | pending | - | 2.292 | - | overnight_v4 autonomous |

### Calibration (V4 32-feature)
| Regime | Backtest Offset | Meaning |
|--------|----------------|---------|
| Death | +15.6 | Backtest 80 = actual ~64 |
| Growth | +5.5 | Backtest 75 = actual ~70 |
| Stable | +13.4 | Backtest 80 = actual ~67 |
| Overall | +11.6 | |

### Why R9 and R15 scored 80+
Both had predictable dynamics: settlements grew steadily, clear directional outcomes.
R9: 33->61 settlements. R15: 32->204 settlements.
When dynamics are chaotic (R16: 58->78, ambiguous), model struggles.
Score depends more on hidden parameters (round predictability) than model quality.

---

## Priority: Deep Analysis Task (NEXT SESSION)
Run on GCP (not local Mac). Validate the hidden rules briefing against ALL 16 rounds of replay data.

Source: /Users/jcfrugaard/Downloads/OVERSEER-BRIEFING-ASTAR-DEEP-ANALYSIS.md

Hypotheses to test with 80 replay files:
1. Do empty cells EVER become forest? (claimed: never)
2. Settlement expansion radius by regime (claimed: 3-12 Manhattan)
3. Do mountains kill adjacent settlements? Measure survival rate.
4. Port formation: always coastal? What % of coastal settlements become ports?
5. Ruin lifecycle: how long do ruins exist before becoming forest/empty?
6. Winter severity detection: can year-10 settlement stats predict final regime?
7. Faction dynamics: do owner_id patterns predict outcomes?
8. What makes R9/R15 dynamics "predictable" vs R16 "chaotic"?

Results should feed directly into V4 feature engineering or hard constraints.

---

## Anti-Drift Rules
- Never assume a rule from memory. Check the API.
- Never ignore a score regression.
- Never submit without verifying probability floors and renormalization.
- Never estimate time. Calculate with python.
- Never spend queries without JC's approval if overnight_v4 is paused.

## Communication
- intelligence/for-ml-agent/ = inbox
- intelligence/for-overseer/ = status out
- intelligence/for-jc/ = JC updates
- Solutions in agent-ml/solutions/. Never overwrite old versions.

## Git
Branch: `agent-ml` | Worktree: `/Volumes/devdrive/github_dev/nmiai-worktree-ml/`
