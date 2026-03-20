#!/usr/bin/env python3
"""
Mock Round Runner — Test v7 on old data as if it were a live round.

Picks a completed round, hides the ground truth from v7, simulates
stochastic observations, runs the full pipeline, then scores against
the real ground truth.

Usage:
  python mock_round.py                    # Random round
  python mock_round.py --round 4          # Specific round
  python mock_round.py --round 3          # Test death round detection
  python mock_round.py --all              # Run all rounds
"""

import argparse
import json
import time
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
from churn import NeighborhoodModelV2
from astar_v7 import detect_regime, compute_ocean_adjacency


DATA_DIR = Path(__file__).parent / "data"


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


class MockAPI:
    """Simulates the Astar Island API using cached ground truth."""

    def __init__(self, round_data, rng=None):
        self.rd = round_data
        self.rng = rng or np.random.default_rng()
        self.queries_used = 0
        self.queries_max = 50
        self.h = round_data["map_height"]
        self.w = round_data["map_width"]
        # Pre-load ground truth for sampling
        self.gt = {}
        for si_str, seed_data in round_data["seeds"].items():
            self.gt[int(si_str)] = np.array(seed_data["ground_truth"])

    def simulate(self, seed_idx, vx, vy, vw=15, vh=15):
        """Simulate one viewport observation by sampling from ground truth."""
        if self.queries_used >= self.queries_max:
            raise Exception("Budget exhausted!")
        self.queries_used += 1

        gt = self.gt.get(seed_idx)
        if gt is None:
            raise Exception(f"No ground truth for seed {seed_idx}")

        grid = []
        settlements = []
        for dy in range(vh):
            row = []
            for dx in range(vw):
                y, x = vy + dy, vx + dx
                if 0 <= y < self.h and 0 <= x < self.w:
                    probs = gt[y, x]
                    probs = np.maximum(probs, 1e-10)
                    probs = probs / probs.sum()
                    terrain = int(self.rng.choice(NUM_CLASSES, p=probs))
                    row.append(terrain)
                    # Generate mock settlement stats
                    if terrain == 1:
                        settlements.append({
                            "x": x, "y": y, "alive": True,
                            "population": float(self.rng.uniform(0.5, 2.0)),
                            "food": float(self.rng.uniform(0.3, 1.5)),
                            "owner_id": int(self.rng.integers(0, 20)),
                        })
                else:
                    row.append(10)  # ocean
            grid.append(row)

        return {
            "grid": grid,
            "viewport": {"x": vx, "y": vy, "w": vw, "h": vh},
            "queries_used": self.queries_used,
            "settlements": settlements,
        }


def tile_viewports(height, width, vsize=15):
    viewports = []
    for vy in range(0, height, vsize):
        for vx in range(0, width, vsize):
            vh = min(vsize, height - vy)
            vw = min(vsize, width - vx)
            viewports.append((vx, vy, vw, vh))
    return viewports


