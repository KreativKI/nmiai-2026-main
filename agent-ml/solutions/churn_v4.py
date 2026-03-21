#!/usr/bin/env python3
"""
Continuous V4 (LightGBM) Hyperparameter Optimization.

Same concept as churn_v2/v3 but for Brain V4:
- Tries different LightGBM hyperparameters
- Backtests each variant (leave-one-out on last 5 rounds)
- Saves best params to brain_v4_params.json
- overnight_v3 reads params at submission time

Knobs:
  - n_estimators, num_leaves, learning_rate
  - min_child_samples, subsample, colsample_bytree
  - Dirichlet alpha (observation blending strength)

Usage:
  python churn_v4.py    # Run continuous loop
"""

import json
import os
import tempfile
import time
import random
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
from build_dataset import build_master_dataset, FEATURE_NAMES, extract_cell_features

DATA_DIR = Path(__file__).parent / "data"
PARAMS_FILE = DATA_DIR / "brain_v4_params.json"
CHURN_LOG = Path.home() / "churn_v4.log"
COMPETITION_END = datetime(2026, 3, 22, 14, 0, 0, tzinfo=timezone.utc)


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        with open(CHURN_LOG, "a") as f:
            f.write(line + "\n")
    except Exception:
        print(line, flush=True)


def load_best():
    if PARAMS_FILE.exists():
        try:
            with open(PARAMS_FILE) as f:
                p = json.load(f)
            return p.get("score", 0), p
        except (json.JSONDecodeError, ValueError):
            pass
    return 0, {}


