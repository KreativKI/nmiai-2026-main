#!/usr/bin/env python3
"""
Query Strategy Simulator for Astar Island.

Tests different allocations of 50 observation queries across 5 seeds.
Uses ground truth from completed rounds to simulate what Chef would see
with each strategy, then scores the resulting predictions.

Key question: overview all 5 seeds (thin) vs deep-stack 2 seeds (thick)?

Usage:
  python query_sim.py                    # Compare strategies
  python query_sim.py --round 9          # Test on specific round
"""

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
from scipy.ndimage import gaussian_filter

import sys
sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    load_cached_rounds, score_prediction,
    TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, PROB_FLOOR, CLASS_NAMES,
)
from churn import NeighborhoodModelV2

DATA_DIR = Path(__file__).parent / "data"


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def simulate_observations(gt_grid, n_samples, h, w, rng):
    """Simulate n_samples observations of the ground truth.

    Each observation = one Monte Carlo sample from the probability distribution.
    Returns obs_counts (h, w, 6) and obs_total (h, w).
    """
    obs_counts = np.zeros((h, w, NUM_CLASSES))
    obs_total = np.zeros((h, w))

    for _ in range(n_samples):
        for y in range(h):
            for x in range(w):
                # Sample from ground truth distribution
                probs = gt_grid[y, x]
                probs = np.maximum(probs, 0)
                if probs.sum() > 0:
                    probs = probs / probs.sum()
                    cls = rng.choice(NUM_CLASSES, p=probs)
                else:
                    cls = 0
                obs_counts[y, x, cls] += 1
                obs_total[y, x] += 1

    return obs_counts, obs_total


def score_strategy(strategy_name, seed_queries, round_data, model, n_trials=5):
    """Score a query allocation strategy using Monte Carlo simulation.

    seed_queries: dict mapping seed_index -> number of full-map samples (queries/9)
    Each full-map sample = 9 viewports = 9 queries.
    Remaining queries become extra samples on seed 0.
    """
    h, w = round_data["map_height"], round_data["map_width"]
    rng = np.random.default_rng(42)

    trial_scores = []
    for trial in range(n_trials):
        seed_scores = []

        for si_str, seed_data in round_data["seeds"].items():
            si = int(si_str)
            gt = np.array(seed_data["ground_truth"])
            ig = round_data["initial_states"][si]["grid"]

            n_samples = seed_queries.get(si, 0)

            if n_samples > 0:
                # Simulate observations
                obs_counts, obs_total = simulate_observations(gt, n_samples, h, w, rng)

                # Predict with model + observations
                pred = model.predict_grid_with_obs(
                    round_data, si,
                    obs_counts=obs_counts,
                    obs_total=obs_total,
                    prior_strength=12.0,
                )
            else:
                # Model-only prediction
                pred = model.predict_grid(round_data, si)

            # Post-process
            pred = pred ** (1.0 / 1.12)
            for y in range(h):
                for x in range(w):
                    if ig[y][x] in STATIC_TERRAIN:
                        continue
                    probs = pred[y, x]
                    mask = probs < 0.016
                    if mask.any() and not mask.all():
                        probs[mask] = 0.0
                        probs[:] = np.maximum(probs, PROB_FLOOR)
                        pred[y, x] = probs / probs.sum()

            smoothed = np.copy(pred)
            for cls in range(NUM_CLASSES):
                smoothed[:, :, cls] = gaussian_filter(pred[:, :, cls], sigma=0.3)
            for y in range(h):
                for x in range(w):
                    if ig[y][x] in STATIC_TERRAIN:
                        smoothed[y, x] = pred[y, x]
            pred = smoothed

            pred = np.maximum(pred, PROB_FLOOR)
            pred = pred / pred.sum(axis=-1, keepdims=True)

            result = score_prediction(gt, pred, initial_grid=ig)
            seed_scores.append(result["score"])

        trial_scores.append(np.mean(seed_scores))

    return np.mean(trial_scores), np.std(trial_scores)


