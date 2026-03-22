#!/usr/bin/env python3
"""
Temperature Calibration for Astar Island predictions.

Grid-searches per-regime temperature T to reduce systematic overconfidence.
Uses leave-one-round-out CV to avoid overfitting.

calibrated[y,x] = pred[y,x] ** (1/T)
calibrated /= calibrated.sum()

T > 1 flattens distribution (reduces overconfidence)
T < 1 sharpens distribution (increases confidence)
T = 1 no change

Usage:
  python temperature_calibration.py
"""

import json
from pathlib import Path

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    load_cached_rounds, score_prediction,
    TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, PROB_FLOOR,
)
from build_dataset import (
    build_master_dataset, extract_cell_features, FEATURE_NAMES,
    _compute_trajectory_features, REPLAY_DIR,
)
from regime_model import classify_round
import lightgbm as lgb

DATA_DIR = Path(__file__).parent / "data"


def predict_round(models, round_data, seed_idx, regime):
    """Predict one seed using trained models. Returns (h, w, 6) array."""
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

    for y, x in zip(*np.where(np.isin(grid_classes, list(STATIC_TERRAIN)))):
        pred[y, x] = PROB_FLOOR
        pred[y, x, grid_classes[y, x]] = 1.0 - (NUM_CLASSES - 1) * PROB_FLOOR

    return pred


def apply_temperature(pred, T):
    """Apply temperature scaling to predictions."""
    if T == 1.0:
        return pred.copy()
    cal = np.maximum(pred, 1e-10) ** (1.0 / T)
    cal = np.maximum(cal, PROB_FLOOR)
    cal /= cal.sum(axis=-1, keepdims=True)
    return cal


def main():
    print("Loading data...")
    rounds_data = load_cached_rounds()
    print(f"  {len(rounds_data)} rounds")

    # Classify regimes
    regimes = {}
    for rd in rounds_data:
        regime, _ = classify_round(rd)
        regimes[rd["round_number"]] = regime

    # Leave-one-round-out: for each round, train on others, predict, try T values
    T_values = np.arange(0.5, 3.05, 0.05)
    regime_scores = {regime: {T: [] for T in T_values} for regime in ("death", "stable", "growth")}
    overall_scores = {T: [] for T in T_values}

    for held_out in rounds_data:
        rn = held_out["round_number"]
        if not held_out.get("seeds"):
            continue
        regime = regimes[rn]

        # Train on other rounds
        X, Y, _ = build_master_dataset(rounds_data, exclude_round=rn)
        models = {}
        for cls in range(NUM_CLASSES):
            m = lgb.LGBMRegressor(
                n_estimators=50, num_leaves=31, learning_rate=0.05,
                min_child_samples=20, subsample=0.8, colsample_bytree=0.8,
                verbose=-1,
            )
            m.fit(X, Y[:, cls])
            models[cls] = m

        # Predict all seeds
        for si_str, sd in held_out["seeds"].items():
            si = int(si_str)
            gt = np.array(sd["ground_truth"])
            ig = held_out["initial_states"][si]["grid"]
            pred = predict_round(models, held_out, si, regime)

            # Score at each T value
            for T in T_values:
                cal = apply_temperature(pred, T)
                result = score_prediction(gt, cal, initial_grid=ig)
                regime_scores[regime][T].append(result["score"])
                overall_scores[T].append(result["score"])

        print(f"  R{rn} [{regime}] done")

    # Find best T per regime (LOO-validated)
    print("\n=== TEMPERATURE CALIBRATION RESULTS (LOO-CV) ===")

    best_overall_T, best_overall_score = 1.0, 0
    for T in T_values:
        scores = overall_scores[T]
        avg = np.mean(scores) if scores else 0
        if avg > best_overall_score:
            best_overall_T, best_overall_score = T, avg

    print(f"\nOverall best: T={best_overall_T:.2f}, score={best_overall_score:.1f}")
    baseline_T = min(T_values, key=lambda t: abs(t - 1.0))
    baseline_score = np.mean(overall_scores[baseline_T])
    print(f"Baseline (T=1.0): score={baseline_score:.1f}")
    print(f"Improvement: {best_overall_score - baseline_score:+.1f}")

    results = {"overall": {"T": round(float(best_overall_T), 2),
                           "score": round(float(best_overall_score), 1)},
               "per_regime": {}}

    for regime in ("death", "stable", "growth"):
        best_T, best_score = 1.0, 0
        for T in T_values:
            scores = regime_scores[regime][T]
            if not scores:
                continue
            avg = np.mean(scores)
            if avg > best_score:
                best_T, best_score = T, avg

        baseline_T_r = min(T_values, key=lambda t: abs(t - 1.0))
        baseline = np.mean(regime_scores[regime][baseline_T_r]) if regime_scores[regime][baseline_T_r] else 0
        improvement = best_score - baseline

        print(f"  {regime}: T={best_T:.2f}, score={best_score:.1f} "
              f"(baseline={baseline:.1f}, delta={improvement:+.1f})")

        results["per_regime"][regime] = {
            "T": round(float(best_T), 2),
            "score": round(float(best_score), 1),
            "baseline": round(float(baseline), 1),
            "improvement": round(float(improvement), 1),
            "n_seeds": len(regime_scores[regime][best_T]),
        }

    # Score curve around the optimum
    print(f"\n=== SCORE vs T (overall) ===")
    for T in np.arange(0.7, 2.0, 0.1):
        T_rounded = round(T, 2)
        closest_T = min(T_values, key=lambda t: abs(t - T_rounded))
        avg = np.mean(overall_scores[closest_T])
        bar = "#" * int(max(0, avg - 60))
        print(f"  T={closest_T:.2f}: {avg:.1f} {bar}")

    # Save
    out_path = DATA_DIR / "temperature_calibration.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
