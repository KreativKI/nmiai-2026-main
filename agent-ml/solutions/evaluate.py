#!/usr/bin/env python3
"""
Evaluation Framework for Astar Island models.

Leave-one-round-out cross-validation with official scoring formula.
Tests any model that implements a predict(round_data, seed_idx, regime) interface.

Usage:
  python evaluate.py                    # Evaluate current baseline
  python evaluate.py --model model_a    # Evaluate Model A
"""

import argparse
import json
from pathlib import Path

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    load_cached_rounds, score_prediction,
    TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, PROB_FLOOR,
)
from regime_model import classify_round


def evaluate_leave_one_out(model_class, rounds_data=None, verbose=True):
    """Run leave-one-round-out CV on a model.

    Args:
        model_class: callable that returns a model instance. Must implement:
            - train(rounds_data, exclude_round) -> trains on all rounds except one
            - predict(round_data, seed_idx, regime) -> returns (H, W, 6) prediction
        rounds_data: list of round dicts (from load_cached_rounds)
        verbose: print per-round results

    Returns:
        dict with per-round scores, per-regime averages, and overall average
    """
    if rounds_data is None:
        rounds_data = load_cached_rounds()

    results = {"per_round": {}, "per_regime": {}, "overall": {}}
    all_scores = []
    regime_scores = {"death": [], "stable": [], "growth": []}

    for held_out in rounds_data:
        rn = held_out["round_number"]
        if not held_out.get("seeds"):
            continue

        regime, _ = classify_round(held_out)
        h, w = held_out["map_height"], held_out["map_width"]

        model = model_class()
        model.train(rounds_data, exclude_round=rn)

        round_scores = []
        for si_str, sd in held_out["seeds"].items():
            si = int(si_str)
            gt = np.array(sd["ground_truth"])
            ig = held_out["initial_states"][si]["grid"]

            pred = model.predict(held_out, si, regime)
            pred = np.maximum(pred, PROB_FLOOR)
            pred /= pred.sum(axis=-1, keepdims=True)

            result = score_prediction(gt, pred, initial_grid=ig)
            round_scores.append(result["score"])

        avg = np.mean(round_scores)
        all_scores.append(avg)
        regime_scores[regime].append(avg)

        results["per_round"][rn] = {
            "regime": regime,
            "score": round(float(avg), 2),
            "seeds": [round(float(s), 2) for s in round_scores],
        }

        if verbose:
            print(f"  R{rn:>2} [{regime:>6}]: {avg:.1f}  seeds={[round(s,1) for s in round_scores]}")

    results["overall"]["mean"] = round(float(np.mean(all_scores)), 2) if all_scores else 0
    results["overall"]["std"] = round(float(np.std(all_scores)), 2) if all_scores else 0
    results["overall"]["n_rounds"] = len(all_scores)

    for regime in ("death", "stable", "growth"):
        scores = regime_scores[regime]
        if scores:
            results["per_regime"][regime] = {
                "mean": round(float(np.mean(scores)), 2),
                "std": round(float(np.std(scores)), 2),
                "n_rounds": len(scores),
            }

    if verbose:
        print(f"\n  Overall: {results['overall']['mean']:.1f} +/- {results['overall']['std']:.1f}")
        for regime in ("death", "stable", "growth"):
            if regime in results["per_regime"]:
                r = results["per_regime"][regime]
                print(f"  {regime}: {r['mean']:.1f} +/- {r['std']:.1f} ({r['n_rounds']} rounds)")

    return results


class BaselineLGBM:
    """Current baseline: 6 independent LightGBM regressors on 51 features."""

    def __init__(self):
        self.models = None

    def train(self, rounds_data, exclude_round=None):
        import lightgbm as lgb
        from build_dataset import build_master_dataset, FEATURE_NAMES

        X, Y, _ = build_master_dataset(rounds_data, exclude_round=exclude_round)

        self.models = {}
        for cls in range(NUM_CLASSES):
            m = lgb.LGBMRegressor(
                n_estimators=50, num_leaves=31, learning_rate=0.05,
                min_child_samples=20, subsample=0.8, colsample_bytree=0.8,
                verbose=-1,
            )
            m.fit(X, Y[:, cls])
            self.models[cls] = m

    def predict(self, round_data, seed_idx, regime):
        from build_dataset import (
            extract_cell_features, FEATURE_NAMES, _compute_trajectory_features,
            REPLAY_DIR,
        )

        h, w = round_data["map_height"], round_data["map_width"]
        ig = round_data["initial_states"][seed_idx]["grid"]
        rn = round_data["round_number"]
        pred = np.zeros((h, w, NUM_CLASSES))

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

        if cells:
            Xp = np.array(cells, dtype=np.float32)
            coord_arr = np.array(coords)
            for cls in range(NUM_CLASSES):
                preds = self.models[cls].predict(Xp)
                pred[coord_arr[:, 0], coord_arr[:, 1], cls] = preds

        static_mask = np.isin(grid_classes, list(STATIC_TERRAIN))
        for y, x in zip(*np.where(static_mask)):
            pred[y, x] = PROB_FLOOR
            pred[y, x, grid_classes[y, x]] = 1.0 - (NUM_CLASSES - 1) * PROB_FLOOR

        return pred


def main():
    parser = argparse.ArgumentParser(description="Evaluate models with leave-one-round-out CV")
    parser.add_argument("--model", default="baseline", choices=["baseline"])
    args = parser.parse_args()

    print("Loading cached rounds...")
    rounds_data = load_cached_rounds()
    print(f"  {len(rounds_data)} rounds loaded")

    models = {"baseline": BaselineLGBM}
    model_class = models[args.model]

    print(f"\n=== EVALUATING: {args.model} ===")
    results = evaluate_leave_one_out(model_class, rounds_data)

    out_path = Path(__file__).parent / "data" / f"eval_{args.model}.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
