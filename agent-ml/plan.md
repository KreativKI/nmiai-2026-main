# Astar Island -- Hail Mary Plan v3

**Created:** 2026-03-21 21:30 CET | **Updated:** 2026-03-21 22:00 CET
**Deadline:** Sunday 2026-03-22 15:00 CET
**Current score:** 169.6 weighted (R15=81.6 best) | Rank 167
**Goal:** Two competing models + ensemble, blind-tested, winner deployed

## Audit History

- v1: First audit killed Model B (U-Net), added CA-Markov, switched to multiclass LightGBM
- v2: Second audit found 3 blockers: prediction-time feature defaults, empty cell
  handling in CA-Markov, transition matrix fallback hierarchy. All fixed in v3.
- v3: Addressed all v2 findings. Added auditor to automation pipeline.
- v3.1: Audit 3 fixes: prediction-time defaults for settlement-stat aggregates
  (use 0.0, accepted mismatch), pseudocode for transition extraction, regime
  fallback = "stable", CV regime label bias note, ruin priors cite exact data.

## Situation

overnight_v4.py continues running autonomously on GCP throughout.
It handles rounds, submits, caches data. It is the safety net.

## Data (verified complete, 2026-03-21 21:00 CET)

| Source | Volume | Status |
|--------|--------|--------|
| Replays | 80 files (16 rounds x 5 seeds x 51 frames) | Complete |
| Ground truth | 16 rounds (40x40x6 probability tensors, 5 seeds each) | Complete |
| Settlement stats per frame | 7 stats x 440K records | Available, UNDER-EXTRACTED |
| Deep analysis results | Transition matrices, hard constraints | Complete |

### Feature gap: data available but not extracted

build_dataset.py currently extracts 32 features. The replays contain much more:

**Currently extracted:**
- Year 0: terrain, 8-neighbor counts, distances, food, pop, wealth, defense, port, owner
- Year 10: terrain, is_settle, food, pop, n_settle
- Year 25: terrain, is_settle, n_settle
- Round-level: regime one-hot, total_settlements, total_ports

**Available but NOT extracted (must fix in Phase 1):**

Per-cell stats from replay frames:
- Year 10: wealth, defense (2 features)
- Year 25: food, pop, wealth, defense (4 features)
- Per-cell survival: did this cell's settlement survive to y10? y25? (2 features)

Round-level trajectory features (from replay aggregates):
- settle_growth_y10 = count_y10 / count_y0
- settle_growth_y25 = count_y25 / count_y0
- wealth_decay_y10 = avg_wealth_y10 / avg_wealth_y0
- wealth_decay_y25 = avg_wealth_y25 / avg_wealth_y0
- faction_consol_y10 = factions_y10 / factions_y0
- pop_trend_y10 = avg_pop_y10 / avg_pop_y0
- food_trend_y10 = avg_food_y10 / avg_food_y0

Round-level aggregates:
- total_wealth_y0, total_food_y0, avg_defense_y0, total_factions_y0

Total: ~17 new features, bringing the model from 32 to ~49 features.

### Prediction-time defaults (CRITICAL, from audit)

At prediction time for a NEW round, replay data does not exist.
`extract_cell_features()` is called with `replay_data=None`.
All new features must have sensible defaults:

| Feature | Default when no replay |
|---------|----------------------|
| wealth_y10, defense_y10 | Carry forward year-0 values (wealth_y0, defense_y0) |
| food_y25, pop_y25, wealth_y25, defense_y25 | Carry forward year-0 values |
| survived_y10, survived_y25 | 1 if cell is currently settlement/port, else 0 |
| settle_growth_y10, settle_growth_y25 | 1.0 (no change assumed) |
| wealth_decay_y10, wealth_decay_y25 | 1.0 (no change assumed) |
| faction_consol_y10 | 1.0 |
| pop_trend_y10, food_trend_y10 | 1.0 |
| total_wealth_y0, total_food_y0, avg_defense_y0 | 0.0 (settlement stats not in terrain grid, accepted training/inference mismatch) |
| total_factions_y0 | Use count of initial settlements as proxy (available from terrain grid) |