def run_mock_round(target_round, all_rounds, trial_seed=42):
    """Run the full v7 pipeline on a mock round."""
    rn = target_round["round_number"]
    h, w = target_round["map_height"], target_round["map_width"]
    seeds_count = target_round.get("seeds_count", 5)

    log(f"\n{'='*60}")
    log(f"  MOCK ROUND {rn} (weight {target_round.get('round_weight', 1.0):.4f})")
    log(f"  Using ground truth as mock API, hidden from model")
    log(f"{'='*60}")

    rng = np.random.default_rng(trial_seed)
    api = MockAPI(target_round, rng)

    # ── PHASE 1: Observe all 5 seeds ──
    log(f"\nPhase 1: Overview ALL {seeds_count} seeds (9 queries each)")
    viewports = tile_viewports(h, w, 15)
    all_obs = {}

    for seed_idx in range(seeds_count):
        if str(seed_idx) not in target_round["seeds"]:
            continue
        grid = target_round["initial_states"][seed_idx]["grid"]
        obs_counts = np.zeros((h, w, NUM_CLASSES))
        obs_total = np.zeros((h, w))

        for i, (vx, vy, vw, vh) in enumerate(viewports):
            obs = api.simulate(seed_idx, vx, vy, vw, vh)
            for dy, row in enumerate(obs["grid"]):
                for dx, terrain in enumerate(row):
                    ya, xa = vy + dy, vx + dx
                    if 0 <= ya < h and 0 <= xa < w:
                        obs_counts[ya, xa, terrain] += 1
                        obs_total[ya, xa] += 1
            log(f"  Seed {seed_idx} [{i+1}/9] ({vx},{vy}) — budget {api.queries_used}/50")

        all_obs[seed_idx] = (obs_counts, obs_total)

        # Summary
        changes = 0
        for y in range(h):
            for x in range(w):
                if obs_total[y, x] == 0:
                    continue
                initial_cls = TERRAIN_TO_CLASS.get(grid[y][x], 0)
                if obs_counts[y, x].argmax() != initial_cls:
                    changes += 1
        log(f"  Seed {seed_idx}: {changes} terrain changes observed")

    # ── REGIME DETECTION ──
    ig0 = target_round["initial_states"][0]["grid"]
    regime_info = detect_regime(all_obs[0][0], all_obs[0][1], ig0, h, w)
    log(f"\n  REGIME DETECTED: {regime_info['regime']}")
    log(f"  Settlement survival: {regime_info['survival_rate']:.0%}")
    log(f"  New settlements: {regime_info['new_settlements']}")

    # ── PHASE 2: Stack remaining queries on seed 0 ──
    remaining = api.queries_max - api.queries_used
    log(f"\nPhase 2: Stacking {remaining} queries on seed 0 high-value cells")
    if remaining > 0 and 0 in all_obs:
        obs_counts_0, obs_total_0 = all_obs[0]
        grid0 = target_round["initial_states"][0]["grid"]

        # Simple heat targeting
        heat = np.zeros((h, w))
        for y in range(h):
            for x in range(w):
                if grid0[y][x] in STATIC_TERRAIN:
                    continue
                cls = TERRAIN_TO_CLASS.get(int(grid0[y][x]), 0)
                if cls in (1, 2):
                    heat[y, x] += 5

        used = np.zeros((h, w), dtype=bool)
        for q in range(remaining):
            best_score = -1
            best_vp = None
            for vy in range(0, max(1, h - 14), 3):
                for vx in range(0, max(1, w - 14), 3):
                    region = heat[vy:vy+15, vx:vx+15]
                    region_used = used[vy:vy+15, vx:vx+15]
                    score = region[~region_used].sum() if (~region_used).any() else 0
                    if score > best_score:
                        best_score = score
                        best_vp = (vx, vy, 15, 15)
            if best_vp is None:
                break
            vx, vy, vw, vh = best_vp
            obs = api.simulate(0, vx, vy, vw, vh)
            for dy, row in enumerate(obs["grid"]):
                for dx, terrain in enumerate(row):
                    ya, xa = vy + dy, vx + dx
                    if 0 <= ya < h and 0 <= xa < w:
                        obs_counts_0[ya, xa, terrain] += 1
                        obs_total_0[ya, xa] += 1
            used[vy:vy+15, vx:vx+15] = True
            log(f"  [{q+1}/{remaining}] ({vx},{vy}) — budget {api.queries_used}/50")
        all_obs[0] = (obs_counts_0, obs_total_0)

    # ── PHASE 3: Build predictions ──
    log(f"\nPhase 3: Building predictions (V2 model + calibration)")

    # Train V2 model (leave-one-out: exclude this round)
    v2 = NeighborhoodModelV2()
    for other_rd in all_rounds:
        if other_rd["round_number"] != rn and other_rd.get("seeds"):
            v2.add_training_data(other_rd)
    v2.finalize()
    log(f"  Trained on {v2.total_cells} cells from {len(all_rounds)-1} rounds")

    # Predict and score each seed
    seed_scores = []
    for seed_idx in range(seeds_count):
        si_str = str(seed_idx)
        if si_str not in target_round["seeds"]:
            continue
        grid = target_round["initial_states"][seed_idx]["grid"]
        gt = np.array(target_round["seeds"][si_str]["ground_truth"])

        obs_c = all_obs[seed_idx][0] if seed_idx in all_obs else None
        obs_t = all_obs[seed_idx][1] if seed_idx in all_obs else None

        pred = v2.predict_grid_with_obs(
            target_round, seed_idx,
            obs_counts=obs_c, obs_total=obs_t,
            prior_strength=12.0)

        # DEATH CALIBRATION
        if regime_info["regime"] == "death":
            for y in range(h):
                for x in range(w):
                    if grid[y][x] in STATIC_TERRAIN:
                        continue
                    cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)
                    if cls in (1, 2):
                        pred[y, x] = [0.65, 0.02, 0.01, 0.02, 0.28, 0.01]
                    pred[y, x, 1] *= 0.05
                    pred[y, x, 2] *= 0.05

        # PORT CONSTRAINT
        ocean_adj = compute_ocean_adjacency(grid, h, w)
        for y in range(h):
            for x in range(w):
                if ocean_adj[y, x] == 0:
                    pred[y, x, 2] = PROB_FLOOR

        # POST-PROCESSING
        pred = pred ** (1.0 / 1.12)
        for y in range(h):
            for x in range(w):
                if grid[y][x] in STATIC_TERRAIN:
                    continue
                probs = pred[y, x]
                mask = probs < 0.016
                if mask.any() and not mask.all():
                    probs[mask] = 0.0
                    probs[:] = np.maximum(probs, PROB_FLOOR)
                    pred[y, x] = probs / probs.sum()
        smoothed = np.copy(pred)
        for cls in range(NUM_CLASSES):
            smoothed[:, :, cls] = gaussian_filter(pred[:, :, cls], sigma=0.3)
        for y in range(h):
            for x in range(w):
                if grid[y][x] in STATIC_TERRAIN:
                    smoothed[y, x] = pred[y, x]
        pred = smoothed
        pred = np.maximum(pred, PROB_FLOOR)
        pred = pred / pred.sum(axis=-1, keepdims=True)

        # SCORE
        result = score_prediction(gt, pred, initial_grid=grid)
        score = result["score"]
        seed_scores.append(score)

        obs_str = f", {int(obs_t.sum())} obs" if obs_t is not None else ""
        log(f"  Seed {seed_idx}: score={score:.1f}{obs_str}")

    avg_score = np.mean(seed_scores)
    log(f"\n{'='*60}")
    log(f"  MOCK ROUND {rn} RESULT: {avg_score:.1f}")
    log(f"  Seeds: {', '.join(f'{s:.1f}' for s in seed_scores)}")
    log(f"  Regime: {regime_info['regime']} (survival={regime_info['survival_rate']:.0%})")
    log(f"  Queries used: {api.queries_used}/50")
    log(f"{'='*60}")

    return avg_score, seed_scores, regime_info


