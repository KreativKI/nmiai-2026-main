#!/usr/bin/env python3
"""
Equilibrium Prediction Model for Astar Island.

Instead of applying learned transitions once (initial -> predicted),
iterates the transition dynamics until convergence to approximate the
simulation's steady state.

The key insight: the ground truth is computed from HUNDREDS of simulation
runs, so it represents the equilibrium distribution. Our learned
transitions approximate the dynamics. Iterating them should converge
to a better approximation of the equilibrium.

Usage:
  python equilibrium.py --backtest               # Compare vs single-step
  python equilibrium.py --backtest --steps 5     # Test specific iteration count
  python equilibrium.py --search                 # Grid search over steps + damping
"""

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    load_cached_rounds, score_prediction, load_real_observations,
    TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, CLASS_NAMES, PROB_FLOOR,
)
from learned_model import NeighborhoodModel
from churn import NeighborhoodModelV2

DATA_DIR = Path(__file__).parent / "data"


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def iterate_predictions(model, round_data, seed_idx, n_steps=3, damping=0.5,
                         obs_counts=None, obs_total=None, obs_weight_max=0.70):
    """Iterate transition dynamics toward equilibrium.

    Instead of: initial -> apply_transitions_once -> prediction
    Does: initial -> step1 -> step2 -> ... -> stepN -> prediction

    Each step applies the learned transitions to the CURRENT state
    (not the initial state), then damps toward the previous prediction
    to prevent oscillation.

    Args:
        n_steps: number of iteration steps (1 = current behavior)
        damping: blend factor with previous step (0 = no damping, 1 = no change)
    """
    h, w = round_data["map_height"], round_data["map_width"]
    grid = round_data["initial_states"][seed_idx]["grid"]

    # Step 0: initial prediction from learned model
    pred = model.predict_grid(round_data, seed_idx)

    # Iterate: apply transitions to current predicted state
    for step in range(1, n_steps):
        new_pred = np.zeros_like(pred)

        for y in range(h):
            for x in range(w):
                terrain = grid[y][x]
                if terrain in STATIC_TERRAIN:
                    new_pred[y, x] = pred[y, x]
                    continue

                # Build "virtual grid" from current predictions for neighborhood
                # Use argmax of current pred as the "most likely terrain"
                # Then look up transition for that neighborhood config
                virtual_grid = _build_virtual_grid(pred, grid, h, w)
                new_pred[y, x] = model.predict_cell(virtual_grid, y, x, h, w)

        # Damp: blend new prediction with previous to prevent oscillation
        pred = damping * pred + (1 - damping) * new_pred

        # Renormalize
        pred = np.maximum(pred, PROB_FLOOR)
        pred = pred / pred.sum(axis=-1, keepdims=True)

    # Blend with observations
    if obs_counts is not None and obs_total is not None:
        has_obs = obs_total > 0
        if has_obs.any():
            ot_3d = obs_total[..., np.newaxis]
            empirical = obs_counts / np.maximum(ot_3d, 1)

            obs_w = np.zeros((h, w, 1))
            for y in range(h):
                for x in range(w):
                    if obs_total[y, x] == 0:
                        continue
                    n = obs_total[y, x]
                    cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)
                    if cls in (1, 2, 3):
                        obs_w[y, x, 0] = min(obs_weight_max, 0.4 + n / 12.0)
                    elif cls == 4:
                        obs_w[y, x, 0] = min(0.4, 0.1 + n / 20.0)
                    else:
                        obs_w[y, x, 0] = min(0.35, 0.1 + n / 25.0)

            pred = np.where(
                has_obs[..., np.newaxis],
                obs_w * empirical + (1 - obs_w) * pred,
                pred
            )

    pred = np.maximum(pred, PROB_FLOOR)
    pred = pred / pred.sum(axis=-1, keepdims=True)
    return pred


def _build_virtual_grid(pred, initial_grid, h, w):
    """Build a virtual grid from predictions for neighborhood lookups.

    Uses a probabilistic approach: for each cell, create a "virtual terrain"
    that reflects the predicted distribution. For the neighborhood model,
    we use the argmax (most likely terrain) as the virtual terrain value.
    """
    virtual = []
    for y in range(h):
        row = []
        for x in range(w):
            terrain = initial_grid[y][x]
            if terrain in STATIC_TERRAIN:
                row.append(terrain)
            else:
                # Use argmax of prediction as virtual terrain
                row.append(int(pred[y, x].argmax()))
        virtual.append(row)
    return virtual


