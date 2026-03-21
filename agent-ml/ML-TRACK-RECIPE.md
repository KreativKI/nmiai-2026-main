# Astar Island ML Track -- Complete Recipe

**Purpose:** Step-by-step instructions for any AI agent to operate this ML track.
No prior knowledge needed. Follow the steps in order.

---

## What This Competition Is

You predict what a 40x40 grid of terrain looks like after 50 years of simulated civilization.
6 terrain types: Empty(0), Settlement(1), Port(2), Ruin(3), Forest(4), Mountain(5).
You output a probability distribution per cell (40x40x6 tensor) for each of 5 seeds.
Scoring: entropy-weighted KL divergence. Higher = better. Max 100.
Leaderboard: your BEST single (round_score x round_weight) across all rounds.

## What You Have

| Resource | Path | Purpose |
|----------|------|---------|
| Brain V4 | `solutions/brain_v4.py` | LightGBM prediction model. Your main tool. |
| Churn V4 | `solutions/churn_v4.py` | Continuous hyperparameter optimizer (runs on GCP). |
| Backtest | `solutions/backtest.py` | Scores predictions against ground truth. |
| Ground truth | `solutions/data/ground_truth_cache/` | Known answers for completed rounds (R1-R15+). |
| Replays | `solutions/data/replays/` | Year-by-year simulation data (FREE from API). |
| Observations | `solutions/data/obs_*.npy` | Deep-stacked query results per round. |
| GCP VM | `ml-churn` (europe-west1-b) | Runs churn_v4. e2-medium, no GPU needed. |
| API | `https://api.ainm.no/astar-island/` | Competition API (see endpoints below). |

## API Endpoints

| Method | Endpoint | Auth | What It Does |
|--------|----------|------|-------------|
| GET | /rounds | No | List all rounds with status |
| GET | /rounds/{id} | No | Round details + initial terrain for all 5 seeds |
| GET | /budget | Yes | How many queries you have left (50 per round) |
| POST | /simulate | Yes | Observe a 15x15 viewport on one seed. Returns terrain + settlement stats. Costs 1 query. |
| POST | /submit | Yes | Submit 40x40x6 prediction for one seed. Can resubmit (overwrites). |
| GET | /my-rounds | Yes | Your scores, ranks, per-seed breakdowns |
| GET | /analysis/{round_id}/{seed} | Yes | Ground truth for completed rounds |
| POST | /replay | Yes | 51 frames (year 0-50) for completed rounds. FREE, no query cost. |
| GET | /leaderboard | No | All teams ranked by best weighted score |

Auth = `Authorization: Bearer {JWT_TOKEN}`

---

## Round Lifecycle Checklist

### When a Round CLOSES (Phase 6)

Do this IMMEDIATELY when a round completes. Every step matters.

- [ ] **6.1 Get score:** `GET /my-rounds` -- find the completed round, note score, rank, per-seed scores, weighted score.

- [ ] **6.2 Cache ground truth:** For each seed (0-4), call `GET /analysis/{round_id}/{seed}`. Save to `data/ground_truth_cache/round_{N}.json`. This is the answer key you'll train on.

- [ ] **6.3 Download replay:** For each seed (0-4), call `POST /replay` with `{round_id, seed_index}`. Save to `data/replays/r{N}_seed{S}.json`. This gives 51 frames of year-by-year terrain + settlement stats. FREE, no query cost.

- [ ] **6.4 Run hindsight:** Compare what you predicted vs what actually happened. Which cells were wrong? Which terrain transitions surprised the model? Log findings.

- [ ] **6.5 Sync to GCP:** Upload the new ground truth file to ml-churn so churn_v4 trains on more data: `gcloud compute scp data/ground_truth_cache/round_{N}.json ml-churn:~/solutions/data/ground_truth_cache/`

- [ ] **6.6 Update calibration:** Compare your backtest estimate for this round vs the actual score. Update your mental model of how much backtest overshoots/undershoots.

- [ ] **6.7 Log to EXPERIMENTS.md:** Record round number, score, model used, params, what worked, what didn't.