# Each strategy maps seed_index -> number of full-map observations
# 50 queries / 9 per full map = 5.5 full maps + remainder
# We approximate: 1 full map = 9 queries (covers 40x40 grid with 15x15 viewports)
STRATEGIES = {
    "current_v7": {
        # 5 regime + 4 fill seed0 + 36 seeds1-4 + 5 stack = 50
        # Effectively: 1 sample all 5 seeds + partial second on seed 0
        "desc": "1 sample all 5 seeds + 5 stack on seed 0",
        "queries": {0: 2, 1: 1, 2: 1, 3: 1, 4: 1},  # ~50 queries (5*9 + 5)
    },
    "deep_2_seeds": {
        # 3 samples on seeds 0-1, skip seeds 2-4
        "desc": "3 samples on seeds 0-1, model-only on 2-4",
        "queries": {0: 3, 1: 3, 2: 0, 3: 0, 4: 0},  # ~54 queries, close enough
    },
    "deep_1_seed": {
        # 5 samples on seed 0 only
        "desc": "5 samples on seed 0, model-only on 1-4",
        "queries": {0: 5, 1: 0, 2: 0, 3: 0, 4: 0},  # ~45 queries
    },
    "balanced_3": {
        # 2 samples on seeds 0-1, 1 sample on seed 2, model on 3-4
        "desc": "2 samples on seeds 0-1, 1 on seed 2, model on 3-4",
        "queries": {0: 2, 1: 2, 2: 1, 3: 0, 4: 0},  # ~45 queries
    },
    "all_double": {
        # 1 sample each on all 5, plus 1 extra on seed 0
        "desc": "1 sample all 5 + 1 extra on seed 0 (like v7 but more stack)",
        "queries": {0: 1, 1: 1, 2: 1, 3: 1, 4: 1},  # 45 queries, 5 remaining unused
    },
    "heavy_stack": {
        # 4 samples on seed 0, 1 on seed 1
        "desc": "4 samples seed 0, 1 sample seed 1, model on 2-4",
        "queries": {0: 4, 1: 1, 2: 0, 3: 0, 4: 0},  # ~45 queries
    },
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--round", type=int, help="Test specific round only")
    parser.add_argument("--trials", type=int, default=5, help="MC trials per strategy")
    args = parser.parse_args()

    rounds_data = load_cached_rounds()
    log(f"Loaded {len(rounds_data)} rounds")

    results = {}

    test_rounds = rounds_data
    if args.round:
        test_rounds = [rd for rd in rounds_data if rd["round_number"] == args.round]

    for rd in test_rounds:
        rn = rd["round_number"]
        if not rd.get("seeds"):
            continue

        # Train model on OTHER rounds (leave-one-out)
        model = NeighborhoodModelV2()
        for other in rounds_data:
            if other["round_number"] != rn:
                model.add_training_data(other)
        model.finalize()

        log(f"\nR{rn}:")
        round_results = {}

        for name, strategy in STRATEGIES.items():
            avg, std = score_strategy(name, strategy["queries"], rd, model, n_trials=args.trials)
            round_results[name] = {"score": round(float(avg), 2), "std": round(float(std), 2)}
            log(f"  {name:>15}: {avg:.1f} +/- {std:.1f}  ({strategy['desc']})")

        results[str(rn)] = round_results

    # Summary
    log(f"\n{'='*60}")
    log(f"AVERAGE ACROSS ALL ROUNDS:")
    for name in STRATEGIES:
        scores = [results[rn][name]["score"] for rn in results]
        avg = np.mean(scores)
        log(f"  {name:>15}: {avg:.1f}  ({STRATEGIES[name]['desc']})")

    # Save
    output = {
        "per_round": results,
        "summary": {},
    }
    for name in STRATEGIES:
        scores = [results[rn][name]["score"] for rn in results]
        output["summary"][name] = {
            "avg_score": round(float(np.mean(scores)), 2),
            "desc": STRATEGIES[name]["desc"],
            "queries": STRATEGIES[name]["queries"],
        }

    with open(DATA_DIR / "query_sim_results.json", "w") as f:
        json.dump(output, f, indent=2)
    log(f"\nSaved to data/query_sim_results.json")


if __name__ == "__main__":
    main()
