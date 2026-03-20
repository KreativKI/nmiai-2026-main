#!/usr/bin/env python3
"""
Regime-Specific Transition Model for Astar Island.

Instead of one global model for all rounds, trains separate models for:
- death: settlement survival < 15%, minimal new growth
- stable: moderate survival (15-60%)
- growth: high survival or explosive new settlement formation

Usage:
  python regime_model.py                    # Backtest: regime vs global
  python regime_model.py --classify         # Show regime classification for all rounds
"""

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    load_cached_rounds, score_prediction,
    TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, PROB_FLOOR, CLASS_NAMES,
)

DATA_DIR = Path(__file__).parent / "data"


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def extract_features(grid, y, x, h, w):
    """Extract neighborhood features for a cell."""
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

    return my_cls, tuple(counts), dist_bucket, settle_r3


def key_full(my_cls, counts, dist, sr3):
    return (my_cls,) + counts + (dist, sr3)


def key_reduced(my_cls, counts, dist, sr3):
    n_dyn = counts[1] + counts[2] + counts[3]
    n_for = counts[4]
    return (my_cls, n_dyn, n_for, dist)


def key_minimal(my_cls, counts, dist, sr3):
    has_s = 1 if (counts[1] + counts[2]) > 0 else 0
    return (my_cls, has_s, min(dist, 3))


def classify_round(round_data):
    """Classify a round's regime from ground truth."""
    h, w = round_data["map_height"], round_data["map_width"]
    total_init = 0
    total_survived = 0
    total_new = 0

    for si_str, seed_data in round_data.get("seeds", {}).items():
        si = int(si_str)
        ig = round_data["initial_states"][si]["grid"]
        gt = np.array(seed_data["ground_truth"])

        for y in range(h):
            for x in range(w):
                init_cls = TERRAIN_TO_CLASS.get(int(ig[y][x]), 0)
                if int(ig[y][x]) in STATIC_TERRAIN:
                    continue
                final_cls = gt[y, x].argmax()

                if init_cls in (1, 2):
                    total_init += 1
                    if final_cls in (1, 2):
                        total_survived += 1
                elif final_cls in (1, 2):
                    total_new += 1

    survival_rate = total_survived / max(1, total_init)
    growth_rate = total_new / max(1, total_init)

    if survival_rate < 0.15 and growth_rate < 0.2:
        regime = "death"
    elif survival_rate > 0.60 or growth_rate > 0.5:
        regime = "growth"
    else:
        regime = "stable"

    return regime, {
        "survival_rate": round(float(survival_rate), 3),
        "growth_rate": round(float(growth_rate), 3),
        "init_settlements": total_init,
        "survived": total_survived,
        "new_settlements": total_new,
    }


