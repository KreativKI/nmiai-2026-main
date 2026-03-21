# Astar Island -- Observation Intelligence Plan v2

**Created:** 2026-03-21 23:00 CET | **Updated:** 2026-03-21 23:30 CET
**Status:** Hail Mary plan COMPLETE. This is the NEXT plan.
**Audit history:** v1 BLOCKED (3 issues). v2 addresses all.

## The Problem

61% of model importance comes from replay-only features that default to 1.0
at prediction time. Our #2 feature (settle_growth_y25, 14.2%) is silent
during live prediction. But observations give us year-50 terrain counts
that could serve as proxies.

## Audit v1 Fixes Applied

A. Correlation analysis is the GATE. No proxy feature is used unless R2 >= 0.5
   against the replay-derived feature across historical data. Features that
   fail stay at 1.0 default.

B. Soft regime blending REMOVED. LightGBM was trained on one-hot regime flags.
   Feeding fractional values (0.3/0.5/0.2) causes unpredictable tree behavior.
   Keep hard thresholds. Improve thresholds if data supports it.

C. The invented proxy wealth_decay = 1/settle_growth REMOVED. No measured
   correlation. Must be validated like any other proxy, not assumed.

D. Current query strategy (deep stack one seed) stays as DEFAULT.
   Multi-seed observation is an EXPERIMENT that requires backtest proof.

E. Out-of-distribution fallback ADDED. If any proxy value exceeds 2x the
   max training value for that feature, fall back to 1.0 and log it.

---

## Phase 1: Correlation Analysis (THE GATE)

### Goal
Determine which observation-derived features are valid proxies for
replay-derived features. Only validated proxies proceed to Phase 2.

### Method
For all 17 rounds x 5 seeds (85 data points), using replay data:

1. Compute "observation-like" features from replay year-50 frame:
   - obs_settle_growth = settle_count_y50 / settle_count_y0
   - obs_forest_ratio = forest_count_y50 / forest_count_y0
   - obs_port_growth = port_count_y50 / max(port_count_y0, 1)

2. Compute actual replay features (what the model was trained on):
   - settle_growth_y25 = settle_count_y25 / settle_count_y0
   - settle_growth_y10 = settle_count_y10 / settle_count_y0
   - wealth_decay_y10 = avg_wealth_y10 / avg_wealth_y0
   - faction_consol_y10 = factions_y10 / factions_y0
   - pop_trend_y10 = avg_pop_y10 / avg_pop_y0
   - food_trend_y10 = avg_food_y10 / avg_food_y0

3. Compute Pearson R2 for each pair:
   - obs_settle_growth vs settle_growth_y25
   - obs_settle_growth vs settle_growth_y10
   - obs_settle_growth vs wealth_decay_y10 (test, don't assume)
   - obs_settle_growth vs faction_consol_y10
   - obs_forest_ratio vs settle_growth_y25 (inverse signal)

4. Decision gate:
   - R2 >= 0.5: proxy is APPROVED for Phase 2
   - R2 0.3-0.5: proxy is EXPERIMENTAL, test in backtest only
   - R2 < 0.3: proxy is REJECTED, feature stays at 1.0

### Note on observation vs replay year-50
Observations are stacked Monte Carlo samples (closer to ground truth).
Replay year-50 is a single simulation (noisier). Phase 1 uses replay
year-50 as a pessimistic proxy. Real observations may correlate better.

File: `observation_analysis.py`

---

## Phase 2: Implement validated proxies (CONDITIONAL on Phase 1)

Only features that passed the R2 >= 0.5 gate get implemented.

### Changes to overnight_v4.py predict_and_submit()

After observations are collected (obs_counts, obs_total), compute:

```python
# Count observed terrain classes from deep-stacked seed
obs_argmax = obs_counts.argmax(axis=2)
observed = obs_total > 0
obs_settle = ((obs_argmax == 1) | (obs_argmax == 2)) & observed
obs_forest = (obs_argmax == 4) & observed

obs_settle_count = obs_settle.sum()
obs_forest_count = obs_forest.sum()

# Compute proxy (only if approved by Phase 1)
obs_settle_growth = obs_settle_count / max(initial_settle_count, 1)
```

### Out-of-distribution guard

For each proxy feature, check against training distribution bounds:

```python
# Computed once from training data
PROXY_BOUNDS = {
    "settle_growth_y25": {"min": 0.0, "max": 8.0},  # from historical data
    "settle_growth_y10": {"min": 0.0, "max": 5.0},
}

# At prediction time
if obs_settle_growth > PROXY_BOUNDS["settle_growth_y25"]["max"] * 2:
    obs_settle_growth = 1.0  # fall back to default
    log("  OOD fallback: obs_settle_growth too high")
```

### Mapping proxies to features

Only approved proxies replace the 1.0 defaults in the trajectory dict.
All other trajectory features stay at 1.0. No invented inverse relationships.

---

## Phase 3: Regime threshold improvement (INDEPENDENT of Phase 2)

### Current approach
```python
if survival < 0.15: regime = "death"
elif survival > 0.60: regime = "growth"
else: regime = "stable"
```

### Proposed improvement
Use obs_settle_growth (computed from full grid, not just 5 cells) for
regime classification. This uses ALL observed cells instead of 5 spots:

```python
obs_settle_growth = obs_settle_count / max(initial_settle_count, 1)
if obs_settle_growth < 0.3: regime = "death"
elif obs_settle_growth > 2.0: regime = "growth"
else: regime = "stable"
```

Still hard thresholds (one-hot regime flags). Still 3 classes.
But computed from full-grid observation data instead of 5 viewport samples.

### Calibration
Use the 85 historical data points to find optimal thresholds.
Grid search over (death_threshold, growth_threshold), pick values
that minimize regime misclassification rate.

---

## Phase 4: Backtest

For each of 17 rounds with replays:
1. Simulate observations from year-50 replay frame
2. Compute observation-derived proxy features
3. Apply improved regime thresholds
4. Predict with 51-feature model (proxies replacing defaults)
5. Score against ground truth
6. Compare to current approach (1.0 defaults, smell-test regime)

### Decision
- If proxies improve overall score by 2+ points: deploy
- If proxies improve some regimes but hurt others: deploy per-regime
- If proxies are neutral or worse: keep current approach

---

## Phase 5: Deploy (CONDITIONAL on Phase 4 results)

Update overnight_v4.py with validated improvements.
Keep current approach as fallback.
Spawn audit before deployment.

---

## Query strategy (future, NOT in this plan)

The current deep-stack strategy (50 queries on 1 seed) is PROVEN.
R9=82.6 and R15=81.6 were scored with this strategy. Changing it
requires backtest evidence that a multi-seed approach beats it.

This is deferred to a separate plan if Phase 2 shows that
observation-derived features significantly help the deep seed.
Only then does spreading queries to other seeds make sense.

---

## Execution

Phase 1 is the gate. If no proxy passes R2 >= 0.5, Phases 2-5 are cancelled
and we focus on other improvements (regime threshold calibration standalone).

Each phase uses Boris workflow.
Audit gates after Phase 1 results and before Phase 5 deployment.
