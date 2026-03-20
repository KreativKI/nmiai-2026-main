#!/usr/bin/env python3
"""
Regime-Calibrated Multi-Seed Model for Astar Island.

Key insight: all 5 seeds share the same hidden parameters.
If we detect the round regime from seed 0 observations, we can calibrate
settlement predictions for ALL seeds.

The model:
1. V2 NeighborhoodModel (base predictions)
2. Regime detection from observations (settlement survival rate)
3. Calibrate: scale settlement probabilities to match detected regime
4. Apply to all seeds (observed and unobserved)

Usage:
  python calibrated_model.py --backtest              # Compare vs V2
  python calibrated_model.py --backtest --multi-seed  # Test 10 queries/seed
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter

import sys
sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    load_cached_rounds, score_prediction, load_real_observations,
    TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, PROB_FLOOR,
)
from churn import NeighborhoodModelV2
from distance_model import compute_ocean_adjacency


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def detect_regime_from_overview(obs_counts, obs_total, initial_grid, h, w):
    """Detect round regime from one seed's overview observations.

    Returns dict with:
      survival_rate: fraction of initial settlements that survived
      growth_rate: new settlements per initial settlement
      regime: 'death' / 'quiet' / 'growth'
    """
    init_settlements = 0
    survived = 0
    new_settlements = 0
    forest_consumed = 0
    init_forests = 0

    for y in range(h):
        for x in range(w):
            if obs_total[y, x] == 0:
                continue
            cls = TERRAIN_TO_CLASS.get(int(initial_grid[y][x]), 0)
            n = obs_total[y, x]

            if cls in (1, 2):  # initial settlement/port
                init_settlements += 1
                sp_frac = (obs_counts[y, x, 1] + obs_counts[y, x, 2]) / n
                if sp_frac > 0.2:
                    survived += 1
            elif cls == 4:  # forest
                init_forests += 1
                f_frac = obs_counts[y, x, 4] / n
                if f_frac < 0.5:
                    forest_consumed += 1
            elif cls == 0:  # empty
                sp_frac = (obs_counts[y, x, 1] + obs_counts[y, x, 2]) / n
                if sp_frac > 0.2:
                    new_settlements += 1

    survival_rate = survived / max(1, init_settlements)
    growth_rate = new_settlements / max(1, init_settlements)
    forest_loss = forest_consumed / max(1, init_forests)

    if survival_rate < 0.05:
        regime = "death"
    elif growth_rate > 1.0 or forest_loss > 0.05:
        regime = "growth"
    else:
        regime = "quiet"

    return {
        "survival_rate": survival_rate,
        "growth_rate": growth_rate,
        "forest_loss": forest_loss,
        "regime": regime,
        "init_settlements": init_settlements,
        "survived": survived,
        "new_settlements": new_settlements,
    }


def calibrate_predictions(pred, initial_grid, regime_info, h, w):
    """Adjust predictions to match the detected regime.

    The key calibration: if we detected X% settlement survival from observations,
    scale the model's settlement predictions to match.
    """
    detected_survival = regime_info["survival_rate"]
    regime = regime_info["regime"]

    # Measure what the model currently predicts for settlement survival
    model_survival_sum = 0
    init_sp_count = 0
    for y in range(h):
        for x in range(w):
            cls = TERRAIN_TO_CLASS.get(int(initial_grid[y][x]), 0)
            if cls in (1, 2):
                init_sp_count += 1
                model_survival_sum += pred[y, x, 1] + pred[y, x, 2]

    if init_sp_count == 0:
        return pred

    model_survival = model_survival_sum / init_sp_count

    if model_survival < 0.01:
        return pred  # avoid division by zero

    # Compute calibration factor
    calibration = detected_survival / model_survival
    calibration = np.clip(calibration, 0.1, 5.0)  # safety bounds

    # Apply calibration to settlement/port probabilities
    calibrated = pred.copy()
    for y in range(h):
        for x in range(w):
            if initial_grid[y][x] in STATIC_TERRAIN:
                continue
            cls = TERRAIN_TO_CLASS.get(int(initial_grid[y][x]), 0)

            if cls in (1, 2):
                # Scale settlement and port survival probability
                calibrated[y, x, 1] *= calibration
                calibrated[y, x, 2] *= calibration
                # Counter-scale empty and forest (what they become when dying)
                remaining = 1.0 - calibrated[y, x, 1] - calibrated[y, x, 2]
                old_remaining = 1.0 - pred[y, x, 1] - pred[y, x, 2]
                if old_remaining > 0.01 and remaining > 0:
                    death_scale = remaining / old_remaining
                    calibrated[y, x, 0] = pred[y, x, 0] * death_scale
                    calibrated[y, x, 3] = pred[y, x, 3] * death_scale
                    calibrated[y, x, 4] = pred[y, x, 4] * death_scale

    # Also calibrate new settlement growth on non-settlement cells
    if regime == "growth":
        growth_boost = min(regime_info["growth_rate"] / 0.5, 3.0)
        for y in range(h):
            for x in range(w):
                cls = TERRAIN_TO_CLASS.get(int(initial_grid[y][x]), 0)
                if cls not in (1, 2) and initial_grid[y][x] not in STATIC_TERRAIN:
                    calibrated[y, x, 1] *= growth_boost
                    calibrated[y, x, 2] *= min(growth_boost, 2.0)
    elif regime == "death":
        for y in range(h):
            for x in range(w):
                cls = TERRAIN_TO_CLASS.get(int(initial_grid[y][x]), 0)
                if cls not in (1, 2) and initial_grid[y][x] not in STATIC_TERRAIN:
                    calibrated[y, x, 1] *= 0.1
                    calibrated[y, x, 2] *= 0.1

    # Port constraint: no ports far from ocean
    ocean_adj = compute_ocean_adjacency(initial_grid, h, w)
    for y in range(h):
        for x in range(w):
            if ocean_adj[y, x] == 0:
                calibrated[y, x, 2] = PROB_FLOOR

    # Floor and renormalize
    calibrated = np.maximum(calibrated, PROB_FLOOR)
    calibrated = calibrated / calibrated.sum(axis=-1, keepdims=True)

    return calibrated


def apply_postprocessing(pred, initial_grid, h, w):
    """Temperature + collapse + smoothing."""
    # Temperature
    pred = pred ** (1.0 / 1.12)

    # Collapse
    for y in range(h):
        for x in range(w):
            if initial_grid[y][x] in STATIC_TERRAIN:
                continue
            probs = pred[y, x]
            mask = probs < 0.016
            if mask.any() and not mask.all():
                probs[mask] = 0.0
                probs[:] = np.maximum(probs, PROB_FLOOR)
                pred[y, x] = probs / probs.sum()

    # Smoothing
    smoothed = np.copy(pred)
    for cls in range(NUM_CLASSES):
        smoothed[:, :, cls] = gaussian_filter(pred[:, :, cls], sigma=0.3)
    for y in range(h):
        for x in range(w):
            if initial_grid[y][x] in STATIC_TERRAIN:
                smoothed[y, x] = pred[y, x]
    pred = smoothed

    pred = np.maximum(pred, PROB_FLOOR)
    pred = pred / pred.sum(axis=-1, keepdims=True)
    return pred


def simulate_multi_seed_overview(round_data, seed_idx, rng=None):
    """Simulate 9 overview queries on a seed (for backtesting).
    Samples from ground truth to simulate stochastic observations."""
    if rng is None:
        rng = np.random.default_rng(42)

    gt = np.array(round_data["seeds"][str(seed_idx)]["ground_truth"])
    h, w = round_data["map_height"], round_data["map_width"]

    obs_counts = np.zeros((h, w, NUM_CLASSES))
    obs_total = np.zeros((h, w))

    # Simulate 9 viewport observations (full map coverage)
    for y in range(h):
        for x in range(w):
            probs = gt[y, x]
            probs = np.maximum(probs, 1e-10)
            probs = probs / probs.sum()
            sampled = rng.choice(NUM_CLASSES, p=probs)
            obs_counts[y, x, sampled] += 1
            obs_total[y, x] += 1

    return obs_counts, obs_total


def backtest_calibrated(rounds_data, multi_seed=False, n_trials=10):
    """Backtest calibrated model.

    If multi_seed: simulate 10 queries per seed (overview + 1 extra)
    If not: use real observations (seed 0 only, like current approach)
    """
    log(f"Backtesting calibrated model (multi_seed={multi_seed}, trials={n_trials})...")

    calibrated_scores = []
    v2_scores = []

    for rd in rounds_data:
        rn = rd["round_number"]
        if not rd.get("seeds"):
            continue

        v2 = NeighborhoodModelV2()
        for other_rd in rounds_data:
            if other_rd["round_number"] != rn and other_rd.get("seeds"):
                v2.add_training_data(other_rd)
        v2.finalize()

        real_obs = load_real_observations(rn)
        h, w = rd["map_height"], rd["map_width"]

        # V2 baseline (current approach: real obs on seed 0 only)
        v2_round = []
        for si in range(5):
            si_str = str(si)
            if si_str not in rd["seeds"]:
                continue
            gt = np.array(rd["seeds"][si_str]["ground_truth"])
            ig = rd["initial_states"][si]["grid"]
            obs_c, obs_t = None, None
            if real_obs and si in real_obs:
                obs_c, obs_t = real_obs[si]
            pred = v2.predict_grid_with_obs(rd, si, obs_counts=obs_c, obs_total=obs_t, obs_weight_max=0.70)
            pred = apply_postprocessing(pred, ig, h, w)
            result = score_prediction(gt, pred, initial_grid=ig)
            v2_round.append(result["score"])

        # Calibrated model (multi-seed or single-seed)
        trial_avgs = []
        for trial in range(n_trials):
            rng = np.random.default_rng(seed=trial * 100 + rn)

            # Step 1: Get seed 0 observations (for regime detection)
            if multi_seed:
                obs_c0, obs_t0 = simulate_multi_seed_overview(rd, 0, rng)
            else:
                if real_obs and 0 in real_obs:
                    obs_c0, obs_t0 = real_obs[0]
                else:
                    obs_c0, obs_t0 = simulate_multi_seed_overview(rd, 0, rng)

            # Step 2: Detect regime from seed 0
            ig0 = rd["initial_states"][0]["grid"]
            regime_info = detect_regime_from_overview(obs_c0, obs_t0, ig0, h, w)

            # Step 3: Predict all seeds with calibration
            cal_round = []
            for si in range(5):
                si_str = str(si)
                if si_str not in rd["seeds"]:
                    continue
                gt = np.array(rd["seeds"][si_str]["ground_truth"])
                ig = rd["initial_states"][si]["grid"]

                # Get observations for this seed
                obs_c, obs_t = None, None
                if multi_seed:
                    obs_c, obs_t = simulate_multi_seed_overview(rd, si,
                                    np.random.default_rng(seed=trial * 100 + rn * 10 + si))
                elif real_obs and si in real_obs:
                    obs_c, obs_t = real_obs[si]

                # V2 base prediction with observations
                pred = v2.predict_grid_with_obs(rd, si, obs_counts=obs_c, obs_total=obs_t, obs_weight_max=0.70)

                # Calibrate with regime
                pred = calibrate_predictions(pred, ig, regime_info, h, w)

                # Post-processing
                pred = apply_postprocessing(pred, ig, h, w)

                result = score_prediction(gt, pred, initial_grid=ig)
                cal_round.append(result["score"])

            trial_avgs.append(np.mean(cal_round))

        avg_cal = np.mean(trial_avgs)
        avg_v2 = np.mean(v2_round)
        delta = avg_cal - avg_v2
        sign = "+" if delta >= 0 else ""

        regime_str = regime_info["regime"]
        surv_str = f'{regime_info["survival_rate"]:.0%}'
        log(f"  R{rn}: cal={avg_cal:.1f}  v2={avg_v2:.1f}  delta={sign}{delta:.1f}  "
            f"regime={regime_str} surv={surv_str}")

        calibrated_scores.append(avg_cal)
        v2_scores.append(avg_v2)

    overall_cal = np.mean(calibrated_scores)
    overall_v2 = np.mean(v2_scores)
    delta = overall_cal - overall_v2
    sign = "+" if delta >= 0 else ""
    log(f"\n  OVERALL: cal={overall_cal:.1f}  v2={overall_v2:.1f}  delta={sign}{delta:.1f}")

    return overall_cal, overall_v2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backtest", action="store_true")
    parser.add_argument("--multi-seed", action="store_true",
                        help="Test 10 queries per seed instead of 50 on seed 0")
    parser.add_argument("--trials", type=int, default=10)
    args = parser.parse_args()

    rounds_data = load_cached_rounds()
    if not rounds_data:
        log("No cached data.")
        return

    if args.backtest:
        backtest_calibrated(rounds_data, multi_seed=args.multi_seed, n_trials=args.trials)


if __name__ == "__main__":
    main()