def backtest_equilibrium(rounds_data, ModelClass=NeighborhoodModelV2,
                          n_steps=3, damping=0.5, temperature=1.12):
    """Compare equilibrium model vs single-step model."""
    single_scores = []
    eq_scores = []

    for rd in rounds_data:
        rn = rd["round_number"]
        if not rd.get("seeds"):
            continue

        model = ModelClass()
        for other_rd in rounds_data:
            if other_rd["round_number"] != rn:
                model.add_training_data(other_rd)
        model.finalize()

        obs_data = load_real_observations(rn)

        for si_str, seed_data in rd["seeds"].items():
            si = int(si_str)
            gt = np.array(seed_data["ground_truth"])
            ig = rd["initial_states"][si]["grid"]

            obs_c, obs_t = None, None
            if obs_data and si in obs_data:
                obs_c, obs_t = obs_data[si]

            # Single-step prediction
            pred_single = model.predict_grid_with_obs(
                rd, si, obs_counts=obs_c, obs_total=obs_t, obs_weight_max=0.70)
            if temperature != 1.0:
                pred_single = pred_single ** (1.0 / temperature)
                pred_single = np.maximum(pred_single, PROB_FLOOR)
                pred_single = pred_single / pred_single.sum(axis=-1, keepdims=True)
            score_s = score_prediction(gt, pred_single, initial_grid=ig)

            # Equilibrium prediction
            pred_eq = iterate_predictions(
                model, rd, si, n_steps=n_steps, damping=damping,
                obs_counts=obs_c, obs_total=obs_t, obs_weight_max=0.70)
            if temperature != 1.0:
                pred_eq = pred_eq ** (1.0 / temperature)
                pred_eq = np.maximum(pred_eq, PROB_FLOOR)
                pred_eq = pred_eq / pred_eq.sum(axis=-1, keepdims=True)
            score_e = score_prediction(gt, pred_eq, initial_grid=ig)

            single_scores.append(score_s["score"])
            eq_scores.append(score_e["score"])

    # Group by round (5 seeds each)
    n_seeds = 5
    for i in range(0, len(single_scores), n_seeds):
        rn = i // n_seeds + 1
        s_avg = np.mean(single_scores[i:i+n_seeds])
        e_avg = np.mean(eq_scores[i:i+n_seeds])
        delta = e_avg - s_avg
        sign = "+" if delta >= 0 else ""
        log(f"  R{rn}: single={s_avg:.1f}  eq={e_avg:.1f}  delta={sign}{delta:.1f}")

    s_total = np.mean(single_scores)
    e_total = np.mean(eq_scores)
    delta = e_total - s_total
    sign = "+" if delta >= 0 else ""
    log(f"\n  OVERALL: single={s_total:.1f}  eq={e_total:.1f}  delta={sign}{delta:.1f}")
    return s_total, e_total


def grid_search_equilibrium(rounds_data):
    """Search over steps and damping parameters."""
    log("Grid searching equilibrium parameters...")

    best_score = -1
    best_params = None

    for n_steps in [2, 3, 4, 5, 8]:
        for damping in [0.3, 0.5, 0.7, 0.8, 0.9]:
            scores = []
            for rd in rounds_data:
                rn = rd["round_number"]
                if not rd.get("seeds"):
                    continue
                model = NeighborhoodModelV2()
                for other_rd in rounds_data:
                    if other_rd["round_number"] != rn:
                        model.add_training_data(other_rd)
                model.finalize()
                obs_data = load_real_observations(rn)
                for si_str, seed_data in rd["seeds"].items():
                    si = int(si_str)
                    gt = np.array(seed_data["ground_truth"])
                    ig = rd["initial_states"][si]["grid"]
                    obs_c, obs_t = None, None
                    if obs_data and si in obs_data:
                        obs_c, obs_t = obs_data[si]
                    pred = iterate_predictions(
                        model, rd, si, n_steps=n_steps, damping=damping,
                        obs_counts=obs_c, obs_total=obs_t)
                    pred = pred ** (1.0 / 1.12)
                    pred = np.maximum(pred, PROB_FLOOR)
                    pred = pred / pred.sum(axis=-1, keepdims=True)
                    result = score_prediction(gt, pred, initial_grid=ig)
                    scores.append(result["score"])

            avg = np.mean(scores)
            if avg > best_score:
                best_score = avg
                best_params = (n_steps, damping)
            log(f"  steps={n_steps}, damping={damping}: avg={avg:.1f}")

    log(f"\n  Best: steps={best_params[0]}, damping={best_params[1]}, score={best_score:.1f}")
    return best_params, best_score


def main():
    parser = argparse.ArgumentParser(description="Equilibrium Prediction Model")
    parser.add_argument("--backtest", action="store_true")
    parser.add_argument("--search", action="store_true")
    parser.add_argument("--steps", type=int, default=3)
    parser.add_argument("--damping", type=float, default=0.5)
    args = parser.parse_args()

    rounds_data = load_cached_rounds()
    if not rounds_data:
        log("No cached data.")
        return

    if args.search:
        grid_search_equilibrium(rounds_data)
    elif args.backtest:
        log(f"Backtesting equilibrium (steps={args.steps}, damping={args.damping})...")
        backtest_equilibrium(rounds_data, n_steps=args.steps, damping=args.damping)
    else:
        log("Use --backtest or --search")


if __name__ == "__main__":
    main()
