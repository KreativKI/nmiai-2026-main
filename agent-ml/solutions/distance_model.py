#!/usr/bin/env python3
"""
Distance-Based Prediction Model for Astar Island.

Uses hidden rules discovered from ground truth analysis:
- Settlement probability decays with Manhattan distance from initial settlements
- Round regime detection (death/quiet/growth) from observations
- Forest consumption by adjacent settlements
- Port = coastal only
- Ruin = background noise

This model is designed to work well on ALL seeds, not just the observed one.
The key insight: distance maps are computable from the initial grid (free, no queries needed).

Usage:
  python distance_model.py --backtest          # Compare vs V2 model
  python distance_model.py --backtest --round 4  # Test specific round
"""

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    load_cached_rounds, score_prediction, load_real_observations,
    TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, CLASS_NAMES, PROB_FLOOR,
)

DATA_DIR = Path(__file__).parent / "data"


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def compute_distance_map(grid, h, w):
    """Compute Manhattan distance from each cell to nearest initial settlement/port."""
    dist = np.full((h, w), 999, dtype=np.float32)
    # Find all initial settlements and ports
    settle_cells = []
    for y in range(h):
        for x in range(w):
            cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)
            if cls in (1, 2):  # settlement, port
                settle_cells.append((y, x))
                dist[y, x] = 0

    # BFS to compute Manhattan distance
    from collections import deque
    queue = deque(settle_cells)
    visited = set((y, x) for y, x in settle_cells)
    while queue:
        y, x = queue.popleft()
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in visited:
                if grid[ny][nx] not in STATIC_TERRAIN:
                    dist[ny, nx] = dist[y, x] + 1
                    visited.add((ny, nx))
                    queue.append((ny, nx))
    return dist


def compute_ocean_adjacency(grid, h, w):
    """For each cell, count how many ocean (terrain=10) neighbors it has."""
    adj = np.zeros((h, w), dtype=int)
    for y in range(h):
        for x in range(w):
            count = 0
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if (dy, dx) == (0, 0):
                        continue
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w:
                        if int(grid[ny][nx]) == 10:
                            count += 1
            adj[y, x] = count
    return adj


def compute_mountain_adjacency(grid, h, w):
    """For each cell, count how many mountain neighbors it has."""
    adj = np.zeros((h, w), dtype=int)
    for y in range(h):
        for x in range(w):
            count = 0
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if (dy, dx) == (0, 0):
                        continue
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w:
                        if int(grid[ny][nx]) == 5:
                            count += 1
            adj[y, x] = count
    return adj


def compute_settlement_adjacency(grid, h, w):
    """For each cell, count how many settlement/port neighbors it has."""
    adj = np.zeros((h, w), dtype=int)
    for y in range(h):
        for x in range(w):
            count = 0
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if (dy, dx) == (0, 0):
                        continue
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w:
                        cls = TERRAIN_TO_CLASS.get(int(grid[ny][nx]), 0)
                        if cls in (1, 2):
                            count += 1
            adj[y, x] = count
    return adj