These defaults must be added to the `temporal_defaults` dict in
`extract_cell_features()` to prevent the 0-value mismatch bug.

---

## Phase 1: Fix the data pipeline

### 1A. Extend build_dataset.py

Add all missing feature extractions listed above.

Changes to `extract_cell_features()`:
- Add wealth_y10, defense_y10 from year-10 settlement lookup
- Add food_y25, pop_y25, wealth_y25, defense_y25 from year-25 settlement lookup
- Add survived_y10, survived_y25 (was this cell a settlement at y0, still one at y10/y25?)
- Add ALL new features to `temporal_defaults` dict with carry-forward defaults
- Update FEATURE_NAMES to include all new features in canonical order

Changes to `build_master_dataset()`:
- Compute round-level trajectory features from replay aggregates per round/seed
- Compute round-level aggregates from initial grid (total_wealth, total_food, etc.)
- These are available at prediction time (computed from initial grid, no replay needed)
- Add to each cell row as round-level features

### 1B. Build evaluation framework

File: `evaluate.py`

Leave-one-round-out cross-validation:
- For each of 16 rounds: train on other 15, predict all 5 seeds of held-out round
- Score using official formula: 100 * exp(-3 * weighted_KL)
- Two modes: (a) model-only prediction, (b) model + simulated observation blending
- Report per-round, per-regime, and overall averages
- Stratify reporting by regime (death/stable/growth)

Note on regime labels in CV: leave-one-round-out uses ground-truth regime labels
(derived from ground truth via classify_round). In production, regime comes from
the smell test (5 viewport queries). This optimistically biases CV scores by an
estimated 2-5 points for regime-dependent models. Apply the known +11.6 calibration
offset to CV results regardless.

### 1C. Build neighborhood-conditioned transition model

File: `transition_model.py`

From deep_analysis.py we have aggregate per-regime transition rates.
For CA-Markov (Model C), we need NEIGHBORHOOD-CONDITIONED rates.

**Matrix structure:**
P(next_terrain | current_terrain, n_settle_neighbors, n_forest_neighbors, regime)

**Data source:**
All 80 replays x 50 year-to-year transitions = 6.4M observations.

**Hierarchical fallback (from audit, matching regime_model.py pattern):**
1. Full key: (regime, terrain, n_settle, n_forest) -- use if 10+ observations
2. Reduced key: (regime, terrain, n_dynamic, has_forest) -- use if 20+ observations
3. Minimal key: (regime, terrain) -- always available
4. Global: (terrain) -- absolute fallback

Each level normalizes to a valid probability distribution.
No Laplace smoothing needed: the fallback hierarchy handles sparsity.

**Transition model applies to non-empty, non-static cells only.**
Empty cells (raw 0) and static cells (Mountain=5, Ocean=10/11) are handled
separately (empty by neighbor-density heuristic, static by near-certain self-prediction).

**Pseudocode for replay frame extraction:**
```
for each replay file (round rn, seed si):
    regime = classify_round(ground_truth_data[rn])
    frames = replay["frames"]  # 51 frames, indices 0-50
    for t in range(50):  # year-to-year transitions
        grid_now = frames[t]["grid"]
        grid_next = frames[t+1]["grid"]
        for y, x in all cells:
            raw = grid_now[y][x]
            if raw in OCEAN_RAW or raw == 5:  # skip static
                continue
            if cell_to_class(raw) == 0:  # skip empty
                continue
            terrain_now = cell_to_class(raw)
            terrain_next = cell_to_class(grid_next[y][x])
            n_settle = count_settle_neighbors(grid_now, y, x)
            n_forest = count_forest_neighbors(grid_now, y, x)
            record_transition(regime, terrain_now, n_settle, n_forest, terrain_next)
```

**Empty cell handling (from audit):**
Empty cells (raw value 0) do not appear in replay grids (confirmed by deep analysis).
The Empty class only exists in ground truth probability space. In the transition model:
- If a cell is Empty in the initial grid: check settlement neighbor density
  - High settle neighbors (2+) in growth regime: assign P(settlement) = 0.3, P(empty) = 0.6, rest floor
  - Otherwise: assign P(empty) = 0.95, rest floor
