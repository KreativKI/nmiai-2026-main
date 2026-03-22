#!/usr/bin/env python3
"""
R23 Final Resubmission Script.

Uses proven-optimal alpha values from exhaustive search:
  - death: alpha=15 (was 5, optimal from search = 84.80 vs 84.35)
  - stable: alpha=12 (was 30, optimal from search = 79.89 vs 79.75)
  - growth: alpha=6 (was 15, optimal from search = 73.14 vs 72.34)
  - extreme growth (avg_growth > 5.0): alpha=3

This script:
1. Loads saved observation data for R23
2. Retrains on ALL available cached ground truth
3. Applies the optimal alpha values
4. Resubmits ALL 5 seeds

Run on GCP ml-brain:
  python3 ~/solutions/resubmit_r23.py --token TOKEN

Or provide round number:
  python3 ~/solutions/resubmit_r23.py --token TOKEN --round 23
"""

import argparse
import json
import time
import sys
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import requests
import lightgbm as lgb

sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    load_cached_rounds, get_session,
    TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, PROB_FLOOR, BASE,
)
from build_dataset import (
    build_master_dataset, FEATURE_NAMES, extract_cell_features,
    _compute_trajectory_features,
)

OCEAN_RAW = {10, 11}
SKIP_CELLS = STATIC_TERRAIN | OCEAN_RAW
DATA_DIR = Path(__file__).parent / "data"
REPLAY_DIR = DATA_DIR / "replays"

# PROVEN OPTIMAL from alpha_search_results.json (LOO-CV on 18 rounds)
OPTIMAL_ALPHA = {
    "death": 15,    # was 5, search shows 84.80 vs 84.35
    "stable": 12,   # was 30, search shows 79.89 vs 79.75
    "growth": 6,    # was 15, search shows 73.14 vs 72.34
}

# LightGBM params (proven optimal: 50 trees is sweet spot)
LGB_PARAMS = {
    "n_estimators": 50,
    "num_leaves": 31,
    "learning_rate": 0.05,
    "min_child_samples": 20,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "objective": "regression",
    "metric": "mse",
    "verbose": -1,
}


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] {msg}", flush=True)


def count_terrain_classes(grid, h, w):
    total_s, total_p, total_f = 0, 0, 0
    for y in range(h):
        for x in range(w):
            cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)
            if cls == 1:
                total_s += 1
            elif cls == 2:
                total_p += 1
            elif cls == 4:
                total_f += 1
    return total_s, total_p, total_f