class DistanceModel:
    """Learns settlement probability as a function of distance, per round regime."""

    def __init__(self):
        # Learned distance curves: distance -> [prob_per_class]
        # Indexed by (initial_terrain_class, distance_bucket)
        self.distance_curves = {}
        self.regime_curves = {"death": {}, "quiet": {}, "growth": {}}
        self.training_data = []  # list of (round_number, round_data)
        self.mountain_effect = {}  # mountain_adj_count -> survival_modifier
        self.forest_consumption = {}  # settle_adj_count -> forest_survival

    def add_training_data(self, round_data):
        """Add one round's ground truth for learning."""
        self.training_data.append(round_data)

    def _classify_regime(self, round_data):
        """Classify a round as death/quiet/growth from ground truth."""
        total_initial_sp = 0
        total_final_sp = 0
        for si_str, seed_data in round_data.get("seeds", {}).items():
            gt = np.array(seed_data["ground_truth"])
            ig = round_data["initial_states"][int(si_str)]["grid"]
            h, w = round_data["map_height"], round_data["map_width"]
            for y in range(h):
                for x in range(w):
                    cls = TERRAIN_TO_CLASS.get(int(ig[y][x]), 0)
                    if cls in (1, 2):
                        total_initial_sp += 1
                        total_final_sp += gt[y, x, 1] + gt[y, x, 2]
        if total_initial_sp == 0:
            return "quiet"
        ratio = total_final_sp / total_initial_sp
        if ratio < 0.1:
            return "death"
        elif ratio > 1.5:
            return "growth"
        else:
            return "quiet"

    def _detect_regime_from_obs(self, round_data, seed_idx, obs_counts, obs_total):
        """Detect round regime from observations on one seed."""
        if obs_total is None or obs_total.sum() == 0:
            return "quiet"  # default assumption

        ig = round_data["initial_states"][seed_idx]["grid"]
        h, w = round_data["map_height"], round_data["map_width"]

        # Count initial settlements that we observed
        initial_settlements = 0
        survived = 0
        new_settlements = 0

        for y in range(h):
            for x in range(w):
                if obs_total[y, x] == 0:
                    continue
                cls = TERRAIN_TO_CLASS.get(int(ig[y][x]), 0)
                if cls in (1, 2):
                    initial_settlements += 1
                    # Check if settlement survived in observations
                    if obs_counts is not None:
                        sp_obs = obs_counts[y, x, 1] + obs_counts[y, x, 2]
                        if sp_obs / obs_total[y, x] > 0.3:
                            survived += 1
                else:
                    # Non-settlement cell: check if new settlement appeared
                    if obs_counts is not None:
                        sp_obs = obs_counts[y, x, 1] + obs_counts[y, x, 2]
                        if sp_obs / obs_total[y, x] > 0.3:
                            new_settlements += 1

        if initial_settlements == 0:
            return "quiet"

        survival_rate = survived / initial_settlements
        growth = new_settlements / max(1, initial_settlements)

        if survival_rate < 0.1:
            return "death"
        elif growth > 0.5:
            return "growth"
        else:
            return "quiet"

    def finalize(self):
        """Learn distance curves from training data."""
        # Collect: for each (regime, initial_cls, distance_bucket) -> list of gt distributions
        max_dist = 20
        curve_data = {}  # (regime, init_cls, dist_bucket) -> list of gt_dist

        for rd in self.training_data:
            rn = rd["round_number"]
            if not rd.get("seeds"):
                continue
            regime = self._classify_regime(rd)
            h, w = rd["map_height"], rd["map_width"]

            for si_str, seed_data in rd["seeds"].items():
                si = int(si_str)
                gt = np.array(seed_data["ground_truth"])
                ig = rd["initial_states"][si]["grid"]

                dist_map = compute_distance_map(ig, h, w)
                mtn_adj = compute_mountain_adjacency(ig, h, w)
                settle_adj = compute_settlement_adjacency(ig, h, w)

                for y in range(h):
                    for x in range(w):
                        terrain = ig[y][x]
                        if terrain in STATIC_TERRAIN:
                            continue
                        cls = TERRAIN_TO_CLASS.get(int(terrain), 0)
                        d = min(int(dist_map[y, x]), max_dist)

                        key = (regime, cls, d)
                        if key not in curve_data:
                            curve_data[key] = []
                        curve_data[key].append(gt[y, x])

                        # Mountain effect on settlements
                        if cls in (1, 2):
                            ma = int(mtn_adj[y, x])
                            mkey = (regime, ma)
                            if mkey not in self.mountain_effect:
                                self.mountain_effect[mkey] = []
                            self.mountain_effect[mkey].append(gt[y, x, 1] + gt[y, x, 2])

                        # Forest consumption
                        if cls == 4:
                            sa = min(int(settle_adj[y, x]), 3)
                            fkey = (regime, sa)
                            if fkey not in self.forest_consumption:
                                self.forest_consumption[fkey] = []
                            self.forest_consumption[fkey].append(gt[y, x, 4])

        # Average the curves
        for key, dists in curve_data.items():
            regime, cls, d = key
            avg_dist = np.mean(dists, axis=0)
            if regime not in self.regime_curves:
                self.regime_curves[regime] = {}
            self.regime_curves[regime][(cls, d)] = avg_dist

        # Average mountain effect
        mtn_avg = {}
        for key, vals in self.mountain_effect.items():
            mtn_avg[key] = np.mean(vals)
        self.mountain_effect = mtn_avg

        # Average forest consumption
        fc_avg = {}
        for key, vals in self.forest_consumption.items():
            fc_avg[key] = np.mean(vals)
        self.forest_consumption = fc_avg

        log(f"  Distance model: {len(curve_data)} curve points, "
            f"regimes: {set(k[0] for k in curve_data.keys())}")

    def predict_grid(self, round_data, seed_idx, regime=None,
                     obs_counts=None, obs_total=None):
        """Predict 40x40x6 probability tensor using distance-based model."""
        h, w = round_data["map_height"], round_data["map_width"]
        ig = round_data["initial_states"][seed_idx]["grid"]

        # Detect regime
        if regime is None:
            if obs_counts is not None:
                regime = self._detect_regime_from_obs(
                    round_data, seed_idx, obs_counts, obs_total)
            else:
                regime = "quiet"  # conservative default

        dist_map = compute_distance_map(ig, h, w)
        ocean_adj = compute_ocean_adjacency(ig, h, w)
        mtn_adj = compute_mountain_adjacency(ig, h, w)
        settle_adj = compute_settlement_adjacency(ig, h, w)

        pred = np.zeros((h, w, NUM_CLASSES))

        for y in range(h):
            for x in range(w):
                terrain = ig[y][x]

                # Static terrain
                if terrain in STATIC_TERRAIN:
                    if int(terrain) == 5:
                        pred[y, x, 5] = 0.98
                    else:  # ocean
                        pred[y, x, 0] = 0.98
                    pred[y, x] = np.maximum(pred[y, x], PROB_FLOOR)
                    pred[y, x] /= pred[y, x].sum()
                    continue

                cls = TERRAIN_TO_CLASS.get(int(terrain), 0)
                d = min(int(dist_map[y, x]), 20)

                # Look up distance curve for this regime
                curves = self.regime_curves.get(regime, {})
                key = (cls, d)
                if key in curves:
                    pred[y, x] = curves[key].copy()
                else:
                    # Fallback: try broader distance
                    found = False
                    for dd in range(d - 1, -1, -1):
                        if (cls, dd) in curves:
                            pred[y, x] = curves[(cls, dd)].copy()
                            found = True
                            break
                    if not found:
                        # Global fallback for this regime and class
                        fallbacks = [v for (c, dd), v in curves.items() if c == cls]
                        if fallbacks:
                            pred[y, x] = np.mean(fallbacks, axis=0)
                        else:
                            pred[y, x] = np.full(NUM_CLASSES, 1.0 / NUM_CLASSES)

                # Apply port constraint: zero port probability for non-coastal cells
                if ocean_adj[y, x] == 0:
                    port_prob = pred[y, x, 2]
                    pred[y, x, 2] = 0.0
                    # Redistribute to other classes
                    if pred[y, x].sum() > 0:
                        pred[y, x] /= pred[y, x].sum()

                # Apply mountain death effect on settlements
                if cls in (1, 2) and mtn_adj[y, x] >= 2:
                    mkey = (regime, int(mtn_adj[y, x]))
                    mkey_base = (regime, 0)
                    if mkey in self.mountain_effect and mkey_base in self.mountain_effect:
                        base_surv = self.mountain_effect[mkey_base]
                        mtn_surv = self.mountain_effect[mkey]
                        if base_surv > 0:
                            factor = mtn_surv / base_surv
                            pred[y, x, 1] *= factor
                            pred[y, x, 2] *= factor

        # Blend with observations (Dirichlet-Categorical)
        if obs_counts is not None and obs_total is not None:
            prior_strength = 12
            for y in range(h):
                for x in range(w):
                    if obs_total[y, x] == 0:
                        continue
                    prior = pred[y, x] * prior_strength
                    posterior = prior + obs_counts[y, x]
                    pred[y, x] = posterior / posterior.sum()

        # Floor and normalize
        pred = np.maximum(pred, PROB_FLOOR)
        pred = pred / pred.sum(axis=-1, keepdims=True)

        return pred