### When a Round OPENS (Phases 1-5)

- [ ] **1.1 Detect round:** Poll `GET /rounds` until a new round shows status "active". Note the round_id, closes_at time, round_weight.

- [ ] **1.2 Get initial states:** `GET /rounds/{round_id}` returns initial terrain grids for all 5 seeds.

- [ ] **1.3 Check churn results:** Before doing anything else, check `data/brain_v4_params.json` on GCP. If churn found better hyperparams, use them. `gcloud compute ssh ml-churn --command="cat ~/solutions/data/brain_v4_params.json"`

- [ ] **2.1 Smell test:** Spend 5 queries on the deep-stack seed to detect regime:
  - Find 5 spread-out settlement cells from the initial grid
  - Query 15x15 viewports centered on each
  - Check if settlements are alive or dead in the simulation result
  - 0% alive = death regime, 100% alive = growth, mixed = stable

- [ ] **2.2 Deep stack:** Spend ALL remaining 45 queries on ONE seed (rotate each round):
  - R16=seed 1, R17=seed 2, R18=seed 3, R19=seed 4, R20=seed 0, etc.
  - First pass: tile 9 viewports (15x15) to cover the 40x40 grid
  - Subsequent passes: repeat the SAME viewports (each call runs a new random simulation, giving independent samples)
  - Goal: ~5 observations per cell on the deep-stacked seed
  - Save observations: `np.save(f"obs_counts_r{N}_seed{S}_stacked.npy", obs_counts)` and `obs_total`
  - Also save settlement stats from each /simulate response

- [ ] **3.1 Test variants against REAL data:** This is the most important step. DO NOT SKIP.
  - Load the MOST RECENT completed round's ground truth + observations
  - Generate predictions using your model with different settings
  - Score each variant using `score_prediction(ground_truth, prediction)`
  - Test at minimum: current params vs churn's latest params
  - Test Dirichlet alpha values: 8, 12, 16, 20, 25, 30
  - Pick the variant with the highest REAL score

- [ ] **4.1 Generate predictions:** Use the winning variant from step 3.1:
  ```python
  from brain_v4 import BrainV4, build_dataset
  rounds_data = load_cached_rounds()
  X, Y = build_dataset(rounds_data)
  brain = BrainV4()
  # Use churn-optimized params (currently n_estimators=50)
  params = json.load(open("data/brain_v4_params.json"))
  for cls in range(6):
      model = lgb.LGBMRegressor(n_estimators=params["n_estimators"], ...)
      model.fit(X, Y[:, cls])
      brain.models[cls] = model
  ```

- [ ] **4.2 Apply observations:** For the deep-stacked seed, blend model predictions with observations using Dirichlet:
  ```python
  alpha = 20  # Or whatever variant test showed was best
  for y, x in dynamic_cells:
      a = alpha * pred[y,x]
      a = np.maximum(a, 0.01)
      pred[y,x] = (a + obs_counts[y,x]) / (a.sum() + obs_total[y,x])
  ```

- [ ] **4.3 Validate:** Before submitting, check:
  - Shape: (40, 40, 6) per seed
  - All probabilities >= 0.01 (floor with `np.maximum(pred, 0.01)`)
  - Each cell sums to 1.0 (`pred /= pred.sum(axis=-1, keepdims=True)`)
  - All 5 seeds prepared

- [ ] **4.4 Submit all 5 seeds:**
  ```python
  for seed_idx in range(5):
      session.post(f"{BASE}/astar-island/submit", json={
          "round_id": round_id, "seed_index": seed_idx,
          "prediction": pred.tolist()
      })
  ```

- [ ] **5.1 Resubmit window:** While the round is still open (check closes_at):
  - If churn_v4 finds new best params during this time, test them against real data
  - If better, resubmit
  - If variant test from step 3.1 was inconclusive, run more thorough comparison

---

## What churn_v4 Does (continuous, runs on GCP)

churn_v4 is a hyperparameter optimizer that runs 24/7 on GCP. It:

