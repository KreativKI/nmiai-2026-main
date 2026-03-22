# Overnight V6 Plan -- All 5 Competitor-Inspired Improvements

**Created:** 2026-03-22 11:30 CET
**Goal:** Learning + automation. Implement all 5 improvements in overnight_v6.py.
**Approach:** New file (v6) so v5 stays as autonomous safety net on GCP.

## Architecture Decision

Create `overnight_v6.py` that imports from the same `build_dataset.py` and `backtest.py` but
adds 5 new capabilities. Also create `build_dataset_v6.py` with extended features (C).
The v5 process keeps running on GCP. V6 can be deployed alongside or as replacement
after local validation.

---

## Change A: MLP Neural Network Ensemble

**What:** Add sklearn MLPRegressor alongside LightGBM. Blend predictions before Dirichlet.
**Why:** LightGBM trains 6 independent regressors (one per class). An MLP with softmax-like
output learns joint class distributions. Captures correlations like "if settlement goes up,
forest goes down."

**Implementation:**
- Use `sklearn.neural_network.MLPRegressor` (available on GCP, no PyTorch needed)
- Train 1 MLP on the same dataset as LightGBM (51 features -> 6 targets simultaneously)
  Actually, sklearn MLPRegressor is single-output. Use `MultiOutputRegressor` wrapper,
  OR train 6 separate MLPs (matches LightGBM pattern), OR use MLPClassifier with
  custom approach.

  **Best approach:** Train one `sklearn.neural_network.MLPRegressor` per class (same as LightGBM),
  then also train a second set with `sklearn.neural_network.MLPClassifier` on argmax labels
  to get `predict_proba` (joint distribution). Blend the three: LightGBM + MLP-regressor + MLP-classifier.

  **Simplification:** Just do LightGBM + MLPRegressor (6 models), 50/50 blend.
  The joint distribution benefit comes from the MLP's hidden layers sharing information
  across the feature space differently than tree splits.

- In `predict_and_submit_v2`:
  1. Train LightGBM models (existing)
  2. Train MLP models (new): `MLPRegressor(hidden_layer_sizes=(128, 64), max_iter=500, early_stopping=True)`
  3. For each cell: `pred = 0.5 * lgb_pred + 0.5 * mlp_pred`
  4. Then apply Dirichlet blending as before

**Risk:** Low. Additive change. If MLP is worse, blend weight can be reduced.
**Validation:** Backtest on cached rounds, compare LightGBM-only vs blended.

---

## Change B: Monte Carlo Simulator Blend

**What:** Use transition probabilities from replay data to run forward simulations.
**Why:** Ground truth is average of hundreds of MC simulations. If we approximate the
transition function, our predictions align better with the generation process.

**Implementation:**
- We already have `transition_model.py` with `RegimeModel` and 1.77M transitions
- `RegimeModel.predict_cell()` already returns probability distributions per cell
- In predict_and_submit_v2:
  1. Build RegimeModel from all cached rounds (already have the code)
  2. For each cell: `transition_pred = regime_model.predict_cell(grid, y, x, h, w, regime)`
  3. Blend: `pred = 0.6 * model_pred + 0.2 * transition_pred + 0.2 * mlp_pred`
     (or tune weights by regime)

**Actually:** RegimeModel is a lookup table, not a forward simulator. It maps
(initial_neighborhood -> final_distribution) using historical averages.
That IS effectively a Monte Carlo average. Using it as a Dirichlet prior
(base distribution) rather than a blend target would be more principled:
  `alpha_base = transition_pred` instead of `alpha_base = model_pred`

**Final approach:**
- Use RegimeModel predictions as the Dirichlet prior (base distribution)
- LightGBM+MLP blend adjusts the prior with learned corrections
- Observations update via Dirichlet as before
- This means: `prior = regime_model`, `correction = lgb+mlp blend`, `evidence = observations`

**Risk:** Medium. Changes the Dirichlet base, which is the core prediction mechanism.
**Validation:** Backtest before/after on all cached rounds.

---

## Change C: Spatial Convolution Features

**What:** Add neighborhood context features beyond immediate 8 neighbors.
**Why:** Settlement growth has spatial structure (frontier expansion, mountain barriers).
Per-cell features miss these patterns.

**New features in build_dataset_v6.py:**
1. `settle_density_r5` -- settlement count in radius 5 (already partial: settle_r3)
2. `mountain_cluster` -- count of mountains in radius 3 (barrier strength)
3. `frontier_score` -- number of empty cells adjacent to settlements in radius 3
   (higher = more room to grow)