- This uses the expansion radius data from deep analysis (median 2-3 cells)

---

## Phase 2: Model A -- Multiclass LightGBM

File: `model_a_lgbm.py`

### Key change from current model
Switch from 6 independent regressors to single multiclass LightGBM:
```python
lgb.LGBMClassifier(objective="multiclass", num_class=6, ...)
```

This forces a valid probability distribution (softmax output).
The current 6-regressor approach produces independent predictions that
don't sum to 1, then clips and renormalizes.

### Features
~49 features from the extended build_dataset.py (Phase 1A).

### Training
- Single LGBMClassifier with multiclass objective
- Hyperparameters: start from churn_v4's best, re-tune if needed
- Leave-one-round-out CV via evaluate.py

### GCP
CPU only, trains in minutes. Runs on ml-brain or ml-churn.

---

## Phase 3: Model C -- CA-Markov Forward Simulation

File: `model_c_camarkov.py`

### Architecture
For each cell in the initial grid:
1. Look up current terrain type
2. Look up neighborhood (n_settle, n_forest neighbors from initial grid)
3. Get the transition probability vector from transition_model.py (regime-conditioned)
4. Apply this transition 50 times iteratively
5. Result: 6-class probability distribution per cell

### Why this works
- Uses ALL 6.4M year-to-year transitions from replay data
- Respects temporal dynamics (year-by-year chaining, not year-0 to year-50 jump)
- Naturally produces valid probability distributions (each transition row sums to 1)
- Handles ruin lifecycle correctly (ruins are transient in the matrix)
- Mountains/ocean are absorbing states (transition to self with probability 1)
- Takes seconds to run, no training needed

### Known limitation: static neighborhoods
The neighborhood is frozen at year 0 and used for all 50 steps. In reality,
as forests get consumed by settlements in growth rounds, the neighborhood
changes. This means CA-Markov UNDERESTIMATES settlement expansion into forests.

Mitigation: ensemble weighting gives Model A higher weight on forest cells
near settlements in growth regime, where CA-Markov's static assumption
is weakest and Model A's spatial features are strongest.

### Empty cell handling
See Phase 1C. Empty cells use neighbor-density heuristic, not the transition matrix.

---

## Phase 4: Ensemble + Hard Constraints

File: `ensemble.py`

### Ensemble strategy
Blend Model A and Model C predictions:
```
final_pred = w_A * model_a_pred + w_C * model_c_pred
```

Weights learned from leave-one-round-out CV:
- Per-regime weights (Model C might dominate on death, Model A on growth)
- Simple grid search over weight combinations, pick lowest average KL
- Can also do per-cell-type weighting if data supports it

### Hard constraints (applied AFTER ensemble blending)
- Ports only on coastal cells: P(port) = 0.01 for inland cells
- Ruin cap: P(ruin) <= 0.05 at year 50
- Mountains never change: near-certain prediction
- Ocean never changes: near-certain prediction
- Ruin hard priors by regime: if cell is currently a ruin, apply
  per-regime destination distribution from `transition_matrix[regime]["Ruin"]`
  in deep_analysis_results.json (exact values, not approximations):
  - death: Settlement=0.4462, Empty=0.3592, Forest=0.1807, Port=0.0138
  - stable: Settlement=0.4823, Empty=0.3403, Forest=0.1652, Port=0.0121
  - growth: Settlement=0.4983, Empty=0.3361, Forest=0.1531, Port=0.0126
- Floor all probabilities at 0.01, renormalize

### Observation blending (at prediction time only)
After ensemble + hard constraints, apply Dirichlet blending with
viewport observation data (same as current overnight_v4 approach).
Only the deep-stacked seed gets observation blending. Other 4 seeds
get ensemble + hard constraints only.

---

## Phase 5: Blind Evaluation Tournament

File: `tournament.py`

