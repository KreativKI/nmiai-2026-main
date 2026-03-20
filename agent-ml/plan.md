# Astar Island — Plan

**Track:** ML | **Task:** Norse World Prediction | **Weight:** 33.33%
**Last updated:** 2026-03-20 21:55 UTC

## Current State
- **Best score:** 82.6 (R9, rank 93/221)
- **R10:** resubmitted with 9-round model + observations. Score pending. Closes ~23:46 UTC.
- **Model:** V2 NeighborhoodModel, 9 rounds training (72K cells), backtest avg 65.6
- **Script:** astar_v7.py + overnight_runner.py (autonomous)
- **GCP VM:** ml-churn running overnight_runner.py (PID 8653, 5-min interval)

## Score History
| Round | Score | Rank | Regime | Notes |
|-------|-------|------|--------|-------|
| R3 | 39.7 | 33/100 | extinction | No regime detection |
| R4 | 71.8 | 49/86 | extinction | Best until R9 |
| R5 | 67.6 | 69/144 | stable | |
| R6 | 70.4 | 52/186 | growth | |
| R7 | 55.1 | 112/199 | growth | Hard round |
| R8 | 61.8 | 126/214 | extinction | Missed death detection |
| R9 | 82.6 | 93/221 | stable | Best round |
| R10 | pending | - | growth | First v7 submission |

---

## Phase 1: R10 Improvement -- DONE
**Goal:** Cache R9 ground truth, retrain model, resubmit R10.
1. DONE: Cached R8+R9 ground truth (was missing from cache)
2. DONE: Retrained V2 model (9 rounds = 72K cells, backtest 65.6 avg, was 64.5)
3. DONE: Resubmitted R10 with retrained model + observations for all 5 seeds
4. INCIDENT: VM runner started and falsely detected extinction (no obs available, 0% survival). Submitted bad model-only predictions. Fixed by resubmitting from local.
5. FIX: overnight_runner.py now checks budget before attempting observations. Falls back to disk observations.

## Phase 2: Overnight Automation -- DONE
**Goal:** Deploy autonomous overnight operation to GCP VM.
1. DONE: Built overnight_runner.py (5-min interval, full round lifecycle)
2. DONE: Deployed v7 + observations + ground truth to VM
3. DONE: Fixed false extinction bug, added budget-check guard
4. DONE: Running as PID 8653 on ml-churn VM
5. Safety: budget check before obs, disk fallback, exception handling, state persistence

## Phase 3: Overnight Automation (GCP VM, ~15 hours)
**Goal:** Submit every round automatically, retrain model after each.
**Status:** ACTIVE. overnight_runner.py handles everything.
3. If round just completed:
   - Cache ground truth via analysis API
   - Retrain V2 model with new data
   - Log: training cells count, model configs
4. Write all activity to `~/overnight_log.txt`

### What the VM needs:
- Latest v7 code (solutions/)
- JWT token
- Python venv with scipy
- Cached ground truth from all completed rounds
- The overnight_runner.sh script

### Safety rules:
- Never skip a round (submit with whatever model is ready)
- Floor all probabilities at 0.01
- Validate predictions before submitting (shape, sum, floors)
- Log every action
- If anything crashes: fall back to model-only predictions (no observations)

## Phase 4: Morning Review (Sunday ~09:00 CET)
1. Read `~/overnight_log.txt` from GCP VM
2. Check leaderboard position
3. Review scores from overnight rounds
4. Any model improvements from accumulated data
5. Feature freeze at 09:00 CET

## Phase 5: Competition Close (Sunday 15:00 CET)
1. 09:00: feature freeze, no more code changes
2. Final submission with best model
3. 14:45: repo goes public automatically
4. 15:00: competition ends

---

## V7 Architecture (current best)
1. **Regime detection:** 5 queries on known settlement positions
2. **Full coverage:** 9 queries per seed x 5 seeds = 45 queries
3. **Stacking:** remaining queries on seed 0 high-value cells
4. **V2 NeighborhoodModel** trained on all completed rounds
5. **Dirichlet-Categorical** observation blending (ps=12)
6. **Extinction calibration:** override settlement probs when death detected
7. **Port constraint:** zero port prob on non-coastal cells
8. **Post-processing:** T=1.12, collapse=0.016, smooth=0.3

## Backtest Results
| Strategy | Avg Score | vs V6 |
|----------|-----------|-------|
| V6 (50 queries seed 0) | 63.6 | baseline |
| V7 (multi-seed overview) | 65.9 | +2.3 |
| V7b (regime-first) | 70.3 | +6.7 |

## Hidden Rules (verified from ground truth)
- See: `solutions/data/hidden_rules_analysis.md`
- Three regimes: extinction / stable / growth
- Settlement spread radius: 3-12 Manhattan distance (per round)
- Ports = coastal only (100%)
- Forests consumed by adjacent settlements
- Mountains kill adjacent settlements
- Ruins never argmax (<10%)
- Ground truth = 200 Monte Carlo simulation runs

## Key Learnings
- Regime detection is the #1 scoring lever (+30 points on death rounds)
- Observing all 5 seeds beats stacking on 1 seed (+2-4 points avg)
- Model improvements plateau fast, query strategy matters more
- Each round of ground truth improves predictions (continuous learning)