1. Loads all cached ground truth rounds
2. Picks a hyperparameter to test (cycling through 7 knobs)
3. Trains a V4 model with that setting
4. Backtests on last 5 rounds (leave-one-out)
5. If score improves: saves to `brain_v4_params.json`
6. Repeats with next setting

**The 7 knobs it tunes:**

| Knob | What It Controls | Range | Current Best |
|------|-----------------|-------|-------------|
| n_estimators | Number of decision trees | 50-500 | 50 |
| num_leaves | Complexity per tree | 15-63 | 31 |
| learning_rate | How fast model learns | 0.01-0.15 | 0.05 |
| min_child_samples | Minimum data per decision | 5-50 | 20 |
| subsample | Fraction of data per tree | 0.6-1.0 | 0.8 |
| colsample_bytree | Fraction of features per tree | 0.6-1.0 | 0.8 |
| alpha_dirichlet | Trust model vs observations | 5-40 | 20 |

**How to check its progress:**
```bash
gcloud compute ssh ml-churn --zone=europe-west1-b --project=ai-nm26osl-1779 \
  --command="grep 'NEW BEST' ~/churn_v4.log | tail -5; cat ~/solutions/data/brain_v4_params.json"
```

**How to restart if it dies:**
```bash
gcloud compute ssh ml-churn --zone=europe-west1-b --project=ai-nm26osl-1779 \
  --command="source ~/ml_env/bin/activate && cd ~/solutions && nohup python3 churn_v4.py >> ~/churn_v4.log 2>&1 &"
```

Cron watchdog restarts it every 15 min automatically.

---

## Key Rules (Learned From Mistakes)

1. **NEVER submit without testing against real data first.** Backtest estimates overshoot reality. Test every variant against the most recent completed round's actual observations and ground truth.

2. **NEVER skip the post-round checklist.** Ground truth caching, replay download, GCP sync, hindsight. Every step feeds the next round.

3. **Floor ALL probabilities at 0.01.** A single 0.0 probability causes infinite KL divergence = score 0.

4. **Rotate deep stack seed.** R17=seed 2, R18=seed 3, etc. Don't always query seed 0.

5. **50 trees beats 200 trees.** With only 15 rounds of training data, less model complexity = less overfitting = better predictions.

6. **Observations add ~1-5 points on the deep-stacked seed.** The V4 model itself does most of the work. Even model-only seeds score 80+.

7. **Round weights compound.** Later rounds are worth more. A 70-point score on R22 (weight ~2.9) gives weighted 203 -- better than an 82 on R15 (weight 2.08 = 170). Don't miss late rounds.

8. **Regime detection doesn't matter much for V4.** R15 was misclassified as death (was actually growth) and still scored 81.6. V4 is robust.

---

## Score History

| Round | Score | Rank | Weight | Weighted | Model | Notes |
|-------|-------|------|--------|----------|-------|-------|
| R9 | 82.6 | 93 | 1.551 | 128.1 | V2 deep stack | Best raw before V4 |
| R15 | **81.6** | 137 | 2.079 | **169.6** | V4 + deep stack | Best weighted. V4's first round. |
| R14 | 67.8 | 95 | 1.980 | 134.2 | V3+V2 blend | Last round with old model |
| R16 | pending | - | 2.183 | - | V4 + 50 trees | Resubmitted with churn params |

## Files Reference

| File | What |
|------|------|
| `brain_v4.py` | LightGBM model. `BrainV4` class, `build_dataset()`, `extract_features()` |
| `churn_v4.py` | Hyperparameter optimizer. Runs on GCP continuously. |
| `backtest.py` | `load_cached_rounds()`, `score_prediction()`, `cache_round()`, `get_session()` |
| `regime_model.py` | `classify_round()` for regime detection. `RegimeModel` class (V3, retired). |
| `learned_model.py` | `NeighborhoodModel` (V2, retired but available for blend). |
| `overnight_v3.py` | Autonomous round handler. Currently PAUSED. |
| `brain_v4_replay.py` | Replay-trained model. FAILED (-41 pts). Do not use. |
| `brain_v5_stepper.py` | Step-forward simulator. FAILED (-43 pts). Do not use. |
