#!/usr/bin/env python3
"""
Hyperparameter Grid Search for Astar Island prediction pipeline.

Searches over: temperature, collapse threshold, smoothing sigma, Dirichlet prior strength.
Uses leave-one-out backtesting on all cached rounds. No API calls needed.

Usage:
  python grid_search.py                # Full grid search
  python grid_search.py --quick        # Reduced grid (faster)

Outputs best params to data/best_params.json
"""

import json
import itertools
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
from scipy.ndimage import gaussian_filter

import sys
sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    load_cached_rounds, score_prediction,
    TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, PROB_FLOOR,
)
from churn import NeighborhoodModelV2

DATA_DIR = Path(__file__).parent / "data"


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def postprocess(pred, grid, h, w, temp, collapse, sigma):
    """Apply post-processing pipeline with given params."""
    # Temperature scaling
    pred = pred ** (1.0 / temp)

    # Collapse thresholding
    for y in range(h):
        for x in range(w):
            if grid[y][x] in STATIC_TERRAIN:
                continue
            probs = pred[y, x]
            mask = probs < collapse
            if mask.any() and not mask.all():
                probs[mask] = 0.0
                probs[:] = np.maximum(probs, PROB_FLOOR)
                pred[y, x] = probs / probs.sum()

    # Spatial smoothing
    if sigma > 0:
        smoothed = np.copy(pred)
        for cls in range(NUM_CLASSES):
            smoothed[:, :, cls] = gaussian_filter(pred[:, :, cls], sigma=sigma)
        for y in range(h):
            for x in range(w):
                if grid[y][x] in STATIC_TERRAIN:
                    smoothed[y, x] = pred[y, x]
        pred = smoothed

    # Floor and renormalize
    pred = np.maximum(pred, PROB_FLOOR)
    pred = pred / pred.sum(axis=-1, keepdims=True)
    return pred


def evaluate_params(rounds_data, temp, collapse, sigma, ps):
    """Leave-one-out backtest with given params."""
    scores = []
    for rd in rounds_data:
        rn = rd["round_number"]
        if not rd.get("seeds"):
            continue

        # Train model excluding this round
        model = NeighborhoodModelV2()
        for other in rounds_data:
            if other["round_number"] != rn:
                model.add_training_data(other)
        model.finalize()

        h, w = rd["map_height"], rd["map_width"]
        round_scores = []

        for si_str, seed_data in rd["seeds"].items():
            si = int(si_str)
            gt = np.array(seed_data["ground_truth"])
            ig = rd["initial_states"][si]["grid"]

            # Predict with Dirichlet prior strength
            pred = model.predict_grid(rd, si)

            # Post-process
            pred = postprocess(pred, ig, h, w, temp, collapse, sigma)

            result = score_prediction(gt, pred, initial_grid=ig)
            round_scores.append(result["score"])

        scores.append(np.mean(round_scores))
    return np.mean(scores), scores


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()

    rounds_data = load_cached_rounds()
    log(f"Loaded {len(rounds_data)} rounds for backtesting")

    if args.quick:
        param_grid = {
            "temp": [1.0, 1.1, 1.15, 1.2],
            "collapse": [0.01, 0.015, 0.02],
            "sigma": [0.0, 0.3, 0.5],
            "ps": [8, 12, 16],
        }
    else:
        param_grid = {
            "temp": [0.9, 0.95, 1.0, 1.05, 1.1, 1.12, 1.15, 1.2, 1.3],
            "collapse": [0.005, 0.01, 0.015, 0.016, 0.02, 0.025, 0.03],
            "sigma": [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.7],
            "ps": [4, 8, 10, 12, 15, 20, 30],
        }

    combos = list(itertools.product(
        param_grid["temp"], param_grid["collapse"],
        param_grid["sigma"], param_grid["ps"]
    ))
    log(f"Testing {len(combos)} parameter combinations")

    best_score = -1
    best_params = None
    results = []

    for i, (temp, collapse, sigma, ps) in enumerate(combos):
        avg, per_round = evaluate_params(rounds_data, temp, collapse, sigma, ps)
        results.append({
            "temp": temp, "collapse": collapse, "sigma": sigma, "ps": ps,
            "avg_score": round(float(avg), 2),
            "per_round": [round(float(s), 1) for s in per_round],
        })

        if avg > best_score:
            best_score = avg
            best_params = {"temp": temp, "collapse": collapse, "sigma": sigma, "ps": ps}
            log(f"  [{i+1}/{len(combos)}] NEW BEST: T={temp} col={collapse} sig={sigma} ps={ps} -> {avg:.2f}")
        elif (i + 1) % 50 == 0:
            log(f"  [{i+1}/{len(combos)}] T={temp} col={collapse} sig={sigma} ps={ps} -> {avg:.2f}")

    log(f"\n{'='*60}")
    log(f"BEST PARAMS: {best_params}")
    log(f"BEST SCORE:  {best_score:.2f}")
    log(f"{'='*60}")

    # Show top 10
    results.sort(key=lambda r: -r["avg_score"])
    log("\nTop 10:")
    for r in results[:10]:
        log(f"  T={r['temp']:.2f} col={r['collapse']:.3f} sig={r['sigma']:.1f} ps={r['ps']:>2d} -> {r['avg_score']:.2f}  {r['per_round']}")

    # Save results
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output = {
        "best_params": best_params,
        "best_score": round(float(best_score), 2),
        "current_params": {"temp": 1.12, "collapse": 0.016, "sigma": 0.3, "ps": 12},
        "top_10": results[:10],
        "total_tested": len(combos),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with open(DATA_DIR / "best_params.json", "w") as f:
        json.dump(output, f, indent=2)
    log(f"\nSaved to data/best_params.json")


if __name__ == "__main__":
    main()
