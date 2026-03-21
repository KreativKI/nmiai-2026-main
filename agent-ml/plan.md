# Astar Island -- Multi-Seed Intelligence Plan

**Created:** 2026-03-22 01:00 CET
**Deadline:** Sunday 2026-03-22 15:00 CET
**Status:** overnight_v4 PAUSED. Cron DISABLED. R19 queries PRESERVED.

## Problem Statement

4 of 5 seeds run blind. The model's top features (61% importance) default to
constants for seeds 1-4 because observations and replay data only exist for
the deep-stacked seed. This is 80% of our per-round submissions running on
a model that can't distinguish death from growth.

## The Fix

9 queries = complete 40x40 map for one seed.
5 seeds x 9 queries = 45 queries.
Budget = 50 queries.
**We can map ALL 5 seeds completely with 5 queries to spare.**

Every seed gets:
- Full year-50 terrain map (1600 cells observed)
- obs_settle_growth computed (our #2 feature, 14.2% importance)
- obs_forest_ratio computed
- Regime classification signal
- Dirichlet blending (1 observation per cell)
- No blind features

## Two Parallel Paths

### Path 1: Multi-Seed Observation (on ml-brain)

Modify observe_round() to spread queries across all 5 seeds.

**Current observe_round():**
```
5 queries: smell test on deep_seed
45 queries: deep-stack deep_seed (re-observe same cells 5x)
Result: 1 seed with ~5 obs per cell, 4 seeds with nothing
```

**New observe_round():**
```
For each seed 0-4:
  9 queries: full grid coverage (3x3 tiling of 15x15 viewports)
5 remaining queries: extra observations on seed 0
Result: ALL 5 seeds with 1 obs per cell, seed 0 with 1-2 obs per cell
```

**Changes to predict_and_submit():**
- Compute obs_settle_growth PER SEED (not just deep seed)
- Each seed gets its own obs_counts and obs_total arrays
- Regime classification from average obs_settle_growth across ALL 5 seeds
  (5 independent samples of same hidden params = more reliable estimate)
- Dirichlet blending on ALL seeds (1 obs per cell, alpha-weighted)
- obs_settle_growth injected into trajectory features for ALL seeds

**Data structures:**
```python
# Instead of: obs_counts (40,40,6), obs_total (40,40) for one seed
# Now: per_seed_obs = {seed_idx: (obs_counts, obs_total)} for all 5
```

**Regime from 5 seeds:**
```python
# Average obs_settle_growth across all 5 seeds
growth_ratios = [compute_obs_settle_growth(per_seed_obs[si], ig[si]) for si in range(5)]
avg_growth = np.mean(growth_ratios)
# Use avg for regime (5 samples = more robust than 1)
if avg_growth < 0.9: regime = "death"
elif avg_growth > 1.4: regime = "growth"
else: regime = "stable"
```

### Path 2: Temperature Calibration + Physics Prior (on ml-churn)

Run in parallel while Path 1 is implemented.

**Temperature calibration:**
For each of 17 rounds, grid-search temperature T per regime:
```python
calibrated = pred ** (1/T)
calibrated /= calibrated.sum(axis=-1, keepdims=True)
```
Optimize T to minimize KL divergence against ground truth.
Three T values: T_death, T_stable, T_growth.

**Physics prior (transition model as Dirichlet base):**
For cells with low observation coverage, use transition_model.py predictions
instead of LightGBM as the Dirichlet prior. The transition model knows:
- Settlements expand into forests
- Ports only form on coasts
- Ruins are transitional
- Mountains/ocean never change

Test: blend LightGBM + transition_model predictions and measure
if the blend scores better than LightGBM alone on held-out rounds.

---

## Implementation Details

### Path 1: observe_round_v2()

New function that replaces observe_round():

```python
def observe_round_v2(session, round_id, detail, round_num):
    """Observe ALL 5 seeds with full grid coverage."""
    h, w = detail["map_height"], detail["map_width"]
    seeds_count = detail.get("seeds_count", 5)

    # 3x3 viewport tiling for full coverage
    viewports = []
    for vy in range(0, h, 15):
        for vx in range(0, w, 15):
            viewports.append((vx, vy, min(15, w-vx), min(15, h-vy)))

    per_seed_obs = {}
    budget_used = 0

    for seed_idx in range(seeds_count):
        oc = np.zeros((h, w, NUM_CLASSES))
        ot = np.zeros((h, w))

        for vx, vy, vw, vh in viewports:
            obs = query_viewport(session, round_id, seed_idx, vx, vy, vw, vh)
            accumulate_obs(obs, oc, ot)
            budget_used += 1

        per_seed_obs[seed_idx] = (oc, ot)
        np.save(DATA_DIR / f"obs_counts_r{round_num}_seed{seed_idx}_full.npy", oc)
        np.save(DATA_DIR / f"obs_total_r{round_num}_seed{seed_idx}_full.npy", ot)

    # Extra queries on seed 0 (remaining budget)
    remaining = 50 - budget_used
    for _ in range(remaining):
        vx, vy, vw, vh = viewports[_ % len(viewports)]
        obs = query_viewport(session, round_id, 0, vx, vy, vw, vh)
        oc0, ot0 = per_seed_obs[0]
        accumulate_obs(obs, oc0, ot0)

    # Regime from all seeds
    growth_ratios = []
    for seed_idx in range(seeds_count):
        ig = detail["initial_states"][seed_idx]["grid"]
        oc, ot = per_seed_obs[seed_idx]
        obs_argmax = oc.argmax(axis=2)
        observed = ot > 0
        settle_count = int(((obs_argmax == 1) | (obs_argmax == 2))[observed].sum())
        init_settle = sum(1 for y in range(h) for x in range(w)
                         if TERRAIN_TO_CLASS.get(int(ig[y][x]), 0) in (1,2))
        growth_ratios.append(settle_count / max(init_settle, 1))

    avg_growth = np.mean(growth_ratios)
    if avg_growth < 0.9: regime = "death"
    elif avg_growth > 1.4: regime = "growth"
    else: regime = "stable"

    log(f"  Multi-seed regime: {regime} (avg_growth={avg_growth:.2f}, "
        f"per_seed={[f'{g:.1f}' for g in growth_ratios]})")

    return per_seed_obs, regime, growth_ratios
```

### Path 1: predict_and_submit_v2()

Modified to accept per_seed_obs and apply Dirichlet + obs proxies per seed:

Key changes:
- Loop over seeds, each seed gets its own obs_counts/obs_total
- obs_settle_growth computed per seed and injected into trajectory features
- Dirichlet blending on ALL seeds (not just deep seed)
- Per-regime alpha applied to all seeds

### Path 2: temperature_calibration.py

```python
def find_optimal_temperature(rounds_data):
    """Grid search T per regime to minimize KL divergence."""
    for regime in ("death", "stable", "growth"):
        best_T, best_score = 1.0, 0.0
        for T in np.arange(0.5, 3.0, 0.1):
            scores = []
            for round in rounds_of_regime:
                pred = model.predict(round)
                calibrated = pred ** (1/T)
                calibrated /= calibrated.sum(axis=-1, keepdims=True)
                scores.append(score_prediction(gt, calibrated))
            avg = np.mean(scores)
            if avg > best_score:
                best_T, best_score = T, avg
        print(f"{regime}: T={best_T:.1f}, score={best_score:.1f}")
```

---

## Evaluation Protocol

### Backtest before deployment
For each of 17 rounds, simulate the new observation strategy:
1. Use replay year-50 frames as simulated observations (1 per seed)
2. Compute per-seed obs_settle_growth
3. Compute 5-seed average regime
4. Predict with LightGBM using obs proxies on all seeds
5. Apply temperature calibration
6. Score against ground truth
7. Compare to current approach (deep-stack 1 seed, 4 blind)

### Metrics
- Overall score (average across all rounds, all seeds)
- Per-seed score (does seed 1-4 improve? Does seed 0 degrade?)
- Per-regime score (death/stable/growth breakdown)
- Regime classification accuracy (5-seed average vs 1-seed smell test)

---

## Environment Assignment

| Environment | Path | Work |
|-------------|------|------|
| ml-brain | Path 1 | Multi-seed observation (overnight_v5.py) |
| ml-churn | Path 2 | Temperature calibration + physics prior |
| Local Mac | Neither | Plan writing, audit, code review only |

Both paths deploy results to ml-brain for final integration.

---

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| 1 obs per cell is too noisy for Dirichlet | With alpha=15, 1 obs gives 6% weight. Small but non-zero correction. Better than 0%. |
| Seed 0 loses deep-stack advantage | Gets 14 queries (9 + 5 extra) = ~1.5 obs per cell. Modest reduction from ~5 obs. |
| Regime from 5 seeds disagrees with itself | Average is more robust. Individual seed variance is expected (R15: 4.1 to 10.3). |
| Code change breaks submission | Backtest on 17 rounds before deployment. overnight_v4 code preserved as fallback. |

---

## Execution

```
Path 1 (ml-brain):
  1. Write observe_round_v2() and predict_and_submit_v2()
  2. Boris workflow (review, simplify, validate)
  3. Backtest on 17 rounds (simulated multi-seed observations)
  4. Deploy as overnight_v5.py if backtest shows improvement

Path 2 (ml-churn):
  1. Write temperature_calibration.py
  2. Grid search T values on 17 rounds
  3. Write physics_prior.py (transition model blending)
  4. Test blend on 17 rounds
  5. Deploy winning calibration to overnight_v5.py

Integration:
  - Merge Path 1 + Path 2 winners into overnight_v5.py
  - Re-enable cron
  - Start R19 submission
```

Boris workflow on each code change.
Audit gate before final deployment.

## Audit Fixes (mandatory before deployment)

### Fix 1: Error handling in observe_round_v2
Wrap each query_viewport call in try/except per seed. A single failed
query must not abort remaining seeds. Return partial data gracefully.
Validate budget_used against live API budget after the loop.

### Fix 2: Resubmit file naming
v5 saves obs files as `_full.npy`, v4 used `_stacked.npy`.
Update run_cycle resubmit logic to check for both naming conventions.

### Fix 3: Temperature calibration independence
Run T calibration on multi-seed simulation data (Path 1 output),
not on single-seed v4 baseline. T values must match the prediction
distribution they will be applied to.
