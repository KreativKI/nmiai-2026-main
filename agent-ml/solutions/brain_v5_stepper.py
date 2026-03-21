#!/usr/bin/env python3
"""
Brain V5: Step-Forward Temporal Predictor.

APPROACH B: Instead of predicting year 50 directly, predict year-by-year.
Trains a 1-step model (year N -> year N+1), then runs it forward 50 times.
Each step's output becomes the next step's input.

This captures temporal dynamics: growth curves, conflict waves, winter effects.
The model learns transition RATES, not just final outcomes.

Usage:
  python brain_v5_stepper.py                # Train and backtest
  python brain_v5_stepper.py --compare      # Compare V5 vs V4 vs V3
  python brain_v5_stepper.py --steps 5      # Use 5-year steps instead of 1
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

CLASS_TO_TERRAIN = {v: k for k, v in TERRAIN_TO_CLASS.items()}


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def extract_features(grid, y, x, h, w):
    """Spatial features for one cell (no temporal, used at each step)."""
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

    ocean_adj = sum(
        1 for dy in (-1, 0, 1) for dx in (-1, 0, 1)
        if (dy, dx) != (0, 0) and 0 <= y+dy < h and 0 <= x+dx < w
        and int(grid[y+dy][x+dx]) == 10
    )

    return [my_cls, counts[0], counts[1], counts[2], counts[3],
            counts[4], counts[5], min(min_dist, 6), settle_r3, ocean_adj]


def build_step_dataset(replay_dir=REPLAY_DIR, step_size=5, exclude_round=None):
    """Build 1-step transition dataset from replay data."""
    X, Y = [], []
    for rf in sorted(replay_dir.glob("r*_seed*.json")):
        rn = int(rf.stem.split("_")[0][1:])
        if exclude_round and rn == exclude_round:
            continue
        with open(rf) as f:
            data = json.load(f)
        h, w = data["height"], data["width"]
        frames = data["frames"]

        for t in range(0, 50, step_size):
            t_next = min(t + step_size, 50)
            grid_now = frames[t]["grid"]
            grid_next = frames[t_next]["grid"]

            for y in range(h):
                for x in range(w):
                    if int(grid_now[y][x]) in STATIC_TERRAIN:
                        continue
                    feats = extract_features(grid_now, y, x, h, w)
                    target_cls = TERRAIN_TO_CLASS.get(int(grid_next[y][x]), 0)
                    target = np.zeros(NUM_CLASSES)
                    target[target_cls] = 1.0
                    X.append(feats)
                    Y.append(target)

    return np.array(X, dtype=np.float32), np.array(Y, dtype=np.float32)


class BrainV5:
    """Step-forward predictor: run 1-step model N times."""

    def __init__(self, step_size=5, lgb_params=None):
        self.step_size = step_size
        self.models = {}
        self.lgb_params = lgb_params or {
            "objective": "regression", "metric": "mse",
            "n_estimators": 50, "num_leaves": 31,
            "learning_rate": 0.05, "min_child_samples": 20,
            "subsample": 0.8, "colsample_bytree": 0.8,
            "verbose": -1,
        }

    def train(self, X, Y):
        log(f"Training stepper on {len(X)} transitions, step_size={self.step_size}")
        for cls in range(NUM_CLASSES):
            model = lgb.LGBMRegressor(**self.lgb_params)
            model.fit(X, Y[:, cls])
            self.models[cls] = model
        log("Trained 6 models")

    def step_once(self, grid, h, w):
        """Predict one step forward. Returns probability grid."""
        cells, coords = [], []
        for y in range(h):
            for x in range(w):
                if int(grid[y][x]) in STATIC_TERRAIN:
                    continue
                cells.append(extract_features(grid, y, x, h, w))
                coords.append((y, x))

        pred = np.zeros((h, w, NUM_CLASSES))
        if cells:
            X = np.array(cells, dtype=np.float32)
            for cls in range(NUM_CLASSES):
                preds_cls = self.models[cls].predict(X)
                for i, (y, x) in enumerate(coords):
                    pred[y, x, cls] = preds_cls[i]

        # Static cells
        for y in range(h):
            for x in range(w):
                if int(grid[y][x]) in STATIC_TERRAIN:
                    cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)
                    pred[y, x] = PROB_FLOOR
                    pred[y, x, cls] = 1.0 - (NUM_CLASSES - 1) * PROB_FLOOR

        pred = np.maximum(pred, PROB_FLOOR)
        pred /= pred.sum(axis=-1, keepdims=True)
        return pred

    def prob_to_grid(self, pred, original_grid, h, w):
        """Convert probability grid to terrain grid (argmax) for next step."""
        grid = []
        for y in range(h):
            row = []
            for x in range(w):
                if int(original_grid[y][x]) in STATIC_TERRAIN:
                    row.append(int(original_grid[y][x]))
                else:
                    cls = int(np.argmax(pred[y, x]))
                    # Map class back to terrain code
                    row.append(CLASS_TO_TERRAIN.get(cls, 11))
            grid.append(row)
        return grid

    def predict_grid(self, round_data, seed_idx, regime="stable"):
        """Run stepper forward from year 0 to year 50."""
        h, w = round_data["map_height"], round_data["map_width"]
        grid = round_data["initial_states"][seed_idx]["grid"]
        n_steps = 50 // self.step_size

        # Accumulate probability predictions across steps
        cumulative_pred = None

        current_grid = [row[:] for row in grid]  # Deep copy
        for step in range(n_steps):
            pred = self.step_once(current_grid, h, w)
            if cumulative_pred is None:
                cumulative_pred = pred.copy()
            else:
                # Blend: accumulate probability mass
                # Weight later steps more (they're closer to year 50)
                weight = (step + 1) / n_steps
                cumulative_pred = (1 - weight) * cumulative_pred + weight * pred

            # Convert to grid for next step's input
            current_grid = self.prob_to_grid(pred, grid, h, w)

        # Final prediction is the last step's probabilities
        # (cumulative helps with uncertainty)
        final = 0.5 * pred + 0.5 * cumulative_pred
        final = np.maximum(final, PROB_FLOOR)
        final /= final.sum(axis=-1, keepdims=True)
        return final

    def save(self, path):
        with open(path, "wb") as f:
            pickle.dump({"models": self.models, "step_size": self.step_size}, f)

    def load(self, path):
        with open(path, "rb") as f:
            d = pickle.load(f)
            self.models = d["models"]
            self.step_size = d.get("step_size", 5)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--steps", type=int, default=5, help="Step size in years")
    args = parser.parse_args()

    rounds_data = load_cached_rounds()
    log(f"Loaded {len(rounds_data)} rounds")

    if args.compare:
        from brain_v4 import BrainV4, build_dataset as build_v4_dataset

        log(f"\n=== V5 Stepper (step_size={args.steps}) ===")
        v5_scores = []
        for rd in rounds_data:
            if not rd.get("seeds"):
                continue
            rn = rd["round_number"]
            regime, _ = classify_round(rd)

            X, Y = build_step_dataset(exclude_round=rn, step_size=args.steps)
            brain = BrainV5(step_size=args.steps)
            brain.train(X, Y)

            rs = []
            for si_str, sd in rd["seeds"].items():
                si = int(si_str)
                gt = np.array(sd["ground_truth"])
                ig = rd["initial_states"][si]["grid"]
                pred = brain.predict_grid(rd, si, regime=regime)
                rs.append(score_prediction(gt, pred, initial_grid=ig)["score"])
            avg = np.mean(rs)
            v5_scores.append(avg)
            log(f"R{rn} [{regime:>6}]: {avg:.1f}")

        log(f"\n=== V4 (Original) ===")
        v4_scores = []
        for rd in rounds_data:
            if not rd.get("seeds"):
                continue
            rn = rd["round_number"]
            regime, _ = classify_round(rd)
            X, Y = build_v4_dataset(rounds_data, exclude_round=rn)
            brain = BrainV4()
            brain.train(X, Y)
            rs = []
            for si_str, sd in rd["seeds"].items():
                si = int(si_str)
                gt = np.array(sd["ground_truth"])
                ig = rd["initial_states"][si]["grid"]
                pred = brain.predict_grid(rd, si, regime=regime)
                rs.append(score_prediction(gt, pred, initial_grid=ig)["score"])
            v4_scores.append(np.mean(rs))
            log(f"R{rn} [{regime:>6}]: {np.mean(rs):.1f}")

        log(f"\n=== COMPARISON ===")
        log(f"V5 avg: {np.mean(v5_scores):.2f}")
        log(f"V4 avg: {np.mean(v4_scores):.2f}")
        log(f"Delta: {np.mean(v5_scores) - np.mean(v4_scores):+.2f}")
    else:
        X, Y = build_step_dataset(step_size=args.steps)
        brain = BrainV5(step_size=args.steps)
        brain.train(X, Y)
        brain.save(DATA_DIR / "brain_v5.pkl")
        log("Saved to data/brain_v5.pkl")


if __name__ == "__main__":
    main()
