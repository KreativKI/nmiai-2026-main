#!/usr/bin/env python3
"""
Astar Island Continuous Improvement Loop — "Machine Learning"

Runs continuously, churning through data to find better models:
1. Cache ground truth from completed rounds
2. Grid search learned model hyperparameters
3. Backtest every variant (leave-one-out)
4. Run hindsight on rounds with observation data
5. Test feature engineering variants
6. Log results, save best model

Usage:
  python churn.py --token TOKEN                    # Run full loop once
  python churn.py --token TOKEN --continuous       # Run in loop (for GCP VM)
  python churn.py --token TOKEN --grid-search      # Just hyperparameter search
  python churn.py --token TOKEN --feature-search   # Just feature engineering
"""

import argparse
import json
import time
import itertools
from pathlib import Path
from datetime import datetime, timezone

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    PredictionModel, load_cached_rounds, score_prediction,
    load_real_observations, get_session, cache_round,
    TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, CLASS_NAMES, PROB_FLOOR,
    BASE,
)
from learned_model import NeighborhoodModel, extract_cell_features

DATA_DIR = Path(__file__).parent / "data"
RESULTS_DIR = DATA_DIR / "churn_results"


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


# ──────────────────────────────────────────────
# Extended Feature Extractors
# ──────────────────────────────────────────────

def extract_features_v2(grid, y, x, h, w):
    """V2 features: base + distance to nearest settlement + settlement density in radius 3."""
    my_cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)
    counts = [0] * NUM_CLASSES
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w:
                ncls = TERRAIN_TO_CLASS.get(int(grid[ny][nx]), 0)
                counts[ncls] += 1

    # Distance to nearest settlement (capped at 5)
    min_dist = 99
    settle_r3 = 0
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w:
                ncls = TERRAIN_TO_CLASS.get(int(grid[ny][nx]), 0)
                if ncls in (1, 2):
                    d = abs(dy) + abs(dx)
                    min_dist = min(min_dist, d)
                    if d <= 3:
                        settle_r3 += 1
    dist_bucket = min(min_dist, 5)

    return (my_cls, tuple(counts), dist_bucket, settle_r3)


def feature_key_v2_full(my_cls, counts, dist_bucket, settle_r3):
    return (my_cls,) + counts + (dist_bucket, settle_r3)


def feature_key_v2_reduced(my_cls, counts, dist_bucket, settle_r3):
    n_dynamic = counts[1] + counts[2] + counts[3]
    n_forest = counts[4]
    return (my_cls, n_dynamic, n_forest, dist_bucket)


def feature_key_v2_minimal(my_cls, counts, dist_bucket, settle_r3):
    has_settle = 1 if (counts[1] + counts[2]) > 0 else 0
    return (my_cls, has_settle, min(dist_bucket, 3))


class NeighborhoodModelV2(NeighborhoodModel):
    """Extended model with richer features (distance to settlement, density)."""

    def add_training_data(self, round_data, exclude_round=None):
        rn = round_data["round_number"]
        if exclude_round is not None and rn == exclude_round:
            return
        h, w = round_data["map_height"], round_data["map_width"]

        for si_str, seed_data in round_data["seeds"].items():
            si = int(si_str)
            ig = round_data["initial_states"][si]["grid"]
            gt = np.array(seed_data["ground_truth"])

            for y in range(h):
                for x in range(w):
                    my_cls, counts, dist_bucket, settle_r3 = extract_features_v2(
                        ig, y, x, h, w)
                    gt_dist = gt[y, x]

                    for level, key_fn in [
                        ("full", lambda: feature_key_v2_full(my_cls, counts, dist_bucket, settle_r3)),
                        ("reduced", lambda: feature_key_v2_reduced(my_cls, counts, dist_bucket, settle_r3)),
                        ("minimal", lambda: feature_key_v2_minimal(my_cls, counts, dist_bucket, settle_r3)),
                    ]:
                        key = key_fn()
                        if key not in self.tables[level]:
                            self.tables[level][key] = [np.zeros(NUM_CLASSES), 0]
                        self.tables[level][key][0] += gt_dist
                        self.tables[level][key][1] += 1

                    if my_cls not in self.global_dist:
                        self.global_dist[my_cls] = [np.zeros(NUM_CLASSES), 0]
                    self.global_dist[my_cls][0] += gt_dist
                    self.global_dist[my_cls][1] += 1
                    self.total_cells += 1

        self.training_rounds.append(rn)

    def predict_cell(self, grid, y, x, h, w):
        terrain = grid[y][x]
        if terrain in STATIC_TERRAIN:
            cls = TERRAIN_TO_CLASS.get(int(terrain), 0)
            dist = np.full(NUM_CLASSES, PROB_FLOOR)
            dist[cls] = 1.0 - (NUM_CLASSES - 1) * PROB_FLOOR
            return dist

        my_cls, counts, dist_bucket, settle_r3 = extract_features_v2(grid, y, x, h, w)

        key_full = feature_key_v2_full(my_cls, counts, dist_bucket, settle_r3)
        if key_full in self.distributions["full"]:
            count = self.tables["full"][key_full][1]
            if count >= self.min_samples_full:
                return self.distributions["full"][key_full].copy()

        key_reduced = feature_key_v2_reduced(my_cls, counts, dist_bucket, settle_r3)
        if key_reduced in self.distributions["reduced"]:
            count = self.tables["reduced"][key_reduced][1]
            if count >= self.min_samples_reduced:
                return self.distributions["reduced"][key_reduced].copy()

        key_minimal = feature_key_v2_minimal(my_cls, counts, dist_bucket, settle_r3)
        if key_minimal in self.distributions["minimal"]:
            return self.distributions["minimal"][key_minimal].copy()

        if my_cls in self.global_fallback:
            return self.global_fallback[my_cls].copy()

        return np.full(NUM_CLASSES, 1.0 / NUM_CLASSES)


