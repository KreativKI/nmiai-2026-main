#!/usr/bin/env python3
"""
Model A: Multiclass LightGBM on 51 features.

Key change from baseline: single LGBMClassifier with multiclass objective
instead of 6 independent regressors. Forces valid probability distributions
via softmax output.

Usage:
  python model_a_lgbm.py                 # Evaluate with leave-one-round-out CV
  python model_a_lgbm.py --save-model    # Save trained model to disk
"""

import argparse
import json
from pathlib import Path

import numpy as np
import lightgbm as lgb

import sys
sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    load_cached_rounds, TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, PROB_FLOOR,
)
from build_dataset import (
    build_master_dataset, extract_cell_features, FEATURE_NAMES,
    _compute_trajectory_features, REPLAY_DIR,
)
from evaluate import evaluate_leave_one_out


class ModelAMulticlass:
    """Multiclass LightGBM: single model, softmax output, 51 features."""

    def __init__(self):
        self.model = None

    def train(self, rounds_data, exclude_round=None):
        X, Y, _ = build_master_dataset(rounds_data, exclude_round=exclude_round)

        # 6 independent regressors on probability targets (NOT multiclass).
        # Multiclass argmax scored 26.3 vs regression's 78.0 because it
        # throws away probability distribution information the scoring rewards.
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
                pred[coord_arr[:, 0], coord_arr[:, 1], cls] = self.models[cls].predict(Xp)

        static_mask = np.isin(grid_classes, list(STATIC_TERRAIN))
        for y, x in zip(*np.where(static_mask)):
            pred[y, x] = PROB_FLOOR
            pred[y, x, grid_classes[y, x]] = 1.0 - (NUM_CLASSES - 1) * PROB_FLOOR

        return pred


def main():
    parser = argparse.ArgumentParser(description="Model A: Multiclass LightGBM")
    parser.add_argument("--save-model", action="store_true")
    args = parser.parse_args()

    print("Loading cached rounds...")
    rounds_data = load_cached_rounds()
    print(f"  {len(rounds_data)} rounds loaded")

    print("\n=== Model A: Multiclass LightGBM (51 features) ===")
    results = evaluate_leave_one_out(ModelAMulticlass, rounds_data)

    out_path = Path(__file__).parent / "data" / "eval_model_a.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to {out_path}")

    if args.save_model:
        print("\nTraining final model on all data...")
        model = ModelAMulticlass()
        model.train(rounds_data)
        for cls, m in model.models.items():
            model_path = Path(__file__).parent / "data" / f"model_a_cls{cls}.txt"
            m.booster_.save_model(str(model_path))
        print(f"  Saved {NUM_CLASSES} models")


if __name__ == "__main__":
    main()
