#!/usr/bin/env python3
"""
Post-processing parameter search for Astar Island predictions.

Tests temperature scaling, spatial smoothing, and collapse thresholding
against cached ground truth using leave-one-out backtesting.

Usage:
  python postprocess_search.py                    # Run all three searches
  python postprocess_search.py --temperature      # Temperature only
  python postprocess_search.py --smoothing        # Gaussian smoothing only
  python postprocess_search.py --collapse         # Collapse thresholding only
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    load_cached_rounds, score_prediction, load_real_observations,
    TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, PROB_FLOOR,
)
from churn import NeighborhoodModelV2


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def apply_temperature(pred, temperature):
    """Temperature scaling: sharpen (T<1) or soften (T>1) distributions."""
    if temperature == 1.0:
        return pred
    scaled = pred ** (1.0 / temperature)
    scaled = np.maximum(scaled, PROB_FLOOR)
    return scaled / scaled.sum(axis=-1, keepdims=True)


def apply_gaussian_smooth(pred, sigma, initial_grid):
    """Spatial Gaussian smoothing on dynamic cells only."""
    if sigma <= 0:
        return pred
    from scipy.ndimage import gaussian_filter
    h, w, c = pred.shape
    smoothed = np.copy(pred)
    for cls in range(c):
        smoothed[:, :, cls] = gaussian_filter(pred[:, :, cls], sigma=sigma)
    # Restore static cells to original predictions
    for y in range(h):
        for x in range(w):
            terrain = initial_grid[y][x]
            if terrain in STATIC_TERRAIN:
                smoothed[y, x] = pred[y, x]
    smoothed = np.maximum(smoothed, PROB_FLOOR)
    return smoothed / smoothed.sum(axis=-1, keepdims=True)


def apply_collapse(pred, threshold, initial_grid):
    """Zero out probabilities below threshold on dynamic cells, redistribute."""
    if threshold <= 0:
        return pred
    h, w, c = pred.shape
    collapsed = np.copy(pred)
    for y in range(h):
        for x in range(w):
            terrain = initial_grid[y][x]
            if terrain in STATIC_TERRAIN:
                continue
            probs = collapsed[y, x]
            mask = probs < threshold
            if mask.any() and not mask.all():
                probs[mask] = 0.0
                probs = np.maximum(probs, PROB_FLOOR)
                collapsed[y, x] = probs / probs.sum()
    return collapsed


def get_predictions(rounds_data, with_obs=True):
    """Generate leave-one-out predictions for all rounds. Returns dict[round_num] -> list of (pred, gt, ig) per seed."""
    results = {}
    for rd in rounds_data:
        rn = rd["round_number"]
        if not rd.get("seeds"):
            continue
        model = NeighborhoodModelV2()
        for other_rd in rounds_data:
            if other_rd["round_number"] != rn:
                model.add_training_data(other_rd)
        model.finalize()

        obs_data = load_real_observations(rn) if with_obs else {}

        seeds = []
        for si_str, seed_data in rd["seeds"].items():
            si = int(si_str)
            gt = np.array(seed_data["ground_truth"])
            ig = rd["initial_states"][si]["grid"]
            obs_c, obs_t = None, None
            if obs_data and si in obs_data:
                obs_c, obs_t = obs_data[si]
            pred = model.predict_grid_with_obs(
                rd, si, obs_counts=obs_c, obs_total=obs_t, obs_weight_max=0.70)
            seeds.append((pred, gt, ig))
        results[rn] = seeds
    return results


def score_with_postprocess(predictions, apply_fn):
    """Score predictions after applying a post-processing function."""
    all_scores = []
    for rn, seeds in sorted(predictions.items()):
        round_scores = []
        for pred, gt, ig in seeds:
            processed = apply_fn(pred.copy(), ig)
            result = score_prediction(gt, processed, initial_grid=ig)
            round_scores.append(result["score"])
        all_scores.append(np.mean(round_scores))
    return np.mean(all_scores), all_scores


def search_temperature(predictions):
    """Search over temperature values."""
    log("=== Temperature Scaling Search ===")
    temps = [0.9, 1.0, 1.05, 1.08, 1.1, 1.12, 1.15, 1.2]
    best_t, best_score = 1.0, -1

    for t in temps:
        avg, per_round = score_with_postprocess(
            predictions,
            lambda pred, ig: apply_temperature(pred, t))
        rounds_str = " ".join(f"{s:.1f}" for s in per_round)
        marker = " <-- current" if t == 1.12 else ""
        log(f"  T={t:.2f}: avg={avg:.1f}  [{rounds_str}]{marker}")
        if avg > best_score:
            best_score = avg
            best_t = t

    log(f"  Best: T={best_t:.2f}, avg={best_score:.1f}")
    return best_t, best_score


def search_smoothing(predictions, temperature=1.12):
    """Search over Gaussian sigma values (applied after temperature)."""
    log("=== Spatial Smoothing Search (after T=1.12) ===")
    sigmas = [0.0, 0.3, 0.5, 0.7, 1.0, 1.5]
    best_s, best_score = 0.0, -1

    for sigma in sigmas:
        avg, per_round = score_with_postprocess(
            predictions,
            lambda pred, ig, s=sigma: apply_gaussian_smooth(
                apply_temperature(pred, temperature), s, ig))
        rounds_str = " ".join(f"{s:.1f}" for s in per_round)
        log(f"  sigma={sigma:.1f}: avg={avg:.1f}  [{rounds_str}]")
        if avg > best_score:
            best_score = avg
            best_s = sigma

    log(f"  Best: sigma={best_s:.1f}, avg={best_score:.1f}")
    return best_s, best_score


def search_collapse(predictions, temperature=1.12):
    """Search over collapse threshold values (applied after temperature)."""
    log("=== Collapse Thresholding Search (after T=1.12) ===")
    thresholds = [0.0, 0.010, 0.016, 0.020, 0.025, 0.030, 0.040]
    best_c, best_score = 0.0, -1

    for thresh in thresholds:
        avg, per_round = score_with_postprocess(
            predictions,
            lambda pred, ig, t=thresh: apply_collapse(
                apply_temperature(pred, temperature), t, ig))
        rounds_str = " ".join(f"{s:.1f}" for s in per_round)
        log(f"  threshold={thresh:.3f}: avg={avg:.1f}  [{rounds_str}]")
        if avg > best_score:
            best_score = avg
            best_c = thresh

    log(f"  Best: threshold={best_c:.3f}, avg={best_score:.1f}")
    return best_c, best_score


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--temperature", action="store_true")
    parser.add_argument("--smoothing", action="store_true")
    parser.add_argument("--collapse", action="store_true")
    parser.add_argument("--with-obs", action="store_true", default=True)
    args = parser.parse_args()

    run_all = not (args.temperature or args.smoothing or args.collapse)

    rounds_data = load_cached_rounds()
    if not rounds_data:
        log("No cached data. Run backtest.py --cache first.")
        return

    log(f"Loaded {len(rounds_data)} rounds")
    log("Building leave-one-out predictions (V2 model)...")
    predictions = get_predictions(rounds_data, with_obs=args.with_obs)
    log(f"Predictions ready for {len(predictions)} rounds")

    results = {}
    if run_all or args.temperature:
        best_t, score_t = search_temperature(predictions)
        results["temperature"] = {"value": best_t, "score": score_t}

    if run_all or args.smoothing:
        t = results.get("temperature", {}).get("value", 1.12)
        best_s, score_s = search_smoothing(predictions, temperature=t)
        results["smoothing"] = {"value": best_s, "score": score_s}

    if run_all or args.collapse:
        t = results.get("temperature", {}).get("value", 1.12)
        best_c, score_c = search_collapse(predictions, temperature=t)
        results["collapse"] = {"value": best_c, "score": score_c}

    log("\n=== SUMMARY ===")
    for name, r in results.items():
        log(f"  {name}: best={r['value']}, avg_score={r['score']:.1f}")


if __name__ == "__main__":
    main()