# ──────────────────────────────────────────────
# Grid Search
# ──────────────────────────────────────────────

def grid_search_hyperparams(rounds_data):
    """Grid search over min_samples thresholds."""
    log("Grid searching hyperparameters...")

    param_grid = {
        "min_samples_full": [3, 5, 8, 12, 20],
        "min_samples_reduced": [5, 10, 15, 25],
    }

    best_score = -1
    best_params = None
    results = []

    for ms_full, ms_reduced in itertools.product(
        param_grid["min_samples_full"],
        param_grid["min_samples_reduced"]
    ):
        if ms_reduced < ms_full:
            continue

        scores = []
        for rd in rounds_data:
            rn = rd["round_number"]
            if not rd.get("seeds"):
                continue

            model = NeighborhoodModel(min_samples_full=ms_full,
                                       min_samples_reduced=ms_reduced)
            for other_rd in rounds_data:
                if other_rd["round_number"] != rn:
                    model.add_training_data(other_rd)
            model.finalize()

            round_scores = []
            for si_str, seed_data in rd["seeds"].items():
                si = int(si_str)
                gt = np.array(seed_data["ground_truth"])
                ig = rd["initial_states"][si]["grid"]
                pred = model.predict_grid(rd, si)
                result = score_prediction(gt, pred, initial_grid=ig)
                round_scores.append(result["score"])
            scores.append(np.mean(round_scores))

        avg = np.mean(scores)
        results.append({
            "min_samples_full": ms_full,
            "min_samples_reduced": ms_reduced,
            "avg_score": round(float(avg), 2),
            "per_round": [round(float(s), 1) for s in scores],
        })

        if avg > best_score:
            best_score = avg
            best_params = (ms_full, ms_reduced)

        log(f"  full={ms_full:>2}, reduced={ms_reduced:>2}: avg={avg:.1f}")

    log(f"\n  Best: full={best_params[0]}, reduced={best_params[1]}, score={best_score:.1f}")
    return results, best_params


def grid_search_features(rounds_data):
    """Compare feature extraction variants."""
    log("Comparing feature extraction variants...")

    variants = {
        "V1_base": NeighborhoodModel,
        "V2_distance": NeighborhoodModelV2,
    }

    results = {}
    for name, ModelClass in variants.items():
        scores = []
        for rd in rounds_data:
            rn = rd["round_number"]
            if not rd.get("seeds"):
                continue

            model = ModelClass()
            for other_rd in rounds_data:
                if other_rd["round_number"] != rn:
                    model.add_training_data(other_rd)
            model.finalize()

            round_scores = []
            for si_str, seed_data in rd["seeds"].items():
                si = int(si_str)
                gt = np.array(seed_data["ground_truth"])
                ig = rd["initial_states"][si]["grid"]
                pred = model.predict_grid(rd, si)
                result = score_prediction(gt, pred, initial_grid=ig)
                round_scores.append(result["score"])
            scores.append(np.mean(round_scores))

        avg = np.mean(scores)
        results[name] = {
            "avg_score": round(float(avg), 2),
            "per_round": [round(float(s), 1) for s in scores],
        }
        log(f"  {name}: avg={avg:.1f} ({[f'{s:.0f}' for s in scores]})")

    return results


def grid_search_obs_weights(rounds_data):
    """Search for best observation blending weights."""
    log("Searching observation blending weights...")

    obs_weight_options = [0.70, 0.80, 0.85, 0.90, 0.95]
    best_score = -1
    best_w = None

    for obs_w_max in obs_weight_options:
        scores = []
        for rd in rounds_data:
            rn = rd["round_number"]
            if not rd.get("seeds"):
                continue

            model = NeighborhoodModel()
            for other_rd in rounds_data:
                if other_rd["round_number"] != rn:
                    model.add_training_data(other_rd)
            model.finalize()

            obs_data = load_real_observations(rn)

            round_scores = []
            for si_str, seed_data in rd["seeds"].items():
                si = int(si_str)
                gt = np.array(seed_data["ground_truth"])
                ig = rd["initial_states"][si]["grid"]

                obs_c, obs_t = None, None
                if obs_data and si in obs_data:
                    obs_c, obs_t = obs_data[si]

                pred = model.predict_grid_with_obs(
                    rd, si, obs_counts=obs_c, obs_total=obs_t,
                    obs_weight_max=obs_w_max
                )
                result = score_prediction(gt, pred, initial_grid=ig)
                round_scores.append(result["score"])
            scores.append(np.mean(round_scores))

        avg = np.mean(scores)
        if avg > best_score:
            best_score = avg
            best_w = obs_w_max
        log(f"  obs_weight_max={obs_w_max}: avg={avg:.1f}")

    log(f"\n  Best obs_weight_max: {best_w} (score={best_score:.1f})")
    return best_w, best_score