def backtest_distance_model(rounds_data, with_obs=True):
    """Backtest the distance model vs V2 neighborhood model."""
    from churn import NeighborhoodModelV2

    log("Backtesting distance model vs V2 (leave-one-out)...")

    dist_scores = []
    v2_scores = []

    for rd in rounds_data:
        rn = rd["round_number"]
        if not rd.get("seeds"):
            continue

        # Build distance model (leave-one-out)
        dm = DistanceModel()
        for other_rd in rounds_data:
            if other_rd["round_number"] != rn and other_rd.get("seeds"):
                dm.add_training_data(other_rd)
        dm.finalize()

        # Build V2 model (leave-one-out)
        v2 = NeighborhoodModelV2()
        for other_rd in rounds_data:
            if other_rd["round_number"] != rn and other_rd.get("seeds"):
                v2.add_training_data(other_rd)
        v2.finalize()

        obs_data = load_real_observations(rn) if with_obs else {}

        round_dist = []
        round_v2 = []

        for si_str, seed_data in rd["seeds"].items():
            si = int(si_str)
            gt = np.array(seed_data["ground_truth"])
            ig = rd["initial_states"][si]["grid"]

            obs_c, obs_t = None, None
            if obs_data and si in obs_data:
                obs_c, obs_t = obs_data[si]

            # Distance model prediction
            pred_dm = dm.predict_grid(rd, si, obs_counts=obs_c, obs_total=obs_t)
            # Apply post-processing
            pred_dm = pred_dm ** (1.0 / 1.12)
            pred_dm = np.maximum(pred_dm, PROB_FLOOR)
            pred_dm = pred_dm / pred_dm.sum(axis=-1, keepdims=True)
            result_dm = score_prediction(gt, pred_dm, initial_grid=ig)
            round_dist.append(result_dm["score"])

            # V2 model prediction
            pred_v2 = v2.predict_grid_with_obs(rd, si, obs_counts=obs_c, obs_total=obs_t,
                                                obs_weight_max=0.70)
            pred_v2 = pred_v2 ** (1.0 / 1.12)
            pred_v2 = np.maximum(pred_v2, PROB_FLOOR)
            pred_v2 = pred_v2 / pred_v2.sum(axis=-1, keepdims=True)
            result_v2 = score_prediction(gt, pred_v2, initial_grid=ig)
            round_v2.append(result_v2["score"])

        avg_dm = np.mean(round_dist)
        avg_v2 = np.mean(round_v2)
        delta = avg_dm - avg_v2
        sign = "+" if delta >= 0 else ""
        log(f"  R{rn}: dist={avg_dm:.1f}  v2={avg_v2:.1f}  delta={sign}{delta:.1f}")

        dist_scores.append(avg_dm)
        v2_scores.append(avg_v2)

    overall_dm = np.mean(dist_scores)
    overall_v2 = np.mean(v2_scores)
    delta = overall_dm - overall_v2
    sign = "+" if delta >= 0 else ""
    log(f"\n  OVERALL: dist={overall_dm:.1f}  v2={overall_v2:.1f}  delta={sign}{delta:.1f}")

    return overall_dm, overall_v2


def main():
    parser = argparse.ArgumentParser(description="Distance-Based Prediction Model")
    parser.add_argument("--backtest", action="store_true")
    parser.add_argument("--round", type=int, default=None)
    parser.add_argument("--with-obs", action="store_true", default=True)
    args = parser.parse_args()

    rounds_data = load_cached_rounds()
    if not rounds_data:
        log("No cached data.")
        return

    if args.round:
        test_rounds = [rd for rd in rounds_data if rd["round_number"] == args.round]
    else:
        test_rounds = rounds_data

    if args.backtest:
        backtest_distance_model(test_rounds if not args.round else rounds_data,
                                with_obs=args.with_obs)


if __name__ == "__main__":
    main()
