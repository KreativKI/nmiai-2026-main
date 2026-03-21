# Astar Island -- Plan

**Last updated:** 2026-03-21 18:00 UTC
**Best:** 169.6 (R15) | **Rank:** 141 | **Top 1:** 196.6 | **Deadline:** Sunday 15:00 CET (~21h)

## Audit Score: 3/10. Fixing it NOW.

### Problem: 3-star model, 1-star operations.

## Priority 1: overnight_v4.py (DO THIS FIRST)
Autonomous round handler using 32-feature V4 model.
Deploy to ml-brain VM. Runs 24/7. Never misses a round.

Includes:
- Round detection + submission (V4 32-feat, 50 trees)
- Deep stack with seed rotation
- Auto data pipeline after each round (cache GT, replay, rebuild dataset)
- Reads churn params from local disk (churn writes brain_v4_params.json)
- Calibrator: logs backtest estimate vs actual after each score

## Priority 2: Update churn_v4 to 32 features
Kill current churn (optimizing wrong 13-feat model).
Deploy updated churn that uses build_dataset.py with 32 features.
Runs on ml-churn.

## Priority 3: Everything else is secondary
- Hindsight analysis: nice to have, built into overnight_v4
- Variant testing: built into overnight_v4 resubmit window
- Feature engineering experiments: only if priorities 1+2 are deployed

## GCP Allocation
| VM | Process | Model |
|----|---------|-------|
| ml-brain | overnight_v4.py (autonomous submitter) | V4 32-feat |
| ml-churn | churn_v4.py (hyperparam optimizer) | V4 32-feat |

## Round Workflow (all automated in overnight_v4)
1. Detect round -> smell test -> deep stack rotating seed
2. Train V4 on master dataset -> predict -> submit
3. During window: check churn params, resubmit if better
4. After close: run data_pipeline (cache GT, replay, rebuild dataset, calibrate)

## Calibration (V4 32-feat, from actual data)
| Regime | Backtest Offset | Meaning |
|--------|----------------|---------|
| Death | +15.6 | Backtest says 80, actual ~64 |
| Growth | +5.5 | Backtest says 75, actual ~70 |
| Stable | +13.4 | Backtest says 80, actual ~67 |
| Overall | +11.6 | Backtest overshoots by ~12 |

## Deep Stack Rotation
R17=seed 2, R18=seed 3, R19=seed 4, R20=seed 0