def save_if_better(score, params, experiment_name):
    best_score, _ = load_best()
    if score > best_score:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        params["score"] = round(float(score), 2)
        params["baseline"] = round(float(best_score), 2)
        params["delta"] = round(float(score - best_score), 2)
        params["experiment"] = experiment_name
        params["fitted_at"] = datetime.now(timezone.utc).isoformat()
        fd, tmp_path = tempfile.mkstemp(dir=str(DATA_DIR), suffix=".json.tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(params, f, indent=2)
            os.replace(tmp_path, str(PARAMS_FILE))
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        log(f"  NEW BEST: {score:.2f} (was {best_score:.2f}, +{score - best_score:.2f}) [{experiment_name}]")
        return True
    return False


def score_variant(rounds_data, lgb_params, alpha):
    """Leave-one-out backtest on last 5 rounds with 32-feature master dataset."""
    test_rounds = rounds_data[-5:] if len(rounds_data) > 5 else rounds_data
    scores = []
    REPLAY_DIR = DATA_DIR / "replays"

    for rd in test_rounds:
        if not rd.get("seeds"):
            continue
        rn = rd["round_number"]
        regime, _ = classify_round(rd)
        h, w = rd["map_height"], rd["map_width"]

        # Train on 32-feature master dataset
        X_train, Y_train, _ = build_master_dataset(rounds_data, exclude_round=rn)
        models = {}
        for cls in range(NUM_CLASSES):
            model = lgb.LGBMRegressor(**lgb_params)
            model.fit(X_train, Y_train[:, cls])
            models[cls] = model

        ig0 = rd["initial_states"][0]["grid"]
        total_s = sum(1 for y in range(h) for x in range(w)
                      if TERRAIN_TO_CLASS.get(int(ig0[y][x]), 0) == 1)
        total_p = sum(1 for y in range(h) for x in range(w)
                      if TERRAIN_TO_CLASS.get(int(ig0[y][x]), 0) == 2)

        for si_str, sd in rd["seeds"].items():
            si = int(si_str)
            gt = np.array(sd["ground_truth"])
            ig = rd["initial_states"][si]["grid"]

            # Load replay for features
            replay_path = REPLAY_DIR / f"r{rn}_seed{si}.json"
            replay_data = None
            if replay_path.exists():
                try:
                    replay_data = json.load(open(replay_path))
                except Exception:
                    pass

            # Extract 32 features
            cells, coords = [], []
            for y in range(h):
                for x in range(w):
                    if int(ig[y][x]) in STATIC_TERRAIN:
                        continue
                    fd = extract_cell_features(ig, y, x, h, w, replay_data)
                    fd["regime_death"] = 1 if regime == "death" else 0
                    fd["regime_growth"] = 1 if regime == "growth" else 0
                    fd["regime_stable"] = 1 if regime == "stable" else 0
                    fd["total_settlements"] = total_s
                    fd["total_ports"] = total_p
                    cells.append([fd.get(n, 0) for n in FEATURE_NAMES])
                    coords.append((y, x))

            pred = np.zeros((h, w, NUM_CLASSES))
            if cells:
                Xp = np.array(cells, dtype=np.float32)
                for cls in range(NUM_CLASSES):
                    preds = models[cls].predict(Xp)
                    for i, (y, x) in enumerate(coords):
                        pred[y, x, cls] = preds[i]

            for y in range(h):
                for x in range(w):
                    if int(ig[y][x]) in STATIC_TERRAIN:
                        cls = TERRAIN_TO_CLASS.get(int(ig[y][x]), 0)
                        pred[y, x] = PROB_FLOOR
                        pred[y, x, cls] = 1.0 - (NUM_CLASSES - 1) * PROB_FLOOR

            pred = np.maximum(pred, PROB_FLOOR)
            pred /= pred.sum(axis=-1, keepdims=True)
            scores.append(score_prediction(gt, pred, initial_grid=ig)["score"])

    return np.mean(scores) if scores else 0.0


def run_experiments(rounds_data):
    """Run a batch of experiments varying LightGBM hyperparameters."""
    best_score, best_params = load_best()

    # Current best or defaults
    base = {
        "n_estimators": best_params.get("n_estimators", 200),
        "num_leaves": best_params.get("num_leaves", 31),
        "learning_rate": best_params.get("learning_rate", 0.05),
        "min_child_samples": best_params.get("min_child_samples", 20),
        "subsample": best_params.get("subsample", 0.8),
        "colsample_bytree": best_params.get("colsample_bytree", 0.8),
        "alpha_dirichlet": best_params.get("alpha_dirichlet", 20.0),
    }

    iteration = 0
    np.random.seed(int(time.time()) % 100000)

    def make_lgb_params(p):
        return {
            "objective": "regression", "metric": "mse",
            "n_estimators": p["n_estimators"],
            "num_leaves": p["num_leaves"],
            "learning_rate": p["learning_rate"],
            "min_child_samples": p["min_child_samples"],
            "subsample": p["subsample"],
            "colsample_bytree": p["colsample_bytree"],
            "verbose": -1,
        }

    def try_params(params, name):
        nonlocal iteration
        iteration += 1
        lgb_p = make_lgb_params(params)
        alpha = params["alpha_dirichlet"]
        s = score_variant(rounds_data, lgb_p, alpha)
        save_params = {k: (round(float(v), 4) if isinstance(v, float) else v) for k, v in params.items()}
        if save_if_better(s, save_params, name):
            for k, v in params.items():
                base[k] = v
        return s

    # A: n_estimators
    log("Experiment A: n_estimators")
    for n in [50, 100, 150, 200, 300, 500]:
        p = dict(base, n_estimators=n)
        s = try_params(p, f"n_est_{n}")
        log(f"  [{iteration}] n_estimators={n} -> {s:.2f}")

    # B: num_leaves
    log("Experiment B: num_leaves")
    for nl in [15, 20, 25, 31, 40, 50, 63]:
        p = dict(base, num_leaves=nl)
        s = try_params(p, f"leaves_{nl}")
        log(f"  [{iteration}] num_leaves={nl} -> {s:.2f}")

    # C: learning_rate
    log("Experiment C: learning_rate")
    for lr in [0.01, 0.02, 0.03, 0.05, 0.08, 0.1, 0.15]:
        p = dict(base, learning_rate=lr)
        s = try_params(p, f"lr_{lr}")
        log(f"  [{iteration}] lr={lr} -> {s:.2f}")

    # D: min_child_samples
    log("Experiment D: min_child_samples")
    for mc in [5, 10, 15, 20, 30, 50]:
        p = dict(base, min_child_samples=mc)
        s = try_params(p, f"min_child_{mc}")
        log(f"  [{iteration}] min_child={mc} -> {s:.2f}")

    # E: Dirichlet alpha
    log("Experiment E: Dirichlet alpha")
    for a in [5, 8, 10, 12, 15, 20, 25, 30, 40]:
        p = dict(base, alpha_dirichlet=float(a))
        s = try_params(p, f"alpha_{a}")
        log(f"  [{iteration}] alpha={a} -> {s:.2f}")

    # F: Random combined
    log("Experiment F: Combined random search")
    for _ in range(10):
        p = {
            "n_estimators": random.choice([100, 150, 200, 300, 400]),
            "num_leaves": random.choice([20, 25, 31, 40, 50]),
            "learning_rate": random.uniform(0.02, 0.12),
            "min_child_samples": random.choice([10, 15, 20, 30]),
            "subsample": random.uniform(0.6, 1.0),
            "colsample_bytree": random.uniform(0.6, 1.0),
            "alpha_dirichlet": random.uniform(10, 35),
        }
        s = try_params(p, f"combined_{iteration}")
        if iteration % 5 == 0:
            log(f"  [{iteration}] combined -> {s:.2f}")

    best_after, _ = load_best()
    log(f"\nBatch done: {iteration} experiments. Score: {best_score:.2f} -> {best_after:.2f}")
    return iteration


def main():
    log("=" * 60)
    log("CHURN V4: LightGBM HYPERPARAMETER OPTIMIZATION")
    log("=" * 60)

    total = 0
    batch = 0

    while datetime.now(timezone.utc) < COMPETITION_END:
        batch += 1
        rounds_data = load_cached_rounds()
        log(f"\nBatch {batch}: {len(rounds_data)} rounds")

        n = run_experiments(rounds_data)
        total += n

        best_score, best_params = load_best()
        log(f"Total: {total} experiments. Best: {best_score:.2f}")
        log(f"Params: n_est={best_params.get('n_estimators')}, "
            f"leaves={best_params.get('num_leaves')}, "
            f"lr={best_params.get('learning_rate')}, "
            f"alpha={best_params.get('alpha_dirichlet')}")

        log("Next batch in 30s...")
        time.sleep(30)

    log(f"\nDone. Total: {total} experiments.")


if __name__ == "__main__":
    main()