class RegimeModel:
    """Regime-specific transition model with hierarchical feature lookup."""

    LEVELS = ["full", "reduced", "minimal"]
    KEY_FNS = {"full": key_full, "reduced": key_reduced, "minimal": key_minimal}

    def __init__(self, min_samples_full=5, min_samples_reduced=10):
        self.regime_tables = {}  # regime -> level -> key -> [sum_dist, count]
        self.regime_global = {}  # regime -> cls -> [sum_dist, count]
        self.overall_global = {}  # cls -> [sum_dist, count]
        self.regime_dists = {}  # regime -> level -> key -> normalized dist
        self.regime_global_dist = {}
        self.overall_global_dist = {}
        self.min_full = min_samples_full
        self.min_reduced = min_samples_reduced
        self.training_info = {}

    def add_training_data(self, round_data, regime=None):
        """Add training data for one round. Auto-classifies if regime is None."""
        if regime is None:
            regime, _ = classify_round(round_data)

        rn = round_data["round_number"]
        h, w = round_data["map_height"], round_data["map_width"]

        if regime not in self.regime_tables:
            self.regime_tables[regime] = {lvl: {} for lvl in self.LEVELS}
            self.regime_global[regime] = {}

        tables = self.regime_tables[regime]
        rglobal = self.regime_global[regime]

        cells_added = 0
        for si_str, seed_data in round_data.get("seeds", {}).items():
            si = int(si_str)
            ig = round_data["initial_states"][si]["grid"]
            gt = np.array(seed_data["ground_truth"])

            for y in range(h):
                for x in range(w):
                    if int(ig[y][x]) in STATIC_TERRAIN:
                        continue
                    my_cls, counts, dist, sr3 = extract_features(ig, y, x, h, w)
                    gt_dist = gt[y, x]

                    for lvl, kfn in self.KEY_FNS.items():
                        key = kfn(my_cls, counts, dist, sr3)
                        if key not in tables[lvl]:
                            tables[lvl][key] = [np.zeros(NUM_CLASSES), 0]
                        tables[lvl][key][0] += gt_dist
                        tables[lvl][key][1] += 1

                    if my_cls not in rglobal:
                        rglobal[my_cls] = [np.zeros(NUM_CLASSES), 0]
                    rglobal[my_cls][0] += gt_dist
                    rglobal[my_cls][1] += 1

                    if my_cls not in self.overall_global:
                        self.overall_global[my_cls] = [np.zeros(NUM_CLASSES), 0]
                    self.overall_global[my_cls][0] += gt_dist
                    self.overall_global[my_cls][1] += 1

                    cells_added += 1

        self.training_info[rn] = {"regime": regime, "cells": cells_added}

    def finalize(self):
        """Normalize all tables into distributions."""
        for regime in self.regime_tables:
            self.regime_dists[regime] = {}
            for lvl in self.LEVELS:
                self.regime_dists[regime][lvl] = {}
                for key, (s, c) in self.regime_tables[regime][lvl].items():
                    dist = s / c
                    dist = np.maximum(dist, PROB_FLOOR)
                    dist /= dist.sum()
                    self.regime_dists[regime][lvl][key] = dist

            self.regime_global_dist[regime] = {}
            for cls, (s, c) in self.regime_global[regime].items():
                dist = s / c
                dist = np.maximum(dist, PROB_FLOOR)
                dist /= dist.sum()
                self.regime_global_dist[regime][cls] = dist

        self.overall_global_dist = {}
        for cls, (s, c) in self.overall_global.items():
            dist = s / c
            dist = np.maximum(dist, PROB_FLOOR)
            dist /= dist.sum()
            self.overall_global_dist[cls] = dist

    def predict_cell(self, grid, y, x, h, w, regime="stable"):
        """Predict one cell using regime-specific hierarchical lookup."""
        terrain = grid[y][x]
        if terrain in STATIC_TERRAIN:
            cls = TERRAIN_TO_CLASS.get(int(terrain), 0)
            dist = np.full(NUM_CLASSES, PROB_FLOOR)
            dist[cls] = 1.0 - (NUM_CLASSES - 1) * PROB_FLOOR
            return dist

        my_cls, counts, dist_b, sr3 = extract_features(grid, y, x, h, w)

        # Try regime-specific tables first
        if regime in self.regime_dists:
            rdist = self.regime_dists[regime]

            k = key_full(my_cls, counts, dist_b, sr3)
            if k in rdist["full"]:
                c = self.regime_tables[regime]["full"][k][1]
                if c >= self.min_full:
                    return rdist["full"][k].copy()

            k = key_reduced(my_cls, counts, dist_b, sr3)
            if k in rdist["reduced"]:
                c = self.regime_tables[regime]["reduced"][k][1]
                if c >= self.min_reduced:
                    return rdist["reduced"][k].copy()

            k = key_minimal(my_cls, counts, dist_b, sr3)
            if k in rdist["minimal"]:
                return rdist["minimal"][k].copy()

            if regime in self.regime_global_dist and my_cls in self.regime_global_dist[regime]:
                return self.regime_global_dist[regime][my_cls].copy()

        # Fall back to overall global
        if my_cls in self.overall_global_dist:
            return self.overall_global_dist[my_cls].copy()

        return np.full(NUM_CLASSES, 1.0 / NUM_CLASSES)

    def predict_grid(self, detail, seed_idx, regime="stable"):
        """Predict full grid for one seed."""
        h, w = detail["map_height"], detail["map_width"]
        grid = detail["initial_states"][seed_idx]["grid"]
        pred = np.zeros((h, w, NUM_CLASSES))
        for y in range(h):
            for x in range(w):
                pred[y, x] = self.predict_cell(grid, y, x, h, w, regime)
        return pred

    def stats(self):
        """Print training statistics."""
        for regime in sorted(self.regime_tables.keys()):
            tables = self.regime_tables[regime]
            rounds_in = [rn for rn, info in self.training_info.items() if info["regime"] == regime]
            total = sum(info["cells"] for rn, info in self.training_info.items() if info["regime"] == regime)
            log(f"  {regime}: {len(rounds_in)} rounds, {total} cells, "
                f"full={len(tables['full'])} reduced={len(tables['reduced'])} minimal={len(tables['minimal'])}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--classify", action="store_true", help="Show regime classification only")
    args = parser.parse_args()

    rounds_data = load_cached_rounds()
    log(f"Loaded {len(rounds_data)} cached rounds")

    # Classify all rounds
    regimes = {}
    for rd in rounds_data:
        rn = rd["round_number"]
        regime, info = classify_round(rd)
        regimes[rn] = {"regime": regime, **info}

    if args.classify:
        for rn in sorted(regimes.keys()):
            r = regimes[rn]
            log(f"R{rn}: {r['regime']:>6}  survival={r['survival_rate']:.1%}  growth={r['growth_rate']:.1%}  "
                f"init={r['init_settlements']}  survived={r['survived']}  new={r['new_settlements']}")
        return

    # Backtest: regime-specific vs global
    log("\n=== BACKTEST: REGIME-SPECIFIC vs GLOBAL ===")

    from scipy.ndimage import gaussian_filter
    from churn import NeighborhoodModelV2

    results = {"regime_assignments": {}, "per_round": {}, "per_regime_avg": {}, "overall": {}}

    regime_scores = []
    global_scores = []

    for rd in rounds_data:
        rn = rd["round_number"]
        if not rd.get("seeds"):
            continue

        regime = regimes[rn]["regime"]
        results["regime_assignments"][str(rn)] = regime

        # Train regime model on other rounds
        rmodel = RegimeModel()
        for other in rounds_data:
            if other["round_number"] != rn:
                rmodel.add_training_data(other)
        rmodel.finalize()

        # Train global model on other rounds
        gmodel = NeighborhoodModelV2()
        for other in rounds_data:
            if other["round_number"] != rn:
                gmodel.add_training_data(other)
        gmodel.finalize()

        h, w = rd["map_height"], rd["map_width"]
        r_round_scores = []
        g_round_scores = []

        for si_str, seed_data in rd["seeds"].items():
            si = int(si_str)
            gt = np.array(seed_data["ground_truth"])
            ig = rd["initial_states"][si]["grid"]

            # Regime model prediction
            r_pred = rmodel.predict_grid(rd, si, regime=regime)
            r_pred = np.maximum(r_pred, PROB_FLOOR)
            r_pred = r_pred / r_pred.sum(axis=-1, keepdims=True)
            r_result = score_prediction(gt, r_pred, initial_grid=ig)
            r_round_scores.append(r_result["score"])

            # Global model prediction
            g_pred = gmodel.predict_grid(rd, si)
            g_pred = np.maximum(g_pred, PROB_FLOOR)
            g_pred = g_pred / g_pred.sum(axis=-1, keepdims=True)
            g_result = score_prediction(gt, g_pred, initial_grid=ig)
            g_round_scores.append(g_result["score"])

        r_avg = np.mean(r_round_scores)
        g_avg = np.mean(g_round_scores)
        delta = r_avg - g_avg

        regime_scores.append(r_avg)
        global_scores.append(g_avg)

        results["per_round"][str(rn)] = {
            "regime": regime,
            "regime_model_score": round(float(r_avg), 2),
            "global_model_score": round(float(g_avg), 2),
            "delta": round(float(delta), 2),
        }

        symbol = "+" if delta >= 0 else ""
        log(f"R{rn} [{regime:>6}]: regime={r_avg:.1f}  global={g_avg:.1f}  delta={symbol}{delta:.1f}")

    # Per-regime averages
    for reg in ["death", "stable", "growth"]:
        reg_rounds = [rn for rn, info in regimes.items() if info["regime"] == reg]
        if not reg_rounds:
            continue
        r_scores = [results["per_round"][str(rn)]["regime_model_score"] for rn in reg_rounds if str(rn) in results["per_round"]]
        g_scores = [results["per_round"][str(rn)]["global_model_score"] for rn in reg_rounds if str(rn) in results["per_round"]]
        if r_scores:
            results["per_regime_avg"][reg] = {
                "regime_model": round(float(np.mean(r_scores)), 2),
                "global": round(float(np.mean(g_scores)), 2),
                "delta": round(float(np.mean(r_scores) - np.mean(g_scores)), 2),
                "n_rounds": len(reg_rounds),
            }

    overall_r = np.mean(regime_scores)
    overall_g = np.mean(global_scores)
    results["overall"] = {
        "regime_model": round(float(overall_r), 2),
        "global": round(float(overall_g), 2),
        "delta": round(float(overall_r - overall_g), 2),
    }
    results["recommendation"] = "USE_REGIME_MODEL" if overall_r > overall_g else "KEEP_GLOBAL"

    log(f"\nOverall: regime={overall_r:.2f}  global={overall_g:.2f}  delta={overall_r - overall_g:+.2f}")
    log(f"Recommendation: {results['recommendation']}")

    for reg in ["death", "stable", "growth"]:
        if reg in results["per_regime_avg"]:
            r = results["per_regime_avg"][reg]
            log(f"  {reg}: regime={r['regime_model']:.1f} global={r['global']:.1f} delta={r['delta']:+.1f} ({r['n_rounds']} rounds)")

    # Save
    output_path = DATA_DIR / "regime_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    log(f"\nSaved to {output_path}")


if __name__ == "__main__":
    main()