def main():
    parser = argparse.ArgumentParser(description="R23 Final Resubmission")
    parser.add_argument("--token", required=True)
    parser.add_argument("--round", type=int, default=None,
                        help="Round number (auto-detects active if not set)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Generate predictions but don't submit")
    args = parser.parse_args()

    session = get_session(args.token)

    # Find the active round
    if args.round:
        round_num = args.round
        rounds = session.get(f"{BASE}/astar-island/rounds").json()
        round_info = next((r for r in rounds if r["round_number"] == round_num), None)
        if not round_info:
            log(f"Round {round_num} not found!")
            return
    else:
        rounds = session.get(f"{BASE}/astar-island/rounds").json()
        round_info = next((r for r in rounds if r["status"] == "active"), None)
        if not round_info:
            log("No active round found!")
            return
        round_num = round_info["round_number"]

    round_id = round_info["id"]
    log(f"Resubmitting Round {round_num} (id={round_id})")

    # Load round details
    detail = session.get(f"{BASE}/astar-island/rounds/{round_id}").json()
    h, w = detail["map_height"], detail["map_width"]
    seeds_count = detail["seeds_count"]

    # Load observation data
    per_seed_obs = {}
    for si in range(seeds_count):
        oc_path = DATA_DIR / f"obs_counts_r{round_num}_seed{si}_full.npy"
        ot_path = DATA_DIR / f"obs_total_r{round_num}_seed{si}_full.npy"
        if oc_path.exists() and ot_path.exists():
            per_seed_obs[si] = (np.load(oc_path), np.load(ot_path))
            covered = int((np.load(ot_path) > 0).sum())
            log(f"  Seed {si}: loaded obs ({covered}/1600 coverage)")
        else:
            log(f"  Seed {si}: NO observation data found!")

    if not per_seed_obs:
        log("ERROR: No observation data found. Cannot resubmit.")
        return

    # Detect regime from observations
    growth_ratios = []
    for seed_idx in range(seeds_count):
        if seed_idx not in per_seed_obs:
            growth_ratios.append(1.0)
            continue
        ig = detail["initial_states"][seed_idx]["grid"]
        oc, ot = per_seed_obs[seed_idx]
        obs_argmax = oc.argmax(axis=2)
        observed = ot > 0
        settle_count = int(((obs_argmax == 1) | (obs_argmax == 2))[observed].sum())
        init_settle = sum(1 for y in range(h) for x in range(w)
                          if TERRAIN_TO_CLASS.get(int(ig[y][x]), 0) in (1, 2))
        growth_ratios.append(settle_count / max(init_settle, 1))

    avg_growth = float(np.mean(growth_ratios))
    if avg_growth < 0.9:
        regime = "death"
    elif avg_growth > 1.4:
        regime = "growth"
    else:
        regime = "stable"

    # Select alpha based on OPTIMAL values from search
    if regime == "growth" and avg_growth > 5.0:
        alpha = 3  # Extreme growth: trust observations
    else:
        alpha = OPTIMAL_ALPHA.get(regime, 6)

    log(f"  Regime: {regime}, avg_growth={avg_growth:.2f}, alpha={alpha}")
    log(f"  Per-seed growth: [{', '.join(f'{g:.1f}' for g in growth_ratios)}]")

    # Train model on ALL available data
    rounds_data = load_cached_rounds()
    X, Y, _ = build_master_dataset(rounds_data)
    log(f"  Training: {X.shape[0]} rows, {X.shape[1]} features, {len(rounds_data)} rounds")

    models = {}
    for cls in range(NUM_CLASSES):
        m = lgb.LGBMRegressor(**LGB_PARAMS)
        m.fit(X, Y[:, cls])
        models[cls] = m

    total_s, total_p, init_forest = count_terrain_classes(
        detail["initial_states"][0]["grid"], h, w)

    regime_flags = {
        "regime_death": 1 if regime == "death" else 0,
        "regime_growth": 1 if regime == "growth" else 0,
        "regime_stable": 1 if regime == "stable" else 0,
    }

    # Predict and submit each seed
    for seed_idx in range(seeds_count):
        ig = detail["initial_states"][seed_idx]["grid"]

        # Load replay if available (won't exist for active rounds)
        replay_path = REPLAY_DIR / f"r{round_num}_seed{seed_idx}.json"
        replay_data = None
        if replay_path.exists():
            try:
                with open(replay_path) as f:
                    replay_data = json.load(f)
            except Exception:
                pass
        traj = _compute_trajectory_features(replay_data, total_s)

        # Obs-derived proxy for this seed
        if not replay_data and seed_idx in per_seed_obs:
            oc_s, ot_s = per_seed_obs[seed_idx]
            if (ot_s > 0).any():
                obs_argmax = oc_s.argmax(axis=2)
                observed = ot_s > 0
                obs_settle = int(((obs_argmax == 1) | (obs_argmax == 2))[observed].sum())
                seed_init_s = sum(1 for y in range(h) for x in range(w)
                                  if TERRAIN_TO_CLASS.get(int(ig[y][x]), 0) in (1, 2))
                obs_growth = obs_settle / max(seed_init_s, 1)
                TRAIN_MAX_Y25 = 4.846
                TRAIN_MAX_Y10 = 2.062
                traj["settle_growth_y25"] = min(obs_growth, TRAIN_MAX_Y25)
                traj["settle_growth_y10"] = min(obs_growth, TRAIN_MAX_Y10)

        round_feats = {**regime_flags, "total_settlements": total_s,
                       "total_ports": total_p, **traj}

        cells, coords = [], []
        for y in range(h):
            for x in range(w):
                if int(ig[y][x]) in STATIC_TERRAIN:
                    continue
                fd = extract_cell_features(ig, y, x, h, w, replay_data=replay_data)
                fd.update(round_feats)
                cells.append([fd.get(n, 0) for n in FEATURE_NAMES])
                coords.append((y, x))

        pred = np.zeros((h, w, NUM_CLASSES))
        if cells:
            Xp = np.array(cells, dtype=np.float32)
            coord_arr = np.array(coords)
            for cls in range(NUM_CLASSES):
                pred[coord_arr[:, 0], coord_arr[:, 1], cls] = models[cls].predict(Xp)

        # Static cells
        for y in range(h):
            for x in range(w):
                if int(ig[y][x]) in STATIC_TERRAIN:
                    cls = TERRAIN_TO_CLASS.get(int(ig[y][x]), 0)
                    pred[y, x] = PROB_FLOOR
                    pred[y, x, cls] = 1.0 - (NUM_CLASSES - 1) * PROB_FLOOR

        # Dirichlet blending with optimal alpha
        if seed_idx in per_seed_obs:
            oc_s, ot_s = per_seed_obs[seed_idx]
            for y in range(h):
                for x in range(w):
                    if ot_s[y, x] == 0:
                        continue
                    a = alpha * pred[y, x]
                    a = np.maximum(a, PROB_FLOOR)
                    pred[y, x] = (a + oc_s[y, x]) / (a.sum() + ot_s[y, x])

        # Hard constraints
        for y in range(h):
            for x in range(w):
                if int(ig[y][x]) in (STATIC_TERRAIN | OCEAN_RAW):
                    continue
                has_ocean = any(
                    0 <= y + dy < h and 0 <= x + dx < w
                    and int(ig[y + dy][x + dx]) in OCEAN_RAW
                    for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                    if (dy, dx) != (0, 0)
                )
                if not has_ocean:
                    pred[y, x, 2] = PROB_FLOOR
                pred[y, x, 3] = min(pred[y, x, 3], 0.05)

        # Floor and renormalize (iterate to ensure floor holds after normalization)
        for _ in range(3):
            pred = np.maximum(pred, PROB_FLOOR)
            pred /= pred.sum(axis=-1, keepdims=True)

        # Validate
        assert pred.shape == (h, w, NUM_CLASSES), f"Bad shape: {pred.shape}"
        assert np.all(pred >= PROB_FLOOR - 1e-4), f"Probability below floor! Min={pred.min()}"
        assert np.allclose(pred.sum(axis=-1), 1.0, atol=1e-6), "Not normalized!"

        conf = pred.max(axis=-1).mean()
        has_obs = "obs" if seed_idx in per_seed_obs else "blind"
        log(f"  Seed {seed_idx}: {has_obs}, conf={conf:.3f}, alpha={alpha}")

        if args.dry_run:
            log(f"  Seed {seed_idx}: DRY RUN (not submitted)")
            continue

        for attempt in range(5):
            try:
                resp = session.post(f"{BASE}/astar-island/submit", json={
                    "round_id": round_id, "seed_index": seed_idx,
                    "prediction": pred.tolist(),
                })
                resp.raise_for_status()
                log(f"  Seed {seed_idx}: SUBMITTED")
                break
            except requests.HTTPError as e:
                if e.response and e.response.status_code == 429:
                    time.sleep(3 * (attempt + 1))
                    continue
                log(f"  Seed {seed_idx}: FAILED - {e}")
                if e.response:
                    log(f"    Response: {e.response.text[:200]}")
                break
        time.sleep(0.5)

    log("Resubmission complete.")


if __name__ == "__main__":
    main()
