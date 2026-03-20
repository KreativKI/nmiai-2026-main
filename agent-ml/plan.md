# Astar Island — Plan

**Track:** ML | **Task:** Norse World Prediction | **Weight:** 33.33%
**Last updated:** 2026-03-19 22:55 CET

## The Problem
Predict terrain probability distributions on a 40×40 grid after 50 years of stochastic simulation. Limited to 50 observation queries across 5 seeds per round. Scored by entropy-weighted KL divergence (0–100).

## Approach A (Primary): Bayesian Prior + Strategic Observation + Cross-Seed Learning

1. **Build strong prior from initial terrain** — mountains and ocean are static (near-certain predictions for free). Forests mostly static. Focus uncertainty on settlement/port/ruin dynamics.
2. **Query strategy (50 budget):** 
   - Seeds 0-1: 15 queries each (deep coverage, ~80% of map with 15×15 viewports)
   - Seed 2: 10 queries (validation)
   - Seeds 3-4: 5 queries each (spot checks)
3. **Cross-seed learning:** All seeds share hidden parameters. Observations from seed 0 teach us about dynamics that apply to ALL seeds.
4. **Prediction:** Blend terrain prior + empirical observations + distance-weighted interpolation. Calibrate uncertainty — never overconfident.
5. **Time:** 2-3 hours for baseline, then iterate each round
6. **Expected:** 40-60 (baseline), 65-80 (with model)

## Approach B (Fallback): Transition Matrix + Markov Chain
1. Estimate terrain transition probabilities from observations
2. Build 6×6 transition matrix
3. Apply Markov chain forward 50 steps
4. Spatial interpolation for unobserved cells
5. **Time:** 2-3 hours
6. **Expected:** 35-50

## Approach C (Baseline — SHIP FIRST): Initial Terrain Prior Only
1. Static cells (mountain, ocean) → near-certain predictions
2. Dynamic cells → spread probability based on terrain type
3. Floor at 0.01, renormalize
4. Zero queries needed — submit immediately
5. **Time:** 30 minutes
6. **Expected:** 15-30

## Round Strategy
- Rounds repeat every ~3h 5m, weights increase 5% each round
- Early rounds: submit baseline, learn from analysis endpoint after scoring
- Later rounds (higher weight): apply learned model, use queries strategically
- **Always submit all 5 seeds** — even bad predictions beat 0

## Validation
- After round completes: use `/analysis/{round_id}/{seed_index}` to compare prediction vs ground truth
- Calculate per-cell KL divergence to find where model is weakest
- Focus next round's queries on high-error regions

## Baseline script ready
`solutions/astar_baseline.py` — needs JWT token, supports --dry-run

## Open Research Questions
- How much do hidden parameters vary between rounds?
- What's the actual dynamics model? (CA-like? Global interactions?)
- Can we infer hidden parameters from cross-seed observations?