### Protocol
For each of 16 rounds:
1. Hold out this round (train models on other 15)
2. Give each model: initial grid + regime label only (no observations)
3. Each model predicts 40x40x6 for all 5 seeds
4. Score against ground truth
5. Also test: ensemble prediction, ensemble + simulated observation blending

### What gets compared
| Label | What it is |
|-------|-----------|
| BASELINE | Current LightGBM (32-feat, 6 independent regressors) |
| ENRICHED | Model A (49-feat, multiclass) |
| SIMULATION | Model C (CA-Markov) |
| COMBINED | Ensemble (A + C weighted blend) |
| FINAL | Ensemble + observation blending |

### Audit gate
Before deploying the winner, spawn an unbiased auditor agent to review:
- Tournament results and statistical significance
- Winner model's predictions on edge cases (death rounds, chaotic rounds)
- Deployment plan risks

Only deploy after auditor approves.

### Decision criteria
Deploy whatever scores best on the tournament. The 11.6-point calibration
gap means we cannot distinguish models within 5 points. If ensemble is
within 5 points of the best single model, prefer ensemble (more robust).

---

## Phase 6: Deployment

### Integration
Create `overnight_v5.py` based on overnight_v4.py with these changes:
- Replace 6 independent LGBMRegressors with winning model pipeline
- Add ensemble logic if ensemble wins
- Add extended feature extraction (imports from updated build_dataset.py)
- Keep same observation, submission, and post-round pipeline
- Keep same cron watchdog and state management

### Explicit changes to predict_and_submit():
- Feature extraction: use updated extract_cell_features with 49 features
- Model: LGBMClassifier multiclass (or ensemble)
- Hard constraints: expanded set from Phase 4
- Observation blending: unchanged

### Regime classification
Carries forward unchanged from overnight_v4 (smell test: 5 viewport queries
on settlement cells, check alive/dead ratio). On ambiguous regime detection,
default is "stable" (matches overnight_v4 state fallback behavior).

### Safety net
overnight_v4 keeps running on its own cron until v5 is validated.
When v5 submits successfully for one round, disable v4 cron.

### Auto-retrain on new data
When a round completes:
- Rebuild master dataset with extended features
- Retrain winning model
- Re-run evaluation against all cached rounds
- Resubmit if current round still active

---

## Automation Pipeline

### Built-in auditor
At each decision point, spawn a `feature-dev:code-architect` agent
as an unbiased auditor to review the work before proceeding:

| Decision point | What auditor reviews |
|---------------|---------------------|
| After Phase 1 | Feature pipeline: are all features extracted correctly? Defaults sound? |
| After Phase 2+3 | Model implementations: any bugs? Edge cases? |
| After Phase 5 | Tournament results: is the winner legit? Any red flags? |
| Before Phase 6 | Deployment plan: will overnight_v5 work? Risks? |

### Automated evaluation on GCP
After deployment, new rounds trigger:
1. Cache GT + download replays (already in overnight_v4/v5)
2. Rebuild dataset
3. Retrain model
4. Run tournament with new data
5. Log results

---

## Execution Order

```
Phase 1A: Extend build_dataset.py
Phase 1B: evaluate.py                 (parallel with 1A)
Phase 1C: transition_model.py         (parallel with 1A)
  -> AUDIT GATE: verify features, defaults, transition model
Phase 2:  model_a_lgbm.py             (after 1A, 1B)
Phase 3:  model_c_camarkov.py         (after 1C, 1B)
  -> AUDIT GATE: verify model implementations
Phase 4:  ensemble.py                 (after 2, 3)
Phase 5:  tournament.py               (after 4)
  -> AUDIT GATE: verify results, approve winner
Phase 6:  deployment                  (after audit approval)
```

Each phase goes through Boris: Explore (done), Plan (this doc), Code,
Review (sequential), Simplify, Validate, Commit.

---

## What stays running during all of this

overnight_v4 on ml-brain: handles rounds, submits, caches data, downloads replays.
Nothing in this plan touches or interrupts it until Phase 6 deployment.
