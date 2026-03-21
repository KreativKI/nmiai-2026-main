#!/usr/bin/env python3
"""
Brain V4: Gradient Boosted Terrain Prediction.

Replaces lookup tables with LightGBM trained on 14+ rounds of ground truth.
Captures non-linear feature interactions the lookup table misses.

Features per cell:
  - Initial terrain class (6)
  - 8-neighbor terrain counts (6 counts)
  - Distance to nearest settlement (bucketed 0-5+)
  - Settlement count within radius 3
  - Forest count within radius 2
  - Ocean adjacency count
  - Edge distance (min distance to grid boundary)
  - Cluster size (connected settlements)

Target: 6-class probability distribution.

Usage:
  python brain_v4.py                # Train and backtest
  python brain_v4.py --compare      # Compare V4 vs V2 vs V3
"""

import argparse
import json
import pickle
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import lightgbm as lgb

import sys
sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    load_cached_rounds, score_prediction,
    TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, PROB_FLOOR, CLASS_NAMES,
)
from regime_model import classify_round

DATA_DIR = Path(__file__).parent / "data"


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def extract_features(grid, y, x, h, w):
    """Rich feature vector for one cell."""
    my_cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)

    # 8-neighbor counts
    counts = [0] * NUM_CLASSES
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w:
                ncls = TERRAIN_TO_CLASS.get(int(grid[ny][nx]), 0)
                counts[ncls] += 1

    # Distance to nearest settlement (Manhattan, capped at 6)
    min_dist_settle = 99
    settle_r3 = 0
    forest_r2 = 0
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w:
                ncls = TERRAIN_TO_CLASS.get(int(grid[ny][nx]), 0)
                d = abs(dy) + abs(dx)
                if ncls in (1, 2):
                    min_dist_settle = min(min_dist_settle, d)
                    if d <= 3:
                        settle_r3 += 1
                if ncls == 4 and d <= 2:
                    forest_r2 += 1
    dist_settle = min(min_dist_settle, 6)

    # Ocean adjacency
    ocean_adj = 0
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if (dy, dx) == (0, 0):
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and int(grid[ny][nx]) == 10:
                ocean_adj += 1

    # Edge distance
    edge_dist = min(y, x, h - 1 - y, w - 1 - x)

    features = [
        my_cls,           # 0: terrain type
        counts[0],        # 1: empty neighbors
        counts[1],        # 2: settlement neighbors
        counts[2],        # 3: port neighbors
        counts[3],        # 4: ruin neighbors
        counts[4],        # 5: forest neighbors
        counts[5],        # 6: mountain neighbors
        dist_settle,      # 7: distance to nearest settlement
        settle_r3,        # 8: settlements within radius 3
        forest_r2,        # 9: forests within radius 2
        ocean_adj,        # 10: ocean adjacency
        edge_dist,        # 11: distance to grid edge
    ]
    return features


def build_dataset(rounds_data, exclude_round=None):
    """Build training dataset from cached rounds."""
    X, Y = [], []
    regimes = []

    for rd in rounds_data:
        if exclude_round and rd["round_number"] == exclude_round:
            continue
        if not rd.get("seeds"):
            continue
        regime, _ = classify_round(rd)
        h, w = rd["map_height"], rd["map_width"]

        for si_str, sd in rd["seeds"].items():
            si = int(si_str)
            ig = rd["initial_states"][si]["grid"]
            gt = np.array(sd["ground_truth"])

            for y in range(h):
                for x in range(w):
                    if int(ig[y][x]) in STATIC_TERRAIN:
                        continue
                    feats = extract_features(ig, y, x, h, w)
                    # Add regime as feature
                    regime_enc = {"death": 0, "stable": 1, "growth": 2}.get(regime, 1)
                    feats.append(regime_enc)  # 12: regime
                    X.append(feats)
                    Y.append(gt[y, x])  # 6-class probability distribution

    return np.array(X, dtype=np.float32), np.array(Y, dtype=np.float32)


