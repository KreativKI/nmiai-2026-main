#!/usr/bin/env python3
"""
Learned Neighborhood Transition Model for Astar Island.

Instead of hand-crafted rules (near/far settlement binary), this learns
transition distributions from ALL ground truth data grouped by actual
neighborhood configuration.

48,000+ labeled transitions -> lookup table with hierarchical smoothing.

Usage:
  # Train and save model
  python learned_model.py --train

  # Backtest against hand-crafted model
  python learned_model.py --backtest

  # Export for use in astar_v6
  python learned_model.py --export
"""

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    PredictionModel, load_cached_rounds, score_prediction,
    load_real_observations,
    TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, CLASS_NAMES, PROB_FLOOR,
)

DATA_DIR = Path(__file__).parent / "data"
MODEL_DIR = DATA_DIR / "learned_model"


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


# ──────────────────────────────────────────────
# Feature Extraction
# ──────────────────────────────────────────────

def extract_cell_features(grid, y, x, h, w):
    """Extract neighborhood features for one cell.

    Returns: (my_class, n_empty, n_settle, n_port, n_ruin, n_forest, n_mountain)
    """
    my_cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)
    counts = [0] * NUM_CLASSES  # [empty, settle, port, ruin, forest, mountain]

    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w:
                ncls = TERRAIN_TO_CLASS.get(int(grid[ny][nx]), 0)
                counts[ncls] += 1
            # Out-of-bounds treated as "ocean" = empty class 0
            # (edges of map are mostly ocean/mountain anyway)

    return (my_cls, tuple(counts))


def feature_key_full(my_cls, counts):
    """Full feature key: (my_class, n0, n1, n2, n3, n4, n5)."""
    return (my_cls,) + counts


def feature_key_reduced(my_cls, counts):
    """Reduced feature key: (my_class, n_dynamic, n_forest).
    n_dynamic = settlements + ports + ruins.
    """
    n_dynamic = counts[1] + counts[2] + counts[3]
    n_forest = counts[4]
    return (my_cls, n_dynamic, n_forest)


def feature_key_minimal(my_cls, counts):
    """Minimal: just (my_class, has_settlement_neighbor)."""
    has_settle = 1 if (counts[1] + counts[2]) > 0 else 0
    return (my_cls, has_settle)


# ──────────────────────────────────────────────
# Model Training
# ──────────────────────────────────────────────

