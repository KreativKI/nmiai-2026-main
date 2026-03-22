#!/usr/bin/env python3
"""Head-to-head backtest: V5 (LightGBM 51-feat) vs V6 (ensemble 56-feat).

Leave-one-round-out CV on all cached rounds.
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    load_cached_rounds, score_prediction,
    TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, PROB_FLOOR,
)
from regime_model import RegimeModel, classify_round
from evaluate import evaluate_leave_one_out, BaselineLGBM

try:
    from sklearn.neural_network import MLPRegressor
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


class V6Ensemble:
    """V6: LightGBM + MLP + RegimeModel on 56 features."""

    def __init__(self):
        self.lgb_models = None
        self.mlp_models = None
        self.scaler = None
        self.regime_model = None

    def train(self, rounds_data, exclude_round=None):
        import lightgbm as lgb
        from build_dataset_v6 import build_master_dataset

        X, Y, _ = build_master_dataset(rounds_data, exclude_round=exclude_round)

        # LightGBM
        self.lgb_models = {}
        for cls in range(NUM_CLASSES):
            m = lgb.LGBMRegressor(
                n_estimators=50, num_leaves=31, learning_rate=0.05,
                min_child_samples=20, subsample=0.8, colsample_bytree=0.8,
                verbose=-1,
            )
            m.fit(X, Y[:, cls])
            self.lgb_models[cls] = m

        # MLP
        self.mlp_models = {}
        if HAS_SKLEARN:
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)
            for cls in range(NUM_CLASSES):
                m = MLPRegressor(
                    hidden_layer_sizes=(128, 64),
                    max_iter=500,
                    early_stopping=True,
                    validation_fraction=0.1,
                    random_state=42,
                    learning_rate_init=0.001,
                )
                m.fit(X_scaled, Y[:, cls])
                self.mlp_models[cls] = m

        # RegimeModel
        self.regime_model = RegimeModel()
        for rd in rounds_data:
            if rd["round_number"] != exclude_round:
                self.regime_model.add_training_data(rd)
        self.regime_model.finalize()

    def predict(self, round_data, seed_idx, regime):
        from build_dataset_v6 import (
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

            # LightGBM
            lgb_pred = np.zeros((len(cells), NUM_CLASSES))
            for cls in range(NUM_CLASSES):
                lgb_pred[:, cls] = self.lgb_models[cls].predict(Xp)

            # MLP
            mlp_pred = np.zeros((len(cells), NUM_CLASSES))
            if HAS_SKLEARN and self.scaler is not None:
                Xp_scaled = self.scaler.transform(Xp)
                for cls in range(NUM_CLASSES):
                    mlp_pred[:, cls] = self.mlp_models[cls].predict(Xp_scaled)

            # RegimeModel transition
            trans_pred = np.zeros((len(cells), NUM_CLASSES))
            for i, (cy, cx) in enumerate(coords):
                trans_pred[i] = self.regime_model.predict_cell(ig, cy, cx, h, w, regime)

            # Blend
            if HAS_SKLEARN:
                blended = 0.40 * lgb_pred + 0.30 * mlp_pred + 0.30 * trans_pred
            else:
                blended = 0.70 * lgb_pred + 0.30 * trans_pred

            for i, (cy, cx) in enumerate(coords):
                pred[cy, cx] = blended[i]

        # Static cells
        static_mask = np.isin(grid_classes, list(STATIC_TERRAIN))
        for y, x in zip(*np.where(static_mask)):
            pred[y, x] = PROB_FLOOR
            pred[y, x, grid_classes[y, x]] = 1.0 - (NUM_CLASSES - 1) * PROB_FLOOR

        return pred


def main():
    rounds_data = load_cached_rounds()
    print(f"Loaded {len(rounds_data)} cached rounds")
    print(f"sklearn: {'available' if HAS_SKLEARN else 'MISSING'}")

    print("\n=== V5 BASELINE (LightGBM 51-feat) ===")
    v5_results = evaluate_leave_one_out(BaselineLGBM, rounds_data)

    print("\n=== V6 ENSEMBLE (LGB+MLP+Transition 56-feat) ===")
    v6_results = evaluate_leave_one_out(V6Ensemble, rounds_data)

    # Comparison
    print("\n" + "=" * 60)
    print("HEAD-TO-HEAD COMPARISON")
    print("=" * 60)

    v5_overall = v5_results["overall"]["mean"]
    v6_overall = v6_results["overall"]["mean"]
    delta = v6_overall - v5_overall
    print(f"\n  V5 overall: {v5_overall:.1f}")
    print(f"  V6 overall: {v6_overall:.1f}")
    print(f"  Delta:      {delta:+.1f}")

    for regime in ("death", "stable", "growth"):
        v5r = v5_results["per_regime"].get(regime, {})
        v6r = v6_results["per_regime"].get(regime, {})
        if v5r and v6r:
            d = v6r["mean"] - v5r["mean"]
            print(f"  {regime:>6}: V5={v5r['mean']:.1f}  V6={v6r['mean']:.1f}  delta={d:+.1f}")

    # Per-round comparison
    print("\nPer-round breakdown:")
    print(f"  {'Round':>5} {'Regime':>7} {'V5':>6} {'V6':>6} {'Delta':>7} {'Winner':>7}")
    v6_wins = 0
    for rn in sorted(v5_results["per_round"].keys()):
        v5s = v5_results["per_round"][rn]["score"]
        v6s = v6_results["per_round"][rn]["score"]
        regime = v5_results["per_round"][rn]["regime"]
        d = v6s - v5s
        winner = "V6" if d > 0 else "V5" if d < 0 else "TIE"
        if d > 0:
            v6_wins += 1
        print(f"  R{rn:>3} {regime:>7} {v5s:>6.1f} {v6s:>6.1f} {d:>+7.1f} {winner:>7}")

    total = len(v5_results["per_round"])
    print(f"\n  V6 wins: {v6_wins}/{total} rounds")
    print(f"\n  RECOMMENDATION: {'DEPLOY V6' if delta > 0 else 'KEEP V5'}")

    # Save
    out = Path(__file__).parent / "data" / "compare_v5_v6.json"
    with open(out, "w") as f:
        json.dump({"v5": v5_results, "v6": v6_results, "delta": delta}, f, indent=2)
    print(f"\n  Saved to {out}")


if __name__ == "__main__":
    main()