class BrainV4:
    """Gradient boosted terrain prediction model."""

    FEATURE_NAMES = [
        "terrain", "n_empty", "n_settle", "n_port", "n_ruin",
        "n_forest", "n_mountain", "dist_settle", "settle_r3",
        "forest_r2", "ocean_adj", "edge_dist", "regime"
    ]

    def __init__(self):
        self.models = {}  # One model per terrain class

    def train(self, X, Y):
        """Train 6 independent regression models, one per output class."""
        log(f"Training on {len(X)} cells, {len(self.FEATURE_NAMES)} features")

        for cls in range(NUM_CLASSES):
            y_cls = Y[:, cls]
            params = {
                "objective": "regression",
                "metric": "mse",
                "num_leaves": 31,
                "learning_rate": 0.05,
                "n_estimators": 200,
                "min_child_samples": 20,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "verbose": -1,
            }
            model = lgb.LGBMRegressor(**params)
            model.fit(X, y_cls)
            self.models[cls] = model

        log(f"Trained {NUM_CLASSES} models")

    def predict_cell(self, features):
        """Predict probability distribution for one cell."""
        x = np.array(features, dtype=np.float32).reshape(1, -1)
        probs = np.array([self.models[cls].predict(x)[0] for cls in range(NUM_CLASSES)])
        probs = np.maximum(probs, PROB_FLOOR)
        probs = probs / probs.sum()
        return probs

    def predict_grid(self, round_data, seed_idx, regime="stable"):
        """Predict full grid."""
        h, w = round_data["map_height"], round_data["map_width"]
        grid = round_data["initial_states"][seed_idx]["grid"]
        regime_enc = {"death": 0, "stable": 1, "growth": 2}.get(regime, 1)

        # Batch predict for speed
        cells = []
        coords = []
        for y in range(h):
            for x in range(w):
                if int(grid[y][x]) in STATIC_TERRAIN:
                    continue
                feats = extract_features(grid, y, x, h, w)
                feats.append(regime_enc)
                cells.append(feats)
                coords.append((y, x))

        if cells:
            X = np.array(cells, dtype=np.float32)
            preds = np.zeros((len(cells), NUM_CLASSES))
            for cls in range(NUM_CLASSES):
                preds[:, cls] = self.models[cls].predict(X)

        # Build output grid
        pred = np.zeros((h, w, NUM_CLASSES))
        for i, (y, x) in enumerate(coords):
            pred[y, x] = preds[i]

        # Static cells
        for y in range(h):
            for x in range(w):
                if int(grid[y][x]) in STATIC_TERRAIN:
                    cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)
                    pred[y, x] = PROB_FLOOR
                    pred[y, x, cls] = 1.0 - (NUM_CLASSES - 1) * PROB_FLOOR

        pred = np.maximum(pred, PROB_FLOOR)
        pred = pred / pred.sum(axis=-1, keepdims=True)
        return pred

    def save(self, path):
        with open(path, "wb") as f:
            pickle.dump(self.models, f)

    def load(self, path):
        with open(path, "rb") as f:
            self.models = pickle.load(f)


def backtest_v4(rounds_data):
    """Leave-one-round-out backtest."""
    scores = []
    for rd in rounds_data:
        if not rd.get("seeds"):
            continue
        rn = rd["round_number"]
        regime, _ = classify_round(rd)

        X_train, Y_train = build_dataset(rounds_data, exclude_round=rn)
        brain = BrainV4()
        brain.train(X_train, Y_train)

        h, w = rd["map_height"], rd["map_width"]
        round_scores = []
        for si_str, sd in rd["seeds"].items():
            si = int(si_str)
            gt = np.array(sd["ground_truth"])
            ig = rd["initial_states"][si]["grid"]
            pred = brain.predict_grid(rd, si, regime=regime)
            result = score_prediction(gt, pred, initial_grid=ig)
            round_scores.append(result["score"])

        avg = np.mean(round_scores)
        scores.append(avg)
        log(f"R{rn} [{regime:>6}]: {avg:.1f}")

    log(f"\nV4 avg: {np.mean(scores):.2f}")
    return scores


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args()

    rounds_data = load_cached_rounds()
    log(f"Loaded {len(rounds_data)} rounds")

    if args.compare:
        from regime_model import RegimeModel
        from learned_model import NeighborhoodModel

        log("\n=== V4 (LightGBM) ===")
        v4_scores = backtest_v4(rounds_data)

        log("\n=== V3 (Regime lookup) ===")
        v3_scores = []
        for rd in rounds_data:
            if not rd.get("seeds"):
                continue
            rn = rd["round_number"]
            regime, _ = classify_round(rd)
            brain = RegimeModel()
            for other in rounds_data:
                if other["round_number"] != rn:
                    brain.add_training_data(other)
            brain.finalize()
            rs = []
            for si_str, sd in rd["seeds"].items():
                si = int(si_str)
                gt = np.array(sd["ground_truth"])
                ig = rd["initial_states"][si]["grid"]
                pred = brain.predict_grid(rd, si, regime=regime)
                pred = np.maximum(pred, PROB_FLOOR)
                pred /= pred.sum(axis=-1, keepdims=True)
                rs.append(score_prediction(gt, pred, initial_grid=ig)["score"])
            v3_scores.append(np.mean(rs))
            log(f"R{rn} [{regime:>6}]: {np.mean(rs):.1f}")

        log(f"\n=== COMPARISON ===")
        log(f"V4 avg: {np.mean(v4_scores):.2f}")
        log(f"V3 avg: {np.mean(v3_scores):.2f}")
        log(f"Delta: {np.mean(v4_scores) - np.mean(v3_scores):+.2f}")

        for i, rd in enumerate([r for r in rounds_data if r.get("seeds")]):
            rn = rd["round_number"]
            regime, _ = classify_round(rd)
            d = v4_scores[i] - v3_scores[i]
            winner = "V4" if d > 0 else "V3"
            log(f"  R{rn} [{regime}]: V4={v4_scores[i]:.1f} V3={v3_scores[i]:.1f} {d:+.1f} -> {winner}")
    else:
        backtest_v4(rounds_data)


if __name__ == "__main__":
    main()
