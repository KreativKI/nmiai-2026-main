#!/usr/bin/env python3
"""Brute-force optimal Dirichlet alpha per regime.

For each completed round with saved observations + ground truth:
  1. Regenerate model predictions (LightGBM, 8 sec)
  2. For each alpha candidate: apply Dirichlet blending, score vs ground truth
  3. Find optimal alpha per regime

This optimizes the mechanism that gives us +4.8 points in live vs backtest.
"""

import json
import sys
from pathlib import Path

import numpy as np
import lightgbm as lgb

sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    load_cached_rounds, score_prediction,
    TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, PROB_FLOOR,
)
from build_dataset import (
    build_master_dataset, FEATURE_NAMES, extract_cell_features,
    _compute_trajectory_features,
)
from regime_model import classify_round

DATA_DIR = Path(__file__).parent / "data"
REPLAY_DIR = DATA_DIR / "replays"
OCEAN_RAW = {10, 11}

ALPHA_CANDIDATES = [1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 75, 100]


def get_raw_predictions(rounds_data, held_out_round):
    """Train LightGBM on all rounds except held_out, return raw predictions."""
    X, Y, _ = build_master_dataset(rounds_data, exclude_round=held_out_round)

    params = {
        "n_estimators": 50, "num_leaves": 31, "learning_rate": 0.05,
        "min_child_samples": 20, "subsample": 0.8, "colsample_bytree": 0.8,
        "objective": "regression", "metric": "mse", "verbose": -1,
    }

    models = {}
    for cls in range(NUM_CLASSES):
        m = lgb.LGBMRegressor(**params)
        m.fit(X, Y[:, cls])
        models[cls] = m

    return models


def predict_round_raw(models, round_data, seed_idx, regime):
    """Get raw model predictions (no Dirichlet blending)."""
    h, w = round_data["map_height"], round_data["map_width"]
    ig = round_data["initial_states"][seed_idx]["grid"]
    rn = round_data["round_number"]

    grid_classes = np.array([[TERRAIN_TO_CLASS.get(int(c), 0) for c in row] for row in ig])
    total_s = int((grid_classes == 1).sum())
    total_p = int((grid_classes == 2).sum())

    replay_path = REPLAY_DIR / f"r{rn}_seed{seed_idx}.json"
    replay_data = None
    if replay_path.exists():
        try:
            with open(replay_path) as f:
                replay_data = json.load(f)
        except Exception:
            pass
    traj = _compute_trajectory_features(replay_data, total_s)

    regime_flags = {f"regime_{r}": int(regime == r) for r in ("death", "growth", "stable")}
    round_feats = {"total_settlements": total_s, "total_ports": total_p, **traj, **regime_flags}

    cells, coords = [], []
    for y in range(h):
        for x in range(w):
            if int(ig[y][x]) in STATIC_TERRAIN:
                continue
            fd = extract_cell_features(ig, y, x, h, w, replay_data=replay_data)
            fd.update(round_feats)
            cells.append([fd.get(n, 0) for n in FEATURE_NAMES])
            coords.append((y, x))

    pred = np.zeros((h, w, NUM_CLASSES))
    if cells:
        Xp = np.array(cells, dtype=np.float32)
        coord_arr = np.array(coords)
        for cls in range(NUM_CLASSES):
            pred[coord_arr[:, 0], coord_arr[:, 1], cls] = models[cls].predict(Xp)

    # Static cells
    for y, x in zip(*np.where(np.isin(grid_classes, list(STATIC_TERRAIN)))):
        pred[y, x] = PROB_FLOOR
        pred[y, x, grid_classes[y, x]] = 1.0 - (NUM_CLASSES - 1) * PROB_FLOOR

    return pred


def apply_dirichlet_and_constraints(pred_raw, obs_counts, obs_total, ig, alpha, h, w):
    """Apply Dirichlet blending + hard constraints. Returns final prediction."""
    pred = pred_raw.copy()

    # Dirichlet blending
    for y in range(h):
        for x in range(w):
            if obs_total[y, x] == 0:
                continue
            a = alpha * pred[y, x]
            a = np.maximum(a, PROB_FLOOR)
            pred[y, x] = (a + obs_counts[y, x]) / (a.sum() + obs_total[y, x])

    # Hard constraints
    skip_cells = STATIC_TERRAIN | OCEAN_RAW
    for y in range(h):
        for x in range(w):
            if int(ig[y][x]) in skip_cells:
                continue
            has_ocean = any(
                0 <= y + dy < h and 0 <= x + dx < w
                and int(ig[y + dy][x + dx]) in OCEAN_RAW
                for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                if (dy, dx) != (0, 0)
            )
            if not has_ocean:
                pred[y, x, 2] = PROB_FLOOR
            pred[y, x, 3] = min(pred[y, x, 3], 0.05)

    pred = np.maximum(pred, PROB_FLOOR)
    pred /= pred.sum(axis=-1, keepdims=True)
    return pred


