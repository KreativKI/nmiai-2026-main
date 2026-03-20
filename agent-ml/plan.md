# Astar Island — Plan

**Track:** ML | **Task:** Norse World Prediction | **Weight:** 33.33%
**Last updated:** 2026-03-20 22:35 UTC
**Rank:** ~100/221 | **Best:** 82.6 (R9) | **Target:** 90+

## Architecture
- **v7** = the chef (full pipeline: observe, detect regime, predict, submit)
- **V2 NeighborhoodModel** = the recipe book (transition lookup table inside v7)
- **overnight_runner.py** = the line cook on GCP (runs v7 every round, auto-submits)

## Score History
| Round | Score | Rank | Regime |
|-------|-------|------|--------|
| R3 | 39.7 | 33/100 | death |
| R4 | 71.8 | 49/86 | death |
| R5 | 67.6 | 69/144 | stable |
| R6 | 70.4 | 52/186 | growth |
| R7 | 55.1 | 112/199 | growth |
| R8 | 61.8 | 126/214 | death |
| R9 | 82.6 | 93/221 | death |
| R10 | pending | - | death+regrowth |

---

## DONE: Phases 1-2
- Retrained model on 9 rounds (72K cells)
- R10 resubmitted with Settlement->Forest fix (35% new transition)
- overnight_runner.py deployed to GCP VM ml-churn

## ACTIVE: Phase 3 — Parallel GCP Experiments (Option D)
**Goal:** Run 4 experiments in parallel on GCP. Results feed into upgraded overnight runner before R11.

### Track 1: Grid Search (RUNNING on ml-churn)
Find optimal post-processing params: temperature, collapse, smoothing, prior strength.
Status: running on ml-churn VM.

### Track 2: Regime-Specific Model
Train separate recipe books per regime (death/stable/growth).
Backtest result: +3.37 avg vs global. Growth rounds +8.8.
Status: regime_model.py built and tested locally. Deploy to GCP.

### Track 3: Query Strategy Simulation
Test different tasting menus for 50 queries. Key question: skip seeds 3-4, stack deeper on 0-1?
Current: 5 regime + 45 overview + 5 stack = thin coverage everywhere.
Alternative: 5 regime + 27 overview (3 seeds) + 18 deep stack = thick coverage on fewer seeds.
Status: needs simulation script built and deployed.

### Track 4: Reinforcement Weighting
Weight the recipe book by recency and regime match. Penalize recipes that scored badly.
- Recent rounds count more (exponential decay)
- Regime-matching rounds count more (2x weight for same regime)
- Cells with high backtest error get wider probability spreads
Status: needs implementation.

## Phase 4 — Upgrade Overnight Runner
Integrate best results from Tracks 1-4 into v8.
Deploy upgraded runner to ml-churn before R11 opens (~00:00 UTC).

## Phase 5 — Autonomous Overnight
v8 overnight runner handles R11+ with improved model.

## Phase 6 — Morning Review (Sunday ~09:00 CET)
Check scores, deploy any final improvements, feature freeze.

## Phase 7 — Competition Close (Sunday 15:00 CET)
Final submission, repo public at 14:45.
