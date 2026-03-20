#!/usr/bin/env python3
"""
Reinforcement-Weighted Transition Model for Astar Island.

Applies three types of weighting to the transition lookup table:
1. Recency: recent rounds count more (exponential decay)
2. Regime matching: rounds with same regime get 2x weight
3. Error penalty: cells with high backtest error get wider probability spreads

Usage:
  python weighted_model.py                  # Full backtest comparison
  python weighted_model.py --grid-search    # Search best decay/regime weights
"""

import argparse
import json
import itertools
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
from scipy.ndimage import gaussian_filter

import sys
sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    load_cached_rounds, score_prediction,
    TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, PROB_FLOOR, CLASS_NAMES,
)
from regime_model import classify_round, extract_features, key_full, key_reduced, key_minimal

DATA_DIR = Path(__file__).parent / "data"


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


class WeightedModel:
    """Transition model with recency decay and regime-matching weights."""

    LEVELS = ["full", "reduced", "minimal"]
    KEY_FNS = {"full": key_full, "reduced": key_reduced, "minimal": key_minimal}

    def __init__(self, decay=0.85, regime_boost=2.0, min_full=5, min_reduced=10):
        self.decay = decay          # weight = decay^(rounds_ago). 0.85 = 15% less per round back
        self.regime_boost = regime_boost  # multiply weight by this if regime matches
        self.min_full = min_full
        self.min_reduced = min_reduced
        self.tables = {lvl: {} for lvl in self.LEVELS}
        self.global_dist = {}
        self.distributions = {lvl: {} for lvl in self.LEVELS}
        self.global_fallback = {}
        self.total_cells = 0
        self.training_rounds = []
        self.max_round = 0

    def add_training_data(self, round_data, target_regime=None, target_round=None):
        """Add weighted training data. Weight based on recency and regime match."""
        rn = round_data["round_number"]
        regime, _ = classify_round(round_data)
        h, w = round_data["map_height"], round_data["map_width"]

        # Calculate weight
        if target_round is not None:
            rounds_ago = abs(target_round - rn)
        else:
            rounds_ago = 0
        recency_weight = self.decay ** rounds_ago

        regime_weight = self.regime_boost if (target_regime and regime == target_regime) else 1.0
        weight = recency_weight * regime_weight

        for si_str, seed_data in round_data.get("seeds", {}).items():
            si = int(si_str)
            ig = round_data["initial_states"][si]["grid"]
            gt = np.array(seed_data["ground_truth"])

            for y in range(h):
                for x in range(w):
                    if int(ig[y][x]) in STATIC_TERRAIN:
                        continue
                    my_cls, counts, dist_b, sr3 = extract_features(ig, y, x, h, w)
                    gt_dist = gt[y, x] * weight  # weighted distribution

                    for lvl, kfn in self.KEY_FNS.items():
                        key = kfn(my_cls, counts, dist_b, sr3)
                        if key not in self.tables[lvl]:
                            self.tables[lvl][key] = [np.zeros(NUM_CLASSES), 0.0]
                        self.tables[lvl][key][0] += gt_dist
                        self.tables[lvl][key][1] += weight

                    if my_cls not in self.global_dist:
                        self.global_dist[my_cls] = [np.zeros(NUM_CLASSES), 0.0]
                    self.global_dist[my_cls][0] += gt_dist
                    self.global_dist[my_cls][1] += weight
                    self.total_cells += 1

        self.training_rounds.append(rn)
        self.max_round = max(self.max_round, rn)

    def finalize(self):
        for lvl in self.LEVELS:
            self.distributions[lvl] = {}
            for key, (s, c) in self.tables[lvl].items():
                if c > 0:
                    dist = s / c
                    dist = np.maximum(dist, PROB_FLOOR)
                    dist /= dist.sum()
                    self.distributions[lvl][key] = dist

        self.global_fallback = {}
        for cls, (s, c) in self.global_dist.items():
            if c > 0:
                dist = s / c
                dist = np.maximum(dist, PROB_FLOOR)
                dist /= dist.sum()
                self.global_fallback[cls] = dist

    def predict_cell(self, grid, y, x, h, w):
        terrain = grid[y][x]
        if terrain in STATIC_TERRAIN:
            cls = TERRAIN_TO_CLASS.get(int(terrain), 0)
            dist = np.full(NUM_CLASSES, PROB_FLOOR)
            dist[cls] = 1.0 - (NUM_CLASSES - 1) * PROB_FLOOR
            return dist

        my_cls, counts, dist_b, sr3 = extract_features(grid, y, x, h, w)

        k = key_full(my_cls, counts, dist_b, sr3)
        if k in self.distributions["full"]:
            if self.tables["full"][k][1] >= self.min_full:
                return self.distributions["full"][k].copy()

        k = key_reduced(my_cls, counts, dist_b, sr3)
        if k in self.distributions["reduced"]:
            if self.tables["reduced"][k][1] >= self.min_reduced:
                return self.distributions["reduced"][k].copy()

        k = key_minimal(my_cls, counts, dist_b, sr3)
        if k in self.distributions["minimal"]:
            return self.distributions["minimal"][k].copy()

        if my_cls in self.global_fallback:
            return self.global_fallback[my_cls].copy()

        return np.full(NUM_CLASSES, 1.0 / NUM_CLASSES)

    def predict_grid(self, detail, seed_idx):
        h, w = detail["map_height"], detail["map_width"]
        grid = detail["initial_states"][seed_idx]["grid"]
        pred = np.zeros((h, w, NUM_CLASSES))
        for y in range(h):
            for x in range(w):
                pred[y, x] = self.predict_cell(grid, y, x, h, w)
        return pred