class NeighborhoodModel:
    """Learned neighborhood transition model.

    Three-level hierarchical lookup:
    1. Full: (my_class, exact neighbor counts) — most specific
    2. Reduced: (my_class, n_dynamic, n_forest) — moderate generalization
    3. Minimal: (my_class, has_settlement) — fallback

    Each level stores the average ground truth distribution for that config.
    Uses the most specific level with enough training examples.
    """

    def __init__(self, min_samples_full=5, min_samples_reduced=10):
        self.min_samples_full = min_samples_full
        self.min_samples_reduced = min_samples_reduced
        self.tables = {
            "full": {},      # feature_key -> (sum_of_distributions, count)
            "reduced": {},
            "minimal": {},
        }
        self.distributions = {
            "full": {},      # feature_key -> normalized distribution
            "reduced": {},
            "minimal": {},
        }
        self.global_dist = {}  # my_class -> distribution (ultimate fallback)
        self.training_rounds = []
        self.total_cells = 0

    def add_training_data(self, round_data, exclude_round=None):
        """Add all cells from a round's ground truth to the model."""
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
                    my_cls, counts = extract_cell_features(ig, y, x, h, w)
                    gt_dist = gt[y, x]

                    # Add to all three levels
                    for level, key_fn in [
                        ("full", feature_key_full),
                        ("reduced", feature_key_reduced),
                        ("minimal", feature_key_minimal),
                    ]:
                        key = key_fn(my_cls, counts)
                        if key not in self.tables[level]:
                            self.tables[level][key] = [np.zeros(NUM_CLASSES), 0]
                        self.tables[level][key][0] += gt_dist
                        self.tables[level][key][1] += 1

                    # Global fallback
                    if my_cls not in self.global_dist:
                        self.global_dist[my_cls] = [np.zeros(NUM_CLASSES), 0]
                    self.global_dist[my_cls][0] += gt_dist
                    self.global_dist[my_cls][1] += 1

                    self.total_cells += 1

        self.training_rounds.append(rn)

    def finalize(self):
        """Normalize all distributions with probability floor."""
        for level in ["full", "reduced", "minimal"]:
            for key, (dist_sum, count) in self.tables[level].items():
                if count > 0:
                    dist = dist_sum / count
                    dist = np.maximum(dist, PROB_FLOOR)
                    dist = dist / dist.sum()
                    self.distributions[level][key] = dist

        # Global fallback
        self.global_fallback = {}
        for cls, (dist_sum, count) in self.global_dist.items():
            if count > 0:
                dist = dist_sum / count
                dist = np.maximum(dist, PROB_FLOOR)
                dist = dist / dist.sum()
                self.global_fallback[cls] = dist

    def predict_cell(self, grid, y, x, h, w):
        """Predict distribution for one cell using hierarchical lookup."""
        terrain = grid[y][x]
        if terrain in STATIC_TERRAIN:
            # Static terrain: near-certain prediction
            cls = TERRAIN_TO_CLASS.get(int(terrain), 0)
            dist = np.full(NUM_CLASSES, PROB_FLOOR)
            dist[cls] = 1.0 - (NUM_CLASSES - 1) * PROB_FLOOR
            return dist

        my_cls, counts = extract_cell_features(grid, y, x, h, w)

        # Level 1: Full neighborhood config
        key_full = feature_key_full(my_cls, counts)
        if key_full in self.distributions["full"]:
            count = self.tables["full"][key_full][1]
            if count >= self.min_samples_full:
                return self.distributions["full"][key_full].copy()

        # Level 2: Reduced config
        key_reduced = feature_key_reduced(my_cls, counts)
        if key_reduced in self.distributions["reduced"]:
            count = self.tables["reduced"][key_reduced][1]
            if count >= self.min_samples_reduced:
                return self.distributions["reduced"][key_reduced].copy()

        # Level 3: Minimal config
        key_minimal = feature_key_minimal(my_cls, counts)
        if key_minimal in self.distributions["minimal"]:
            return self.distributions["minimal"][key_minimal].copy()

        # Level 4: Global fallback
        if my_cls in self.global_fallback:
            return self.global_fallback[my_cls].copy()

        return np.full(NUM_CLASSES, 1.0 / NUM_CLASSES)

    def predict_grid(self, round_data, seed_idx):
        """Predict full 40x40x6 grid for a seed."""
        h, w = round_data["map_height"], round_data["map_width"]
        grid = round_data["initial_states"][seed_idx]["grid"]
        pred = np.zeros((h, w, NUM_CLASSES))

        for y in range(h):
            for x in range(w):
                pred[y, x] = self.predict_cell(grid, y, x, h, w)

        return pred

    def predict_grid_with_obs(self, round_data, seed_idx, obs_counts=None,
                                obs_total=None, obs_weight_max=0.90):
        """Predict with observation blending."""
        h, w = round_data["map_height"], round_data["map_width"]
        grid = round_data["initial_states"][seed_idx]["grid"]
        pred = self.predict_grid(round_data, seed_idx)

        if obs_counts is not None and obs_total is not None:
            has_obs = obs_total > 0
            if has_obs.any():
                ot_3d = obs_total[..., np.newaxis]
                empirical = obs_counts / np.maximum(ot_3d, 1)

                obs_w = np.zeros((h, w, 1))
                for y in range(h):
                    for x in range(w):
                        if obs_total[y, x] == 0:
                            continue
                        n = obs_total[y, x]
                        cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)
                        if cls in (1, 2, 3):
                            obs_w[y, x, 0] = min(obs_weight_max, 0.4 + n / 12.0)
                        elif cls == 4:
                            obs_w[y, x, 0] = min(0.4, 0.1 + n / 20.0)
                        else:
                            obs_w[y, x, 0] = min(0.35, 0.1 + n / 25.0)

                pred = np.where(
                    has_obs[..., np.newaxis],
                    obs_w * empirical + (1 - obs_w) * pred,
                    pred
                )

        pred = np.maximum(pred, PROB_FLOOR)
        pred = pred / pred.sum(axis=-1, keepdims=True)
        return pred

    def stats(self):
        """Print model statistics."""
        log(f"Training data: {self.total_cells} cells from rounds {self.training_rounds}")
        for level in ["full", "reduced", "minimal"]:
            n_keys = len(self.distributions[level])
            if self.tables[level]:
                counts = [v[1] for v in self.tables[level].values()]
                log(f"  {level}: {n_keys} configs, "
                    f"avg {np.mean(counts):.1f} samples/config, "
                    f"max {max(counts)}")


# ──────────────────────────────────────────────
# Backtest Comparison
# ──────────────────────────────────────────────

