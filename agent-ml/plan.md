# Astar Island — Plan

**Track:** ML | **Task:** Norse World Prediction | **Weight:** 33.33%
**Last updated:** 2026-03-20 02:15 UTC

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

## Current Script
`solutions/astar_v5.py` — production script for round 4+

## What We've Learned (rounds 1-3)
- Only 10-40/1600 cells change dominant class per round (97-99% static)
- Round 2: mass settlement die-off on some seeds (23 settlements -> empty)
- Hidden parameters vary significantly between rounds
- Neighborhood context matters: cells near settlements have different transitions
- Cookie auth required for API (not Bearer header)
- Broadcasting bug: always test with synthetic observations before real queries

## Round 4 Plan (ACTIVE)
**Score to beat:** 39.7 (round 3 avg)
**Main error source:** Forest MAE 0.23, Empty MAE 0.19

### Phase 1: Overview (9 queries on seed 0)
- Tile seed 0 fully with 3x3 viewports (9 queries, 15x15 each)
- This gives us ONE stochastic realization of the full map for seed 0
- Compare with initial terrain to see what changed
- Identify: which settlements survived? Which forests were cleared? Any new ports?

### Phase 2: Analyze (0 queries)
- Build round-4-specific transition counts from phase 1 data
- Compare with rounds 1-3 transition rates: is this round more/less destructive?
- Identify high-uncertainty zones: cells where initial terrain != observed terrain
- Decide: where to stack queries for multi-sample probability estimates?

### Phase 3: Targeted stacking (20-25 queries on seed 0)
- Stack 2-3 queries on each high-uncertainty zone
- Multiple observations of same cell -> empirical probability distribution
- Focus on settlement frontiers (forest/empty adjacent to settlements)

### Phase 4: Secondary seed coverage (16 queries on seeds 1-2)
- Seed 1: 9 queries (full coverage)
- Seed 2: 7 queries (partial coverage, focus on dynamic areas)
- Seeds 3-4: rely entirely on cross-seed transfer

### Phase 5: Build & Submit
- Build round-4-specific transitions from all observations
- Blend 70/30 with historical (3 rounds of ground truth)
- For observed cells: use empirical distribution directly (weighted by sample count)
- Floor at 0.01, renormalize, validate
- Submit all 5 seeds

**Total budget:** 9 + 0 + ~22 + ~16 = ~47 queries (3 spare)

## Open Research Questions
- How much do hidden parameters vary between rounds? (answer: significantly)
- What's the actual dynamics model? (CA-like? Global interactions?)
- Can we infer hidden parameters from cross-seed observations?
- Does stacking observations (multiple queries on same area) actually improve score?