def main():
    parser = argparse.ArgumentParser(description="Mock Round Runner")
    parser.add_argument("--round", type=int, default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--trials", type=int, default=1)
    args = parser.parse_args()

    all_rounds = load_cached_rounds()
    if not all_rounds:
        log("No cached data.")
        return

    if args.all:
        targets = [rd for rd in all_rounds if rd.get("seeds")]
    elif args.round:
        targets = [rd for rd in all_rounds if rd["round_number"] == args.round]
    else:
        import random
        candidates = [rd for rd in all_rounds if rd.get("seeds")]
        targets = [random.choice(candidates)]

    all_scores = []
    for rd in targets:
        trial_scores = []
        for trial in range(args.trials):
            score, seeds, regime = run_mock_round(rd, all_rounds, trial_seed=trial * 42 + 7)
            trial_scores.append(score)
        avg = np.mean(trial_scores)
        all_scores.append((rd["round_number"], avg))

    if len(all_scores) > 1:
        log(f"\n{'='*60}")
        log(f"  MOCK TOURNAMENT SUMMARY")
        log(f"{'='*60}")
        for rn, score in all_scores:
            log(f"  R{rn}: {score:.1f}")
        overall = np.mean([s for _, s in all_scores])
        log(f"\n  OVERALL AVG: {overall:.1f}")


if __name__ == "__main__":
    main()