# ──────────────────────────────────────────────
# Full Churn Loop
# ──────────────────────────────────────────────

def run_churn(session, continuous=False):
    """Run the full improvement loop."""
    iteration = 0

    while True:
        iteration += 1
        log(f"\n{'='*60}")
        log(f"  CHURN ITERATION {iteration}")
        log(f"  {datetime.now(timezone.utc).isoformat()}")
        log(f"{'='*60}")

        # Step 1: Cache latest ground truth
        log("\n--- Step 1: Cache ground truth ---")
        rounds = session.get(f"{BASE}/astar-island/rounds").json()
        completed = [r for r in rounds if r["status"] == "completed"]
        for r in sorted(completed, key=lambda r: r["round_number"]):
            cache_round(session, r)

        rounds_data = load_cached_rounds()
        n_rounds = len(rounds_data)
        n_cells = n_rounds * 8000
        log(f"  {n_rounds} rounds cached, {n_cells} training cells")

        # Step 2: Grid search hyperparameters
        log("\n--- Step 2: Hyperparameter search ---")
        hp_results, best_hp = grid_search_hyperparams(rounds_data)

        # Step 3: Feature engineering comparison
        log("\n--- Step 3: Feature engineering ---")
        feat_results = grid_search_features(rounds_data)

        # Step 4: Observation weight search
        log("\n--- Step 4: Observation weight search ---")
        best_obs_w, best_obs_score = grid_search_obs_weights(rounds_data)

        # Step 5: Run hindsight on rounds with observation data
        log("\n--- Step 5: Hindsight analysis ---")
        from hindsight import run_hindsight
        run_hindsight(rounds_data)

        # Step 6: Save results
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "iteration": iteration,
            "rounds": n_rounds,
            "cells": n_cells,
            "best_hyperparams": {
                "min_samples_full": best_hp[0],
                "min_samples_reduced": best_hp[1],
            },
            "feature_variants": feat_results,
            "best_obs_weight": best_obs_w,
            "hyperparameter_search": hp_results,
        }

        result_path = RESULTS_DIR / f"churn_{ts}.json"
        result_path.write_text(json.dumps(result, indent=2))

        # Also save as "latest"
        latest_path = RESULTS_DIR / "churn_latest.json"
        latest_path.write_text(json.dumps(result, indent=2))
        log(f"\n  Results saved: {result_path.name}")

        # Step 7: Export best model
        log("\n--- Step 7: Export best model ---")
        best_model = NeighborhoodModel(
            min_samples_full=best_hp[0],
            min_samples_reduced=best_hp[1]
        )
        for rd in rounds_data:
            best_model.add_training_data(rd)
        best_model.finalize()
        best_model.stats()

        # Summary
        v1_score = feat_results.get("V1_base", {}).get("avg_score", 0)
        v2_score = feat_results.get("V2_distance", {}).get("avg_score", 0)
        log(f"\n{'='*60}")
        log(f"  CHURN SUMMARY (iteration {iteration})")
        log(f"  Best hyperparams: full={best_hp[0]}, reduced={best_hp[1]}")
        log(f"  V1 (base features): {v1_score}")
        log(f"  V2 (distance features): {v2_score}")
        log(f"  Best obs weight: {best_obs_w}")
        log(f"  Winner: {'V2_distance' if v2_score > v1_score else 'V1_base'}")
        log(f"{'='*60}")

        if not continuous:
            break

        # Wait 30 min before next iteration
        log("\nSleeping 30 min before next churn iteration...")
        time.sleep(1800)


def main():
    parser = argparse.ArgumentParser(description="Continuous Improvement Loop")
    parser.add_argument("--token", required=True)
    parser.add_argument("--continuous", action="store_true",
                        help="Run in continuous loop (for GCP VM)")
    parser.add_argument("--grid-search", action="store_true",
                        help="Only run hyperparameter grid search")
    parser.add_argument("--feature-search", action="store_true",
                        help="Only run feature engineering comparison")
    args = parser.parse_args()

    session = get_session(args.token)

    if args.grid_search:
        rounds_data = load_cached_rounds()
        if not rounds_data:
            log("Cache ground truth first")
            return
        grid_search_hyperparams(rounds_data)
        return

    if args.feature_search:
        rounds_data = load_cached_rounds()
        if not rounds_data:
            log("Cache ground truth first")
            return
        grid_search_features(rounds_data)
        return

    run_churn(session, continuous=args.continuous)


if __name__ == "__main__":
    main()
