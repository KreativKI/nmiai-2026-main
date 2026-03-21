# Astar Island -- Plan

**Track:** ML | **Last updated:** 2026-03-21 17:45 UTC
**Best weighted:** 169.6 (R15) | **Rank:** 141 | **Top 1:** 196.6 | **Deadline:** Sunday 15:00 CET

---

## The Problem

We have a 40x40 grid. We must predict what each cell looks like after 50 years of simulation. We get 50 observation queries per round. Later rounds have higher weights.

## What We Have That We're Not Using

| Data Source | Volume | Currently Used? |
|------------|--------|----------------|
| 69 replay files (51 frames each, terrain + settlement stats) | ~3.5M cell-states | **NO** |
| Settlement stats per cell per year (food, pop, wealth, defense) | ~175K settlement snapshots | **NO** |
| Year-by-year terrain transitions (what happens at year 10, 25, 40) | 69 x 50 transitions | **NO** |
| Faction/owner data per settlement | All replays | **NO** |
| 15 rounds of ground truth (initial + final) | 102K cells | Yes (V4 trains on this) |

We're using 3% of our data. The top teams at 196 are almost certainly using more.

---

## The Plan: Master Dataset + Pipeline

### Step 1: Build the Master Dataset
Create `build_dataset.py` that extracts EVERY feature from EVERY data source into one flat table. Each row = one cell from one seed from one round.

**Features per cell (30+):**

Spatial (from initial grid):
- Terrain type (one-hot: 6)
- 8-neighbor terrain counts (6)
- Distance to nearest settlement (1)
- Settlement count within radius 3 (1)
- Forest count within radius 2 (1)
- Ocean adjacency count (1)
- Edge distance (1)
- Is on coastline (1)

Settlement stats (from replay year 0):
- Population (1)
- Food (1)
- Wealth (1)
- Defense (1)
- Has port (1)
- Owner/faction ID (1)

Temporal (from replay intermediate frames):
- Alive at year 10? (1)
- Alive at year 25? (1)
- Settlement count at year 10 in neighborhood (1)
- Settlement count at year 25 in neighborhood (1)
- Food trend year 0->10 (1)

Round-level:
- Regime indicator (growth/death/stable) (3)
- Total initial settlements on map (1)
- Total initial ports (1)

**Target:** 6-class probability distribution at year 50 (from ground truth)

**Estimated size:** 15 rounds x 5 seeds x ~700 dynamic cells = ~52K rows x ~35 features

### Step 2: Data Pipeline Script
Create `data_pipeline.py` that runs after every round:

```
1. Fetch ground truth (GET /analysis)
2. Fetch replay (POST /replay) for all 5 seeds
3. Extract features into master dataset format
4. Append to master_dataset.csv (or .npz)
5. Upload to GCP (scp to ml-churn and ml-brain)
6. Trigger model retrain on GCP
```

This script should be idempotent (safe to run multiple times).

### Step 3: Retrain V4 on Master Dataset
Update brain_v4 to use the full feature set (35 features instead of 13).
Train on GCP where the dataset lives.

### Step 4: Continuous Improvement on GCP
churn_v4 uses the master dataset for hyperparameter search.
Every time the pipeline adds data, churn picks it up automatically.

---

## GCP Allocation

| VM | What | Status |
|----|------|--------|
| ml-churn | churn_v4 (hyperparam search) + retrain on master dataset | Active |
| ml-brain | Available for parallel experiments or model comparison | Idle |

## Round Workflow Checklist

### After Round Closes
- [ ] Get score from API
- [ ] Run `data_pipeline.py` (caches GT, replay, extracts features, syncs to GCP)
- [ ] Run hindsight (compare prediction vs reality)
- [ ] Check churn_v4 for new best params
- [ ] Log results

### When Round Opens
- [ ] Check churn_v4 params first
- [ ] Smell test (5 queries on deep-stack seed)
- [ ] Deep stack rotating seed (all remaining queries)
- [ ] Test variants against most recent real data
- [ ] Submit with winner
- [ ] Monitor resubmit window

### Deep Stack Rotation
R17=seed 2, R18=seed 3, R19=seed 4, R20=seed 0, R21=seed 1

---

## Score Targets

| Target | R17 (2.29) | R18 (2.41) | R19 (2.53) | R20 (2.65) |
|--------|-----------|-----------|-----------|-----------|
| Top 50 | 73 | 69 | 66 | 63 |
| Top 20 | 76 | 72 | 68 | 65 |
| Top 3 | 77 | 73 | 70 | 67 |
| Top 1 (196.6) | 86 | 82 | 78 | 74 |

## Immediate Next Steps
1. Build `build_dataset.py` with all features from replays
2. Build `data_pipeline.py` for automatic round processing
3. Update `brain_v4.py` to accept the full feature set
4. Deploy to GCP, retrain, backtest
5. Submit R17 with the improved model