def backtest_comparison(rounds_data):
    """Compare learned model vs hand-crafted model."""
    log("Running leave-one-out backtest comparison...\n")

    heuristic_model = PredictionModel({
        "near_dist_1": 0.6, "near_dist_3": 0.4, "near_dist_5": 0.2,
        "forest_bonus_per_adj": 0.0, "forest_bonus_cap": 0.0,
    })

    results = {"learned": [], "heuristic": []}

    for rd in rounds_data:
        rn = rd["round_number"]
        if not rd.get("seeds"):
            continue

        # Train learned model on all OTHER rounds (leave-one-out)
        learned = NeighborhoodModel()
        for other_rd in rounds_data:
            if other_rd["round_number"] != rn:
                learned.add_training_data(other_rd)
        learned.finalize()

        # Build heuristic transitions (also leave-one-out)
        hist_trans = heuristic_model.build_transitions(rounds_data, exclude_round=rn)

        # Load observations
        obs_data = load_real_observations(rn)

        learned_scores = []
        heuristic_scores = []

        for si_str, seed_data in rd["seeds"].items():
            si = int(si_str)
            gt = np.array(seed_data["ground_truth"])
            ig = rd["initial_states"][si]["grid"]

            obs_c, obs_t = None, None
            if obs_data and si in obs_data:
                obs_c, obs_t = obs_data[si]

            # Learned model prediction
            if obs_c is not None:
                pred_learned = learned.predict_grid_with_obs(rd, si, obs_c, obs_t)
            else:
                pred_learned = learned.predict_grid(rd, si)
            score_l = score_prediction(gt, pred_learned, initial_grid=ig)
            learned_scores.append(score_l["score"])

            # Heuristic model prediction
            pred_heuristic = heuristic_model.predict_seed(
                rd, si, hist_trans, hist_trans,
                obs_counts=obs_c, obs_total=obs_t
            )
            score_h = score_prediction(gt, pred_heuristic, initial_grid=ig)
            heuristic_scores.append(score_h["score"])

        avg_l = np.mean(learned_scores)
        avg_h = np.mean(heuristic_scores)
        delta = avg_l - avg_h
        sign = "+" if delta >= 0 else ""

        results["learned"].append(avg_l)
        results["heuristic"].append(avg_h)

        log(f"R{rn}: learned={avg_l:.1f}  heuristic={avg_h:.1f}  delta={sign}{delta:.1f}")

        # Per-class breakdown for learned model (first seed)
        si0 = int(list(rd["seeds"].keys())[0])
        gt0 = np.array(rd["seeds"][str(si0)]["ground_truth"])
        ig0 = rd["initial_states"][si0]["grid"]
        pred_l0 = learned.predict_grid(rd, si0)
        score_detail = score_prediction(gt0, pred_l0, initial_grid=ig0)
        if "per_class" in score_detail:
            for cls_name in ["Settlement", "Port", "Empty", "Forest"]:
                if cls_name in score_detail["per_class"]:
                    c = score_detail["per_class"][cls_name]
                    log(f"    {cls_name}: KL={c['weighted_kl']:.3f} score={c['score']:.1f}")

    # Summary
    avg_learned = np.mean(results["learned"])
    avg_heuristic = np.mean(results["heuristic"])
    delta = avg_learned - avg_heuristic
    sign = "+" if delta >= 0 else ""

    log(f"\nSUMMARY:")
    log(f"  Learned model:    avg={avg_learned:.1f}")
    log(f"  Heuristic model:  avg={avg_heuristic:.1f}")
    log(f"  Delta:            {sign}{delta:.1f}")
    log(f"  Best learned:     {max(results['learned']):.1f}")
    log(f"  Best heuristic:   {max(results['heuristic']):.1f}")

    return results


# ──────────────────────────────────────────────
# Export for v6
# ──────────────────────────────────────────────

def export_model(rounds_data):
    """Train on ALL rounds and export lookup tables as numpy arrays."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    model = NeighborhoodModel()
    for rd in rounds_data:
        model.add_training_data(rd)
    model.finalize()
    model.stats()

    # Save distributions as JSON for portability
    export = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "training_rounds": model.training_rounds,
        "total_cells": model.total_cells,
        "min_samples_full": model.min_samples_full,
        "min_samples_reduced": model.min_samples_reduced,
    }

    for level in ["full", "reduced", "minimal"]:
        level_data = {}
        for key, dist in model.distributions[level].items():
            count = model.tables[level][key][1]
            level_data[str(key)] = {
                "dist": dist.tolist(),
                "count": int(count),
            }
        export[level] = level_data

    export["global"] = {}
    for cls, dist in model.global_fallback.items():
        export["global"][str(cls)] = dist.tolist()

    export_path = MODEL_DIR / "neighborhood_model.json"
    export_path.write_text(json.dumps(export))
    log(f"Exported to {export_path} ({len(export['full'])} full configs, "
        f"{len(export['reduced'])} reduced, {len(export['minimal'])} minimal)")

    return model


def main():
    parser = argparse.ArgumentParser(description="Learned Neighborhood Model")
    parser.add_argument("--train", action="store_true", help="Train and show stats")
    parser.add_argument("--backtest", action="store_true", help="Compare vs heuristic")
    parser.add_argument("--export", action="store_true", help="Export model for v6")
    args = parser.parse_args()

    rounds_data = load_cached_rounds()
    if not rounds_data:
        log("No cached data. Run backtest.py --cache first.")
        return

    if args.train or (not args.backtest and not args.export):
        model = NeighborhoodModel()
        for rd in rounds_data:
            model.add_training_data(rd)
        model.finalize()
        model.stats()

    if args.backtest:
        backtest_comparison(rounds_data)

    if args.export:
        export_model(rounds_data)


if __name__ == "__main__":
    main()
