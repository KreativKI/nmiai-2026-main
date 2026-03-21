#!/usr/bin/env python3
"""
Brain V4-R: LightGBM trained on REPLAY data (year-by-year transitions).

APPROACH A: Same V4 architecture but 50x more training data.
Instead of initial -> final (50 year jump), trains on year N -> year N+1.
14 rounds x 5 seeds x 50 steps x ~700 dynamic cells = ~2.4M transitions.

Features: same 13 from brain_v4 + temporal features:
  - Current year (0-50)
  - Settlement age (years since cell became settlement)
  - Food/population/wealth/defense from settlement stats

Usage:
  python brain_v4_replay.py                # Train and backtest
  python brain_v4_replay.py --compare      # Compare V4-R vs V4 vs V3
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
    TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, PROB_FLOOR,
)
from regime_model import classify_round

DATA_DIR = Path(__file__).parent / "data"
REPLAY_DIR = DATA_DIR / "replays"


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def extract_features(grid, y, x, h, w, year=50, settlement_stats=None):
    """Feature vector: brain_v4 features + temporal + settlement stats."""
    my_cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)

    counts = [0] * NUM_CLASSES
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w:
                counts[TERRAIN_TO_CLASS.get(int(grid[ny][nx]), 0)] += 1

    min_dist = 99
    settle_r3 = 0
    forest_r2 = 0
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w:
                ncls = TERRAIN_TO_CLASS.get(int(grid[ny][nx]), 0)
                d = abs(dy) + abs(dx)
                if ncls in (1, 2):
                    min_dist = min(min_dist, d)
                    if d <= 3:
                        settle_r3 += 1
                if ncls == 4 and d <= 2:
                    forest_r2 += 1

    ocean_adj = 0
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if (dy, dx) == (0, 0):
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and int(grid[ny][nx]) == 10:
                ocean_adj += 1

    edge_dist = min(y, x, h - 1 - y, w - 1 - x)

    # Settlement stats for this cell (if available)
    food, pop, wealth, defense = 0.0, 0.0, 0.0, 0.0
    if settlement_stats:
        for s in settlement_stats:
            if s.get("x") == x and s.get("y") == y:
                food = s.get("food", 0.0)
                pop = s.get("population", 0.0)
                wealth = s.get("wealth", 0.0)
                defense = s.get("defense", 0.0)
                break

    features = [
        my_cls, counts[0], counts[1], counts[2], counts[3],
        counts[4], counts[5], min(min_dist, 6), settle_r3,
        forest_r2, ocean_adj, edge_dist,
        year / 50.0,    # Normalized year
        food, pop, wealth, defense,
    ]
    return features


FEATURE_NAMES = [
    "terrain", "n_empty", "n_settle", "n_port", "n_ruin",
    "n_forest", "n_mountain", "dist_settle", "settle_r3",
    "forest_r2", "ocean_adj", "edge_dist",
    "year", "food", "pop", "wealth", "defense",
]


def build_replay_dataset(replay_dir=REPLAY_DIR, step_interval=10):
    """Build training data from replay frames.

    Uses transitions every `step_interval` years to avoid correlated samples.
    Year 0->10, 10->20, 20->30, 30->40, 40->50 = 5 transitions per replay.
    """
    X, Y = [], []
    replay_files = sorted(replay_dir.glob("r*_seed*.json"))
    log(f"Loading {len(replay_files)} replay files...")

    for rf in replay_files:
        with open(rf) as f:
            data = json.load(f)

        h, w = data["height"], data["width"]
        frames = data["frames"]

        for step_from in range(0, 50, step_interval):
            step_to = min(step_from + step_interval, 50)
            frame_from = frames[step_from]
            frame_to = frames[step_to]

            grid_from = frame_from["grid"]
            grid_to = frame_to["grid"]
            settlements = frame_from.get("settlements", [])

            for y in range(h):
                for x in range(w):
                    if int(grid_from[y][x]) in STATIC_TERRAIN:
                        continue

                    feats = extract_features(
                        grid_from, y, x, h, w,
                        year=step_from,
                        settlement_stats=settlements,
                    )

                    # Target: terrain class at step_to (one-hot probability)
                    target_cls = TERRAIN_TO_CLASS.get(int(grid_to[y][x]), 0)
                    target = np.zeros(NUM_CLASSES)
                    target[target_cls] = 1.0

                    X.append(feats)
                    Y.append(target)

    X = np.array(X, dtype=np.float32)
    Y = np.array(Y, dtype=np.float32)
    log(f"Dataset: {len(X)} samples, {X.shape[1]} features")
    return X, Y


class BrainV4R:
    """V4 with replay data: same LightGBM architecture, temporal features."""

    def __init__(self, lgb_params=None):
        self.models = {}
        self.lgb_params = lgb_params or {
            "objective": "regression", "metric": "mse",
            "n_estimators": 100, "num_leaves": 31,
            "learning_rate": 0.05, "min_child_samples": 20,
            "subsample": 0.8, "colsample_bytree": 0.8,
            "verbose": -1,
        }

    def train(self, X, Y):
        log(f"Training on {len(X)} samples, {X.shape[1]} features")
        for cls in range(NUM_CLASSES):
            model = lgb.LGBMRegressor(**self.lgb_params)
            model.fit(X, Y[:, cls])
            self.models[cls] = model
        log("Trained 6 models")

    def predict_grid(self, round_data, seed_idx, regime="stable"):
        """Predict year 50 state from year 0."""
        h, w = round_data["map_height"], round_data["map_width"]
        grid = round_data["initial_states"][seed_idx]["grid"]

        cells, coords = [], []
        for y in range(h):
            for x in range(w):
                if int(grid[y][x]) in STATIC_TERRAIN:
                    continue
                feats = extract_features(grid, y, x, h, w, year=0)
                cells.append(feats)
                coords.append((y, x))

        pred = np.zeros((h, w, NUM_CLASSES))
        if cells:
            X = np.array(cells, dtype=np.float32)
            for cls in range(NUM_CLASSES):
                preds_cls = self.models[cls].predict(X)
                for i, (y, x) in enumerate(coords):
                    pred[y, x, cls] = preds_cls[i]

        for y in range(h):
            for x in range(w):
                if int(grid[y][x]) in STATIC_TERRAIN:
                    cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)
                    pred[y, x] = PROB_FLOOR
                    pred[y, x, cls] = 1.0 - (NUM_CLASSES - 1) * PROB_FLOOR

        pred = np.maximum(pred, PROB_FLOOR)
        pred /= pred.sum(axis=-1, keepdims=True)
        return pred

    def save(self, path):
        with open(path, "wb") as f:
            pickle.dump({"models": self.models, "params": self.lgb_params}, f)

    def load(self, path):
        with open(path, "rb") as f:
            d = pickle.load(f)
            self.models = d["models"]
            self.lgb_params = d.get("params", {})


def backtest(rounds_data, brain_cls, train_fn, label="V4-R"):
    """Leave-one-round-out backtest."""
    scores = []
    for rd in rounds_data:
        if not rd.get("seeds"):
            continue
        rn = rd["round_number"]
        regime, _ = classify_round(rd)

        # Exclude this round's replays from training
        X, Y = train_fn(exclude_round=rn)
        brain = brain_cls()
        brain.train(X, Y)

        round_scores = []
        for si_str, sd in rd["seeds"].items():
            si = int(si_str)
            gt = np.array(sd["ground_truth"])
            ig = rd["initial_states"][si]["grid"]
            pred = brain.predict_grid(rd, si, regime=regime)
            s = score_prediction(gt, pred, initial_grid=ig)["score"]
            round_scores.append(s)

        avg = np.mean(round_scores)
        scores.append(avg)
        log(f"R{rn} [{regime:>6}]: {avg:.1f}")

    log(f"{label} avg: {np.mean(scores):.2f}")
    return scores


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--step-interval", type=int, default=10)
    args = parser.parse_args()

    rounds_data = load_cached_rounds()
    log(f"Loaded {len(rounds_data)} rounds")

    if args.compare:
        from brain_v4 import BrainV4, build_dataset as build_v4_dataset

        # V4-R with replay data
        log("\n=== V4-R (Replay-trained LightGBM) ===")

        def train_v4r(exclude_round=None):
            # Build from replays, excluding one round
            X_all, Y_all = [], []
            for rf in sorted(REPLAY_DIR.glob("r*_seed*.json")):
                rn = int(rf.stem.split("_")[0][1:])
                if exclude_round and rn == exclude_round:
                    continue
                with open(rf) as f:
                    data = json.load(f)
                h, w = data["height"], data["width"]
                frames = data["frames"]
                for step_from in range(0, 50, args.step_interval):
                    step_to = min(step_from + args.step_interval, 50)
                    gf = frames[step_from]["grid"]
                    gt = frames[step_to]["grid"]
                    setts = frames[step_from].get("settlements", [])
                    for y in range(h):
                        for x in range(w):
                            if int(gf[y][x]) in STATIC_TERRAIN:
                                continue
                            feats = extract_features(gf, y, x, h, w, step_from, setts)
                            tc = TERRAIN_TO_CLASS.get(int(gt[y][x]), 0)
                            target = np.zeros(NUM_CLASSES)
                            target[tc] = 1.0
                            X_all.append(feats)
                            Y_all.append(target)
            return np.array(X_all, dtype=np.float32), np.array(Y_all, dtype=np.float32)

        v4r_scores = backtest(rounds_data, BrainV4R, train_v4r, "V4-R")

        # V4 baseline
        log("\n=== V4 (Original) ===")

        def train_v4(exclude_round=None):
            return build_v4_dataset(rounds_data, exclude_round=exclude_round)

        v4_scores = backtest(rounds_data, BrainV4, train_v4, "V4")

        log(f"\n=== COMPARISON ===")
        log(f"V4-R avg: {np.mean(v4r_scores):.2f}")
        log(f"V4   avg: {np.mean(v4_scores):.2f}")
        log(f"Delta: {np.mean(v4r_scores) - np.mean(v4_scores):+.2f}")
    else:
        X, Y = build_replay_dataset(step_interval=args.step_interval)
        brain = BrainV4R()
        brain.train(X, Y)
        brain.save(DATA_DIR / "brain_v4r.pkl")
        log("Saved to data/brain_v4r.pkl")


if __name__ == "__main__":
    main()