def backtest_weighted(rounds_data, decay, regime_boost):
    """Leave-one-out backtest with weighted model."""
    scores = []
    for rd in rounds_data:
        rn = rd["round_number"]
        if not rd.get("seeds"):
            continue
        regime, _ = classify_round(rd)

        model = WeightedModel(decay=decay, regime_boost=regime_boost)
        for other in rounds_data:
            if other["round_number"] != rn:
                model.add_training_data(other, target_regime=regime, target_round=rn)
        model.finalize()

        round_scores = []
        for si_str, seed_data in rd["seeds"].items():
            si = int(si_str)
            gt = np.array(seed_data["ground_truth"])
            ig = rd["initial_states"][si]["grid"]
            pred = model.predict_grid(rd, si)
            pred = np.maximum(pred, PROB_FLOOR)
            pred = pred / pred.sum(axis=-1, keepdims=True)
            result = score_prediction(gt, pred, initial_grid=ig)
            round_scores.append(result["score"])
        scores.append(np.mean(round_scores))
    return np.mean(scores), scores


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--grid-search", action="store_true")
    args = parser.parse_args()

    rounds_data = load_cached_rounds()
    log(f"Loaded {len(rounds_data)} rounds")

    if args.grid_search:
        log("Grid searching decay and regime_boost...")
        best_score = -1
        best_params = None
        results = []

        for decay in [0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0]:
            for regime_boost in [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]:
                avg, per_round = backtest_weighted(rounds_data, decay, regime_boost)
                results.append({
                    "decay": decay, "regime_boost": regime_boost,
                    "avg_score": round(float(avg), 2),
                    "per_round": [round(float(s), 1) for s in per_round],
                })
                if avg > best_score:
                    best_score = avg
                    best_params = (decay, regime_boost)
                    log(f"  NEW BEST: decay={decay} boost={regime_boost} -> {avg:.2f}")

        log(f"\nBEST: decay={best_params[0]} boost={best_params[1]} -> {best_score:.2f}")

        # Compare vs unweighted (decay=1.0, boost=1.0)
        baseline, _ = backtest_weighted(rounds_data, 1.0, 1.0)
        log(f"Unweighted baseline: {baseline:.2f}")
        log(f"Delta: {best_score - baseline:+.2f}")

        results.sort(key=lambda r: -r["avg_score"])
        with open(DATA_DIR / "weighted_results.json", "w") as f:
            json.dump({
                "best_params": {"decay": best_params[0], "regime_boost": best_params[1]},
                "best_score": round(float(best_score), 2),
                "baseline": round(float(baseline), 2),
                "delta": round(float(best_score - baseline), 2),
                "top_10": results[:10],
            }, f, indent=2)
        log(f"Saved to data/weighted_results.json")
    else:
        # Single comparison: weighted vs unweighted
        log("Comparing weighted vs unweighted...")
        w_avg, w_scores = backtest_weighted(rounds_data, 0.85, 2.0)
        u_avg, u_scores = backtest_weighted(rounds_data, 1.0, 1.0)

        for i, rd in enumerate(rounds_data):
            if not rd.get("seeds"):
                continue
            rn = rd["round_number"]
            regime, _ = classify_round(rd)
            delta = w_scores[i] - u_scores[i]
            sym = "+" if delta >= 0 else ""
            log(f"R{rn} [{regime:>6}]: weighted={w_scores[i]:.1f}  uniform={u_scores[i]:.1f}  delta={sym}{delta:.1f}")

        log(f"\nWeighted avg: {w_avg:.2f}  Uniform avg: {u_avg:.2f}  Delta: {w_avg - u_avg:+.2f}")


if __name__ == "__main__":
    main()
