# Astar Island — Plan

**Track:** ML | **Task:** Norse World Prediction | **Weight:** 33.33%
**Last updated:** 2026-03-20 19:55 UTC

## Current State
- **Best score:** 71.77 (R4)
- **Rounds submitted:** 9 (R3-R9, R1-R2 missed)
- **R9:** active, closes 20:47 UTC. Submitted but no improvement found for resubmission.
- **R8 score:** 61.8 (rank 126/214)
- **Seed gap:** Seed 0 scores 5-9 points higher than seeds 1-4 (observed vs unobserved)

## Active Phase: Distance-Based Model + Multi-Seed Strategy

### The Problem (kitchen version)
We taste-test all 50 spoons in one kitchen (seed 0) and guess the other 4 kitchens.
Result: kitchen 0 scores 70-75, kitchens 1-4 score 55-65. 80% of our submission is guesswork.

### What We Just Learned (hidden rules analysis)
A. Settlements spread with a DISTANCE CUTOFF from existing settlements (3-12 Manhattan distance per round)
B. Three round types: death (0% survival), quiet (60-88%), golden age (2-3x growth)
C. Forests consumed by adjacent settlements (97% safe when isolated, 50% when adjacent)
D. Ports only appear next to ocean (100% rule)
E. Mountains kill adjacent settlements
F. Ruins are background noise (<10% probability), never the main answer

### Plan: Build Distance-Aware Model (astar_v7.py)
**Boris: EXPLORE -> PLAN -> CODE -> REVIEW -> VALIDATE -> COMMIT**

#### Step 1: Distance model (CODE)
Build a prediction model that uses:
- Manhattan distance from each cell to nearest initial settlement
- Round regime detection (death/quiet/growth) from seed 0 observations
- Distance-dependent settlement probability curves (learned from 35 ground truth maps)
- Forest consumption rules (adj settlement count)
- Port = coastal only
- Ruin = 2-4% background

#### Step 2: Multi-seed query strategy (CODE)
Test new strategy: 10 queries per seed (full coverage of all 5 kitchens)
- 9 queries = full map, 1 extra for highest-value cell
- Regime detection from ANY seed helps ALL seeds
- With distance model, even 1 observation per cell may be enough

#### Step 3: Backtest (VALIDATE)
- Leave-one-out on 7 rounds
- Compare: current V2 (seed 0 only, 50 queries) vs distance model (all seeds, 10 each)
- Run in simulator with Monte Carlo trials

#### Step 4: Deploy + Submit R10 (if improved)

### Time Budget
- R9 closes: 20:47 UTC
- R10 opens: ~21:02 UTC
- Build time: ~30 min
- Backtest: ~10 min
- Decision point: 21:00 UTC

---

## Hidden Rules (verified from ground truth analysis)
See: `solutions/data/hidden_rules_analysis.md`
Shared with overseer: `intelligence/for-overseer/hidden-rules-discovery.md`

### Immutable (100% confidence)
- Mountains never change
- Ocean -> Empty always
- Ports require ocean adjacency
- Empty never becomes Forest
- Ground truth = 200 Monte Carlo runs

### Per-Round Hidden Parameters
- Settlement spread radius (3-12 Manhattan distance)
- Survival rate (0% to 88%)
- Growth multiplier (0x to 2.86x)
- Forest consumption rate

---

## Model Stack (current v6)
1. V2 NeighborhoodModel (1102 configs)
2. Dirichlet Bayesian observation blend (ps=12)
3. Temperature T=1.12, collapse=0.016, smooth=0.3
4. Backtest avg: 64.5

## Answered Questions (this session)
- Batch size 5 vs 8 vs 10: no significant difference (SIM-001)
- Per-class temperature: doesn't help (PP-001)
- Equilibrium iteration: hurts (EQ-001)
- Tile values: empty cells = 64% of score weight, edges most valuable
- Seed 0 vs 1-4 gap: 5-9 points (the biggest improvement opportunity)