4. `forest_density_r5` -- forest count in radius 5 (fuel for growth)
5. `port_density_r3` -- port count in radius 3 (trade network)
6. `ruin_density_r3` -- ruin count in radius 3 (recent death signal)

**Implementation:**
- Add to `extract_cell_features()` in build_dataset_v6.py (copy of build_dataset.py)
- Extend FEATURE_NAMES with 6 new features (51 -> 57)
- Rebuild dataset with new features
- Retrain models on 57 features

**Risk:** Low. Additive features. LightGBM handles irrelevant features well.
**Validation:** Feature importance analysis. Backtest score comparison.

---

## Change D: Cross-Seed Information Transfer

**What:** Propagate regime detection from all seeds to improve per-seed predictions.
**Why:** All 5 seeds share hidden params (growth_rate, raid_severity, winter_harshness).
Regime detected from seed 0's observations should explicitly inform seeds 1-4.

**Current state:** Already partially done -- `observe_round_v2` computes `avg_growth`
across all seeds and classifies regime. But per-seed growth ratios aren't used
individually in prediction.

**Implementation:**
- After observing all 5 seeds, compute cross-seed statistics:
  - `cross_seed_avg_growth`: mean growth across all seeds
  - `cross_seed_std_growth`: std of growth (low = confident regime)
  - `cross_seed_max_growth`: max growth (catches outlier explosions)
  - `cross_seed_min_growth`: min growth
- Inject these as 4 extra features into each seed's prediction
- Use growth_std to modulate alpha: low std = more confident = higher alpha

**Risk:** Low. Extra features + alpha modulation.
**Validation:** Check if cross-seed stats improve backtest.

---

## Change E: Regime-Specific Observation Weighting

**What:** More nuanced alpha (Dirichlet weight) based on regime confidence.
**Why:** Current system: death=5, stable=30, growth=15, extreme_growth=3.
But "stable" is the hardest regime -- model is least reliable there.
We should trust observations MORE for stable (lower alpha), not less.

**Current alphas and their meaning:**
- alpha=5 (death): trust obs heavily (model agrees with obs anyway)
- alpha=30 (stable): trust model heavily (but model is worst for stable!)
- alpha=15 (growth): moderate trust
- alpha=3 (extreme growth): almost pure obs

**Proposed revision:**
- death: alpha=5 (keep -- model and obs agree)
- stable_confident (low growth_std): alpha=15 (reduce from 30)
- stable_uncertain (high growth_std): alpha=8 (trust obs more)
- growth: alpha=12 (slight reduction)
- extreme_growth: alpha=3 (keep)

**Also:** Scale alpha by observation coverage. If a cell has 3+ observations,
alpha matters less (obs dominate anyway). If 1 observation, alpha matters a lot.

**Implementation:**
- Compute `regime_confidence` from cross-seed growth_std (Change D)
- Map to alpha using a lookup table with confidence tiers
- Optionally: per-cell alpha based on observation count

**Risk:** Low. Tuning existing parameter.
**Validation:** Backtest with different alpha schedules.

---

## Execution Order

```
A. MLP Ensemble          -> overnight_v6.py: add MLPRegressor training + blending
B. MC Simulator Blend    -> overnight_v6.py: integrate RegimeModel as Dirichlet prior
C. Spatial Features      -> build_dataset_v6.py: 6 new features (51->57)
                         -> overnight_v6.py: use build_dataset_v6
D. Cross-Seed Transfer   -> overnight_v6.py: 4 cross-seed stats as features + alpha mod
E. Regime Alpha Tuning   -> overnight_v6.py: confidence-based alpha schedule
```

Each change goes through Boris: Code -> Review -> Simplify -> Validate -> Commit.
Changes are cumulative (B builds on A, C on B, etc).

## Files Created/Modified

| File | Action | Purpose |
|------|--------|---------|
| overnight_v6.py | CREATE | New autonomous handler with all 5 improvements |
| build_dataset_v6.py | CREATE | Extended feature extraction (57 features) |
| plan-v6.md | CREATE | This plan |

## Dependencies

- sklearn (MLPRegressor) -- should be on GCP already
- lightgbm -- already on GCP
- numpy -- already on GCP
- regime_model.py -- already exists, import RegimeModel
- build_dataset.py -- base for v6 copy
- backtest.py -- unchanged, shared utilities
