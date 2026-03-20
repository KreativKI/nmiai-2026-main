#!/usr/bin/env python3
"""
Strategy Comparison: V7 (full coverage) vs V7b (regime-first)

V7:  9 queries/seed x 5 seeds = 45 overview, then 5 stacking on seed 0
V7b: 5 queries on known settlements (regime detect), then regime-specific:
     - EXTINCTION: minimal queries, high-confidence empty prediction
     - STABLE: spread queries across seeds, focus on settlement clusters
     - GROWTH: query frontier cells around settlements

Runs blind mock rounds on all cached data to compare.
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter

import sys
sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    load_cached_rounds, score_prediction,
    TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, PROB_FLOOR,
)
from churn import NeighborhoodModelV2
from mock_round import MockAPI, tile_viewports
from astar_v7 import compute_ocean_adjacency


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def apply_postprocessing(pred, grid, h, w):
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
    return pred


def find_settlement_cells(grid, h, w):
    """Find initial settlement/port positions."""
    cells = []
    for y in range(h):
        for x in range(w):
            cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)
            if cls in (1, 2):
                cells.append((y, x))
    return cells


def detect_regime_from_settlement_queries(api, seed_idx, grid, h, w, n_queries=5):
    """Query known settlement positions to detect regime.
    Returns regime info + obs data."""
    settle_cells = find_settlement_cells(grid, h, w)
    obs_counts = np.zeros((h, w, NUM_CLASSES))
    obs_total = np.zeros((h, w))

    alive = 0
    dead = 0
    queried = 0

    # Query small viewports centered on settlements (3x3 around each)
    queried_positions = set()
    for sy, sx in settle_cells[:n_queries * 3]:  # more candidates than queries
        if queried >= n_queries:
            break
        # Find a viewport that includes this settlement
        vx = max(0, min(sx - 7, w - 15))
        vy = max(0, min(sy - 7, h - 15))
        vp_key = (vx, vy)
        if vp_key in queried_positions:
            continue
        queried_positions.add(vp_key)

        obs = api.simulate(seed_idx, vx, vy, 15, 15)
        for dy, row in enumerate(obs["grid"]):
            for dx, terrain in enumerate(row):
                ya, xa = vy + dy, vx + dx
                if 0 <= ya < h and 0 <= xa < w:
                    obs_counts[ya, xa, terrain] += 1
                    obs_total[ya, xa] += 1
        queried += 1

        # Check settlements in this viewport
        for sy2, sx2 in settle_cells:
            if vy <= sy2 < vy + 15 and vx <= sx2 < vx + 15:
                observed_cls = int(obs["grid"][sy2 - vy][sx2 - vx])
                if observed_cls in (1, 2):
                    alive += 1
                else:
                    dead += 1

    total_checked = alive + dead
    survival_rate = alive / max(1, total_checked)

    # Count new settlements in observed area
    new_settlements = 0
    for y in range(h):
        for x in range(w):
            if obs_total[y, x] == 0:
                continue
            cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)
            if cls not in (1, 2) and grid[y][x] not in STATIC_TERRAIN:
                if obs_counts[y, x, 1] + obs_counts[y, x, 2] > 0:
                    new_settlements += 1

    if survival_rate < 0.10 and new_settlements <= 2:
        regime = "extinction"
    elif new_settlements > total_checked * 0.5:
        regime = "growth"
    else:
        regime = "stable"

    return regime, survival_rate, obs_counts, obs_total, queried


def run_strategy_v7(target_round, all_rounds, trial_seed=42):
    """V7: Full overview of all 5 seeds (9 each = 45), then 5 stacking."""
    rn = target_round["round_number"]
    h, w = target_round["map_height"], target_round["map_width"]
    rng = np.random.default_rng(trial_seed)
    api = MockAPI(target_round, rng)

    # Train model
    v2 = NeighborhoodModelV2()
    for other_rd in all_rounds:
        if other_rd["round_number"] != rn and other_rd.get("seeds"):
            v2.add_training_data(other_rd)
    v2.finalize()

    viewports = tile_viewports(h, w, 15)
    all_obs = {}

    # Overview all 5 seeds
    for si in range(5):
        if str(si) not in target_round["seeds"]:
            continue
        obs_c = np.zeros((h, w, NUM_CLASSES))
        obs_t = np.zeros((h, w))
        for vx, vy, vw, vh in viewports:
            obs = api.simulate(si, vx, vy, vw, vh)
            for dy, row in enumerate(obs["grid"]):
                for dx, terrain in enumerate(row):
                    ya, xa = vy + dy, vx + dx
                    if 0 <= ya < h and 0 <= xa < w:
                        obs_c[ya, xa, terrain] += 1
                        obs_t[ya, xa] += 1
        all_obs[si] = (obs_c, obs_t)

    # Detect regime from seed 0
    ig0 = target_round["initial_states"][0]["grid"]
    settle_cells = find_settlement_cells(ig0, h, w)
    alive = sum(1 for sy, sx in settle_cells
                if all_obs[0][0][sy, sx, 1] + all_obs[0][0][sy, sx, 2] > 0)
    survival = alive / max(1, len(settle_cells))
    new_s = 0
    for y in range(h):
        for x in range(w):
            cls = TERRAIN_TO_CLASS.get(int(ig0[y][x]), 0)
            if cls not in (1, 2) and ig0[y][x] not in STATIC_TERRAIN:
                if all_obs[0][0][y, x, 1] + all_obs[0][0][y, x, 2] > 0:
                    new_s += 1
    if survival < 0.10 and new_s <= 2:
        regime = "extinction"
    elif new_s > len(settle_cells) * 0.5:
        regime = "growth"
    else:
        regime = "stable"

    # 5 stacking queries on seed 0
    obs_c0, obs_t0 = all_obs[0]
    heat = np.zeros((h, w))
    for y in range(h):
        for x in range(w):
            if ig0[y][x] in STATIC_TERRAIN:
                continue
            cls = TERRAIN_TO_CLASS.get(int(ig0[y][x]), 0)
            if cls in (1, 2):
                heat[y, x] += 5
    used = np.zeros((h, w), dtype=bool)
    for _ in range(min(5, api.queries_max - api.queries_used)):
        best_score = -1
        best_vp = None
        for vy in range(0, max(1, h - 14), 3):
            for vx in range(0, max(1, w - 14), 3):
                region = heat[vy:vy+15, vx:vx+15]
                ru = used[vy:vy+15, vx:vx+15]
                s = region[~ru].sum() if (~ru).any() else 0
                if s > best_score:
                    best_score = s
                    best_vp = (vx, vy, 15, 15)
        if best_vp is None:
            break
        vx, vy, vw, vh = best_vp
        obs = api.simulate(0, vx, vy, vw, vh)
        for dy, row in enumerate(obs["grid"]):
            for dx, terrain in enumerate(row):
                ya, xa = vy + dy, vx + dx
                if 0 <= ya < h and 0 <= xa < w:
                    obs_c0[ya, xa, terrain] += 1
                    obs_t0[ya, xa] += 1
        used[vy:vy+15, vx:vx+15] = True
    all_obs[0] = (obs_c0, obs_t0)

    # Build and score predictions
    return _score_predictions(target_round, all_obs, v2, regime, h, w)


def run_strategy_v7b(target_round, all_rounds, trial_seed=42):
    """V7b: 5 settlement queries for regime, then regime-specific strategy."""
    rn = target_round["round_number"]
    h, w = target_round["map_height"], target_round["map_width"]
    rng = np.random.default_rng(trial_seed)
    api = MockAPI(target_round, rng)

    v2 = NeighborhoodModelV2()
    for other_rd in all_rounds:
        if other_rd["round_number"] != rn and other_rd.get("seeds"):
            v2.add_training_data(other_rd)
    v2.finalize()

    ig0 = target_round["initial_states"][0]["grid"]

    # Phase 1: 5 queries on seed 0 settlement locations for regime detection
    regime, survival, obs_c0, obs_t0, queries_used = detect_regime_from_settlement_queries(
        api, 0, ig0, h, w, n_queries=5)

    all_obs = {0: (obs_c0, obs_t0)}
    remaining = api.queries_max - api.queries_used

    if regime == "extinction":
        # EXTINCTION: Don't waste queries. Use remaining for overview of all seeds
        # (to get observation data for Dirichlet blending)
        viewports = tile_viewports(h, w, 15)
        for si in range(5):
            if str(si) not in target_round["seeds"]:
                continue
            if si == 0:
                # Finish seed 0 overview
                for vx, vy, vw, vh in viewports:
                    if api.queries_used >= api.queries_max:
                        break
                    # Skip if already observed
                    if obs_t0[vy, vx] > 0:
                        continue
                    obs = api.simulate(si, vx, vy, vw, vh)
                    for dy, row in enumerate(obs["grid"]):
                        for dx, terrain in enumerate(row):
                            ya, xa = vy + dy, vx + dx
                            if 0 <= ya < h and 0 <= xa < w:
                                obs_c0[ya, xa, terrain] += 1
                                obs_t0[ya, xa] += 1
                all_obs[0] = (obs_c0, obs_t0)
            else:
                if api.queries_used >= api.queries_max:
                    break
                obs_c = np.zeros((h, w, NUM_CLASSES))
                obs_t = np.zeros((h, w))
                for vx, vy, vw, vh in viewports:
                    if api.queries_used >= api.queries_max:
                        break
                    obs = api.simulate(si, vx, vy, vw, vh)
                    for dy, row in enumerate(obs["grid"]):
                        for dx, terrain in enumerate(row):
                            ya, xa = vy + dy, vx + dx
                            if 0 <= ya < h and 0 <= xa < w:
                                obs_c[ya, xa, terrain] += 1
                                obs_t[ya, xa] += 1
                all_obs[si] = (obs_c, obs_t)

    elif regime == "growth":
        # GROWTH: Overview seed 0 fully, then overview seeds 1-4
        viewports = tile_viewports(h, w, 15)
        # Finish seed 0 overview
        for vx, vy, vw, vh in viewports:
            if api.queries_used >= api.queries_max:
                break
            if obs_t0[vy, vx] > 0:
                continue
            obs = api.simulate(0, vx, vy, vw, vh)
            for dy, row in enumerate(obs["grid"]):
                for dx, terrain in enumerate(row):
                    ya, xa = vy + dy, vx + dx
                    if 0 <= ya < h and 0 <= xa < w:
                        obs_c0[ya, xa, terrain] += 1
                        obs_t0[ya, xa] += 1
        all_obs[0] = (obs_c0, obs_t0)

        # Overview remaining seeds
        for si in range(1, 5):
            if str(si) not in target_round["seeds"]:
                continue
            if api.queries_used >= api.queries_max:
                break
            grid_si = target_round["initial_states"][si]["grid"]
            obs_c = np.zeros((h, w, NUM_CLASSES))
            obs_t = np.zeros((h, w))
            for vx, vy, vw, vh in viewports:
                if api.queries_used >= api.queries_max:
                    break
                obs = api.simulate(si, vx, vy, vw, vh)
                for dy, row in enumerate(obs["grid"]):
                    for dx, terrain in enumerate(row):
                        ya, xa = vy + dy, vx + dx
                        if 0 <= ya < h and 0 <= xa < w:
                            obs_c[ya, xa, terrain] += 1
                            obs_t[ya, xa] += 1
            all_obs[si] = (obs_c, obs_t)

    else:
        # STABLE: Same as growth strategy (overview all seeds)
        viewports = tile_viewports(h, w, 15)
        for vx, vy, vw, vh in viewports:
            if api.queries_used >= api.queries_max:
                break
            if obs_t0[vy, vx] > 0:
                continue
            obs = api.simulate(0, vx, vy, vw, vh)
            for dy, row in enumerate(obs["grid"]):
                for dx, terrain in enumerate(row):
                    ya, xa = vy + dy, vx + dx
                    if 0 <= ya < h and 0 <= xa < w:
                        obs_c0[ya, xa, terrain] += 1
                        obs_t0[ya, xa] += 1
        all_obs[0] = (obs_c0, obs_t0)

        for si in range(1, 5):
            if str(si) not in target_round["seeds"]:
                continue
            if api.queries_used >= api.queries_max:
                break
            obs_c = np.zeros((h, w, NUM_CLASSES))
            obs_t = np.zeros((h, w))
            for vx, vy, vw, vh in viewports:
                if api.queries_used >= api.queries_max:
                    break
                obs = api.simulate(si, vx, vy, vw, vh)
                for dy, row in enumerate(obs["grid"]):
                    for dx, terrain in enumerate(row):
                        ya, xa = vy + dy, vx + dx
                        if 0 <= ya < h and 0 <= xa < w:
                            obs_c[ya, xa, terrain] += 1
                            obs_t[ya, xa] += 1
            all_obs[si] = (obs_c, obs_t)

    return _score_predictions(target_round, all_obs, v2, regime, h, w)


def _score_predictions(target_round, all_obs, v2, regime, h, w):
    """Build predictions with V2 + calibration, score against ground truth."""
    seed_scores = []

    for si in range(5):
        si_str = str(si)
        if si_str not in target_round["seeds"]:
            continue
        grid = target_round["initial_states"][si]["grid"]
        gt = np.array(target_round["seeds"][si_str]["ground_truth"])

        obs_c = all_obs[si][0] if si in all_obs else None
        obs_t = all_obs[si][1] if si in all_obs else None

        pred = v2.predict_grid_with_obs(
            target_round, si,
            obs_counts=obs_c, obs_total=obs_t,
            prior_strength=12.0)

        # EXTINCTION calibration
        if regime == "extinction":
            for y in range(h):
                for x in range(w):
                    if grid[y][x] in STATIC_TERRAIN:
                        continue
                    cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)
                    if cls in (1, 2):
                        pred[y, x] = [0.65, 0.02, 0.01, 0.02, 0.28, 0.01]
                    pred[y, x, 1] *= 0.05
                    pred[y, x, 2] *= 0.05

        # Port constraint
        ocean_adj = compute_ocean_adjacency(grid, h, w)
        for y in range(h):
            for x in range(w):
                if ocean_adj[y, x] == 0:
                    pred[y, x, 2] = PROB_FLOOR

        pred = apply_postprocessing(pred, grid, h, w)
        result = score_prediction(gt, pred, initial_grid=grid)
        seed_scores.append(result["score"])

    avg = np.mean(seed_scores)
    return avg, seed_scores, regime


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=5)
    args = parser.parse_args()

    all_rounds = load_cached_rounds()
    targets = [rd for rd in all_rounds if rd.get("seeds")]

    log(f"Comparing V7 vs V7b across {len(targets)} rounds, {args.trials} trials each")
    log(f"{'='*70}")

    v7_all = []
    v7b_all = []

    for rd in targets:
        rn = rd["round_number"]
        v7_trials = []
        v7b_trials = []
        v7b_regimes = []

        for trial in range(args.trials):
            seed = trial * 42 + rn * 7
            s7, _, _ = run_strategy_v7(rd, all_rounds, trial_seed=seed)
            s7b, _, regime = run_strategy_v7b(rd, all_rounds, trial_seed=seed)
            v7_trials.append(s7)
            v7b_trials.append(s7b)
            v7b_regimes.append(regime)

        avg7 = np.mean(v7_trials)
        avg7b = np.mean(v7b_trials)
        delta = avg7b - avg7
        sign = "+" if delta >= 0 else ""
        regime_counts = {}
        for r in v7b_regimes:
            regime_counts[r] = regime_counts.get(r, 0) + 1

        log(f"R{rn}: v7={avg7:.1f}  v7b={avg7b:.1f}  delta={sign}{delta:.1f}  "
            f"regimes={regime_counts}")
        v7_all.append(avg7)
        v7b_all.append(avg7b)

    overall_v7 = np.mean(v7_all)
    overall_v7b = np.mean(v7b_all)
    delta = overall_v7b - overall_v7
    sign = "+" if delta >= 0 else ""
    log(f"\n{'='*70}")
    log(f"OVERALL: v7={overall_v7:.1f}  v7b={overall_v7b:.1f}  delta={sign}{delta:.1f}")
    log(f"{'='*70}")


if __name__ == "__main__":
    main()
