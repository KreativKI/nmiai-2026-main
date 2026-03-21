# Astar Island -- Plan

**Track:** ML | **Last updated:** 2026-03-21 15:15 UTC
**Best weighted:** 134.2 (R14) | **Rank:** 162 | **Top 3:** 177 | **Deadline:** Sunday 15:00 CET

## GCP VMs
| VM | Purpose | Status |
|----|---------|--------|
| ml-churn | Approach A: V4-R (replay-trained LightGBM) comparison running | Active |
| ml-brain | Approach B: V5 (step-forward simulator) comparison | Setting up |

## Models Under Test
| Model | Training Data | Description | Status |
|-------|-------------|-------------|--------|
| V4 | 14 rounds x 5 seeds, initial->final (95K cells) | LightGBM, 13 features | **Current best. +6.2 vs V3 on R14.** |
| V4-R | 69 replays x 50 steps x ~700 cells (~2.4M transitions) | V4 + temporal features + settlement stats | Running comparison on ml-churn |
| V5 | Same replay data, 5-year step transitions | Step-forward: runs model 10 times to simulate 50 years | Running comparison on ml-brain |

## Round-to-Round Workflow (MANDATORY every round)

### Phase 1: Round Opens (0-5 min)
1. Detect new round via API
2. Get initial states for all 5 seeds
3. Smell test: 5 queries on deep-stack seed to detect regime

### Phase 2: Observe (5-15 min)
1. Deep stack: ALL remaining queries on ONE seed (rotate: R16=seed 1, R17=seed 2...)
2. Capture settlement stats from every /simulate response
3. Save observations to disk (obs_counts, obs_total)

### Phase 3: Test Variants (15-30 min)
**This is the step we kept skipping. Non-negotiable.**
1. Load most recent completed round's ground truth + real observations
2. Generate predictions with EACH available model variant:
   - V4 + Dirichlet obs (current)
   - V4-R replay-trained (if ready)
   - V5 stepper (if ready)
3. Score each variant against the real ground truth
4. Test Dirichlet alpha values (8, 12, 16, 20, 25, 30)
5. Pick the winner based on SCORED DATA

### Phase 4: Submit (30-35 min)
1. Generate predictions with winning variant + calibrated alpha
2. Validate: floor >= 0.01, normalized, shape 40x40x6, all 5 seeds
3. Submit all 5 seeds

### Phase 5: Resubmit Window (35 min - round close)
1. If V4-R or V5 comparison finishes during this window, test against latest ground truth
2. If new variant beats current submission, resubmit
3. Do NOT resubmit without real-data testing

### Phase 6: Round Closes
1. Fetch and cache ground truth for all 5 seeds
2. Download replay data for all 5 seeds (FREE, no query cost)
3. Retrain all models with new data
4. Run hindsight analysis: what did we get wrong?
5. Update calibration offsets
6. Log results to EXPERIMENTS.md

## Query Strategy
- Deep stack on ONE seed per round (rotate: R16=1, R17=2, R18=3, R19=4, R20=0)
- Same tiling positions (9 viewports cover 40x40), repeated 5x for ~5 obs/cell
- Each repeat gives independent simulation results (stochastic)
- Settlement stats captured from every query response

## Discovery: Replay API
`POST /astar-island/replay` returns 51 frames (year 0-50) with full terrain grid + settlement stats per frame. FREE, no query cost. Available for completed rounds only.
- 69/70 replays cached in data/replays/
- Gives 50x more training data than initial->final approach
- Settlement stats per year reveal growth curves, conflict timing, resource depletion

## Score Targets (leaderboard = best score x weight)
| Target | R16 (2.18) | R17 (2.29) | R18 (2.41) | R20 (2.65) |
|--------|-----------|-----------|-----------|-----------|
| Top 50 (166) | 76 | 73 | 69 | 63 |
| Top 20 (173) | 79 | 76 | 72 | 65 |
| Top 3 (177) | 81 | 77 | 73 | 67 |

## Next Steps
1. Wait for V4-R and V5 comparison results from GCP
2. R16 opens in ~20 min: deep stack seed 1, test all variants, submit winner
3. After R15 scores: cache ground truth + replay, recalibrate
4. Integrate winning model into overnight_v3 for autonomous night operation