def main():
    rounds_data = load_cached_rounds()
    print(f"Loaded {len(rounds_data)} rounds")

    # Classify regimes
    regimes = {}
    for rd in rounds_data:
        regime, _ = classify_round(rd)
        regimes[rd["round_number"]] = regime

    # Find rounds with saved observations
    obs_rounds = []
    for rd in rounds_data:
        rn = rd["round_number"]
        oc_path = DATA_DIR / f"obs_counts_r{rn}_seed0_full.npy"
        ot_path = DATA_DIR / f"obs_total_r{rn}_seed0_full.npy"
        if oc_path.exists() and ot_path.exists():
            obs_rounds.append(rd)
    print(f"Rounds with saved observations: {[r['round_number'] for r in obs_rounds]}")

    if not obs_rounds:
        print("No rounds with observations found. Using simulated obs from GT.")
        # Simulate observations from ground truth (single sample = argmax)
        obs_rounds = rounds_data

    # For each round with obs, train model, sweep alphas
    regime_alpha_scores = {regime: {a: [] for a in ALPHA_CANDIDATES}
                          for regime in ("death", "stable", "growth")}

    for rd in obs_rounds:
        rn = rd["round_number"]
        regime = regimes[rn]
        h, w = rd["map_height"], rd["map_width"]

        print(f"\nR{rn} [{regime}]: training model (LOO)...")
        models = get_raw_predictions(rounds_data, rn)

        for si_str, sd in rd["seeds"].items():
            si = int(si_str)
            gt = np.array(sd["ground_truth"])
            ig = rd["initial_states"][si]["grid"]

            # Get raw model prediction
            pred_raw = predict_round_raw(models, rd, si, regime)

            # Load saved observations or simulate from GT
            oc_path = DATA_DIR / f"obs_counts_r{rn}_seed{si}_full.npy"
            ot_path = DATA_DIR / f"obs_total_r{rn}_seed{si}_full.npy"

            if oc_path.exists() and ot_path.exists():
                obs_counts = np.load(oc_path)
                obs_total = np.load(ot_path)
            else:
                # Simulate: use GT argmax as single observation
                obs_counts = np.zeros((h, w, NUM_CLASSES))
                obs_total = np.zeros((h, w))
                gt_argmax = gt.argmax(axis=2)
                for y in range(h):
                    for x in range(w):
                        if int(ig[y][x]) not in STATIC_TERRAIN:
                            obs_counts[y, x, gt_argmax[y, x]] = 1
                            obs_total[y, x] = 1

            # Sweep alphas
            for alpha in ALPHA_CANDIDATES:
                pred_final = apply_dirichlet_and_constraints(
                    pred_raw, obs_counts, obs_total, ig, alpha, h, w)
                result = score_prediction(gt, pred_final, initial_grid=ig)
                regime_alpha_scores[regime][alpha].append(result["score"])

        # Print progress
        for alpha in [3, 5, 10, 15, 20, 30]:
            scores = regime_alpha_scores[regime][alpha]
            if scores:
                recent = np.mean(scores[-5:])
                print(f"  alpha={alpha:>3}: latest avg={recent:.1f}")

    # Results
    print("\n" + "=" * 70)
    print("OPTIMAL ALPHA PER REGIME")
    print("=" * 70)

    optimal = {}
    for regime in ("death", "stable", "growth"):
        print(f"\n  {regime.upper()}:")
        best_alpha = None
        best_score = -1
        for alpha in ALPHA_CANDIDATES:
            scores = regime_alpha_scores[regime][alpha]
            if scores:
                avg = np.mean(scores)
                std = np.std(scores)
                n = len(scores)
                marker = ""
                if avg > best_score:
                    best_score = avg
                    best_alpha = alpha
                    marker = " <-- BEST"
                print(f"    alpha={alpha:>3}: {avg:>6.2f} +/- {std:>5.2f} (n={n}){marker}")
        optimal[regime] = {"alpha": best_alpha, "score": round(best_score, 2)}
        print(f"  => OPTIMAL: alpha={best_alpha} (score={best_score:.2f})")

    print("\n" + "=" * 70)
    print("CURRENT vs OPTIMAL")
    print("=" * 70)
    current = {"death": 5, "stable": 30, "growth": 15}
    for regime in ("death", "stable", "growth"):
        cur = current[regime]
        opt = optimal[regime]["alpha"]
        cur_scores = regime_alpha_scores[regime][cur]
        opt_scores = regime_alpha_scores[regime][opt]
        cur_avg = np.mean(cur_scores) if cur_scores else 0
        opt_avg = np.mean(opt_scores) if opt_scores else 0
        delta = opt_avg - cur_avg
        print(f"  {regime:>6}: current alpha={cur:>3} ({cur_avg:.1f}) -> optimal alpha={opt:>3} ({opt_avg:.1f}) delta={delta:+.1f}")

    # Save results
    out = DATA_DIR / "alpha_search_results.json"
    serializable = {}
    for regime in regime_alpha_scores:
        serializable[regime] = {}
        for alpha in regime_alpha_scores[regime]:
            scores = regime_alpha_scores[regime][alpha]
            if scores:
                serializable[regime][str(alpha)] = {
                    "mean": round(float(np.mean(scores)), 2),
                    "std": round(float(np.std(scores)), 2),
                    "n": len(scores),
                }
    serializable["optimal"] = optimal
    serializable["current"] = current
    with open(out, "w") as f:
        json.dump(serializable, f, indent=2)
    print(f"\n  Saved to {out}")


if __name__ == "__main__":
    main()
