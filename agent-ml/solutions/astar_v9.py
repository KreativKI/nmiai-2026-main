#!/usr/bin/env python3
"""
Chef v9 — Back to Basics + Smell Test

R9 scored 82.6 using the simple approach:
- V2 NeighborhoodModel (global, no regime forcing)
- All 50 queries on seed 0 (deep stacking)
- Dirichlet blending ps=12
- T=1.12, collapse=0.016, sigma=0.3

V9 keeps what worked and adds only the smell test for safety:
- Smell test: 5+5 queries for reliable regime detection (no more false positives)
- Deep stack: remaining 40 queries ALL on seed 0 (not spread across 5 seeds)
- V2 model trained on ALL 13 rounds (was 8 for R9)
- Same post-processing as R9

What V9 does NOT do (lessons from V7/V8 regressions):
- No regime-specific transition tables (over-corrects, hurt R9 score)
- No spreading queries across 5 seeds (thin coverage hurts more than it helps)
- No round-specific calibration overrides (too aggressive)
- No entropy-aware temperature (one global T works better)

Usage:
  python astar_v9.py --token TOKEN --phase all
  python astar_v9.py --token TOKEN --phase all --dry-run
"""

import argparse
import json
import time
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import requests
from scipy.ndimage import gaussian_filter

BASE = "https://api.ainm.no"
DATA_DIR = Path(__file__).parent / "data"

TERRAIN_TO_CLASS = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 10: 0, 11: 0}
STATIC_TERRAIN = {5, 10}
NUM_CLASSES = 6
PROB_FLOOR = 0.01
TEMPERATURE = 1.12
COLLAPSE_THRESH = 0.016
SMOOTH_SIGMA = 0.3
PRIOR_STRENGTH = 12.0


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def get_session(token):
    s = requests.Session()
    s.cookies.set("access_token", token, domain="api.ainm.no")
    s.headers["User-Agent"] = "chef-v9/nmiai-2026"
    return s


def query_viewport(session, round_id, seed_idx, x, y, w=15, h=15):
    resp = session.post(f"{BASE}/astar-island/simulate", json={
        "round_id": round_id, "seed_index": seed_idx,
        "viewport_x": x, "viewport_y": y, "viewport_w": w, "viewport_h": h,
    })
    resp.raise_for_status()
    time.sleep(0.22)
    return resp.json()


def tile_viewports(height, width, vsize=15):
    vps = []
    for vy in range(0, height, vsize):
        for vx in range(0, width, vsize):
            vps.append((vx, vy, min(vsize, width - vx), min(vsize, height - vy)))
    return vps


def find_settlement_cells(grid, h, w):
    cells = []
    for y in range(h):
        for x in range(w):
            if TERRAIN_TO_CLASS.get(int(grid[y][x]), 0) in (1, 2):
                cells.append((y, x))
    return cells


# ──────────────────────────────────────────────
# PHASE 1: Smell Test (5+5 queries for regime detection)
# ──────────────────────────────────────────────
def smell_test(session, round_id, detail, round_num):
    """Reliable regime detection. Returns obs data collected during test."""
    height, width = detail["map_height"], detail["map_width"]
    ig0 = detail["initial_states"][0]["grid"]
    settle_cells = find_settlement_cells(ig0, height, width)

    obs_counts = np.zeros((height, width, NUM_CLASSES))
    obs_total = np.zeros((height, width))

    # Pick 5 spread settlement cells
    if len(settle_cells) > 5:
        indices = np.linspace(0, len(settle_cells) - 1, 5, dtype=int)
        test_cells = [settle_cells[i] for i in indices]
    else:
        test_cells = settle_cells[:5]

    test_vps = []
    used_vps = set()
    for sy, sx in test_cells:
        vx = max(0, min(sx - 7, width - 15))
        vy = max(0, min(sy - 7, height - 15))
        if (vx, vy) not in used_vps:
            used_vps.add((vx, vy))
            test_vps.append((vx, vy, 15, 15))

    queries_used = 0

    def do_queries(vps, max_n):
        nonlocal queries_used
        for vx, vy, vw, vh in vps[:max_n]:
            try:
                obs = query_viewport(session, round_id, 0, vx, vy, vw, vh)
                for dy, row in enumerate(obs["grid"]):
                    for dx, terrain in enumerate(row):
                        ya, xa = obs["viewport"]["y"] + dy, obs["viewport"]["x"] + dx
                        obs_counts[ya, xa, TERRAIN_TO_CLASS.get(terrain, 0)] += 1
                        obs_total[ya, xa] += 1
                queries_used += 1
            except Exception as e:
                log(f"  Query failed: {e}")
                break

    # First sniff
    do_queries(test_vps, 5)
    alive, dead = 0, 0
    for sy, sx in test_cells:
        if obs_total[sy, sx] == 0:
            continue
        if obs_counts[sy, sx, 1] + obs_counts[sy, sx, 2] > 0:
            alive += 1
        else:
            dead += 1
    checked = alive + dead
    log(f"  Smell test: {alive}/{checked} alive")

    if checked > 0 and alive == 0:
        regime = "death"
        log(f"  CONFIDENT: death")
    elif checked > 0 and alive == checked:
        regime = "growth"
        log(f"  CONFIDENT: growth")
    else:
        # Uncertain: re-sample
        log(f"  UNCERTAIN. Confirming...")
        do_queries(test_vps, 5)
        alive2, dead2 = 0, 0
        for sy, sx in test_cells:
            n = obs_total[sy, sx]
            if n == 0:
                continue
            sp_frac = (obs_counts[sy, sx, 1] + obs_counts[sy, sx, 2]) / n
            if sp_frac > 0.3:
                alive2 += 1
            else:
                dead2 += 1
        survival = alive2 / max(1, alive2 + dead2)
        if survival < 0.15:
            regime = "death"
        elif survival > 0.60:
            regime = "growth"
        else:
            regime = "stable"
        log(f"  Confirmed: {regime} (survival={survival:.0%})")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_DIR / f"regime_r{round_num}.json", "w") as f:
        json.dump({"regime": regime, "queries_used": queries_used}, f)

    log(f"  Regime: {regime} ({queries_used} queries)")
    return obs_counts, obs_total, regime, queries_used


# ──────────────────────────────────────────────
# PHASE 2: Deep stack on seed 0 (like R9)
# ──────────────────────────────────────────────
def deep_stack_seed0(session, round_id, detail, round_num,
                     obs_counts, obs_total, queries_spent):
    """Use ALL remaining queries on seed 0. Deep stacking = multiple samples per cell."""
    height, width = detail["map_height"], detail["map_width"]
    viewports = tile_viewports(height, width, 15)

    budget = session.get(f"{BASE}/astar-island/budget").json()
    remaining = budget["queries_max"] - budget["queries_used"]
    log(f"  Deep stacking seed 0: {remaining} queries remaining")

    # First pass: fill any uncovered areas
    for vx, vy, vw, vh in viewports:
        if remaining <= 0:
            break
        if obs_total[vy, vx] > 0:
            continue
        try:
            obs = query_viewport(session, round_id, 0, vx, vy, vw, vh)
            for dy, row in enumerate(obs["grid"]):
                for dx, terrain in enumerate(row):
                    ya, xa = obs["viewport"]["y"] + dy, obs["viewport"]["x"] + dx
                    obs_counts[ya, xa, TERRAIN_TO_CLASS.get(terrain, 0)] += 1
                    obs_total[ya, xa] += 1
            remaining -= 1
        except Exception as e:
            log(f"  Fill query failed: {e}")
            break

    # Second pass: stack on dynamic regions (settlements, forests near settlements)
    ig0 = detail["initial_states"][0]["grid"]
    heat = np.zeros((height, width))
    for y in range(height):
        for x in range(width):
            if ig0[y][x] in STATIC_TERRAIN:
                continue
            cls = TERRAIN_TO_CLASS.get(int(ig0[y][x]), 0)
            if cls in (1, 2):
                heat[y, x] += 5
            elif cls == 4:
                heat[y, x] += 2
            elif cls == 0:
                heat[y, x] += 1

    used = np.zeros((height, width), dtype=bool)
    while remaining > 0:
        best_score = -1
        best_vp = None
        for vy in range(0, max(1, height - 14), 3):
            for vx in range(0, max(1, width - 14), 3):
                region = heat[vy:vy+15, vx:vx+15]
                region_used = used[vy:vy+15, vx:vx+15]
                score = region[~region_used].sum() if (~region_used).any() else 0
                if score > best_score:
                    best_score = score
                    best_vp = (vx, vy, 15, 15)
        if best_vp is None or best_score <= 0:
            # All heat exhausted, just tile the whole map again
            for vx, vy, vw, vh in viewports:
                if remaining <= 0:
                    break
                try:
                    obs = query_viewport(session, round_id, 0, vx, vy, vw, vh)
                    for dy, row in enumerate(obs["grid"]):
                        for dx, terrain in enumerate(row):
                            ya, xa = obs["viewport"]["y"] + dy, obs["viewport"]["x"] + dx
                            obs_counts[ya, xa, TERRAIN_TO_CLASS.get(terrain, 0)] += 1
                            obs_total[ya, xa] += 1
                    remaining -= 1
                except Exception as e:
                    break
            break

        vx, vy, vw, vh = best_vp
        try:
            obs = query_viewport(session, round_id, 0, vx, vy, vw, vh)
            for dy, row in enumerate(obs["grid"]):
                for dx, terrain in enumerate(row):
                    ya, xa = obs["viewport"]["y"] + dy, obs["viewport"]["x"] + dx
                    obs_counts[ya, xa, TERRAIN_TO_CLASS.get(terrain, 0)] += 1
                    obs_total[ya, xa] += 1
            used[vy:vy+15, vx:vx+15] = True
            remaining -= 1
        except Exception as e:
            break

    np.save(DATA_DIR / f"obs_counts_r{round_num}_seed0_stacked.npy", obs_counts)
    np.save(DATA_DIR / f"obs_total_r{round_num}_seed0_stacked.npy", obs_total)

    multi = (obs_total >= 2).sum()
    total = (obs_total > 0).sum()
    log(f"  Seed 0: {total}/{height*width} covered, {multi} with 2+ samples")
    return obs_counts, obs_total


# ──────────────────────────────────────────────
# PHASE 3: Predict & Submit (V2 model, like R9)
# ──────────────────────────────────────────────
def predict_and_submit(session, round_id, detail, round_num,
                       obs_counts, obs_total, regime, dry_run=False):
    """V2 NeighborhoodModel + Dirichlet blending. Same recipe as R9."""
    height, width = detail["map_height"], detail["map_width"]
    seeds_count = detail["seeds_count"]

    # Train V2 on all cached rounds
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from backtest import load_cached_rounds, TERRAIN_TO_CLASS as TC
    from churn import NeighborhoodModelV2

    model = NeighborhoodModelV2()
    for rd in load_cached_rounds():
        model.add_training_data(rd)
    model.finalize()
    model.stats()

    log(f"\nPredicting {seeds_count} seeds (regime={regime})...")

    for seed_idx in range(seeds_count):
        grid = detail["initial_states"][seed_idx]["grid"]

        # V2 model + Dirichlet observation blending (only seed 0 has obs)
        if seed_idx == 0:
            pred = model.predict_grid_with_obs(
                detail, seed_idx,
                obs_counts=obs_counts,
                obs_total=obs_total,
                prior_strength=PRIOR_STRENGTH,
            )
        else:
            pred = model.predict_grid(detail, seed_idx)

        # Global temperature scaling (same as R9)
        pred = pred ** (1.0 / TEMPERATURE)

        # Fixed collapse thresholding
        for y in range(height):
            for x in range(width):
                if grid[y][x] in STATIC_TERRAIN:
                    continue
                probs = pred[y, x]
                mask = probs < COLLAPSE_THRESH
                if mask.any() and not mask.all():
                    probs[mask] = PROB_FLOOR
                    pred[y, x] = probs / probs.sum()

        # Spatial smoothing
        smoothed = np.copy(pred)
        for cls in range(NUM_CLASSES):
            smoothed[:, :, cls] = gaussian_filter(pred[:, :, cls], sigma=SMOOTH_SIGMA)
        for y in range(height):
            for x in range(width):
                if grid[y][x] in STATIC_TERRAIN:
                    smoothed[y, x] = pred[y, x]
        pred = smoothed

        # Floor and renormalize
        pred = np.maximum(pred, PROB_FLOOR)
        pred = pred / pred.sum(axis=-1, keepdims=True)

        # Validate
        assert pred.shape == (height, width, NUM_CLASSES)
        assert np.allclose(pred.sum(axis=-1), 1.0, atol=0.01)
        assert (pred >= PROB_FLOOR - 0.001).all()

        avg_conf = pred.max(axis=-1).mean()
        obs_n = int(obs_total.sum()) if seed_idx == 0 else 0
        log(f"Seed {seed_idx}: conf {avg_conf:.3f}, {obs_n} obs")

        if dry_run:
            log(f"  [DRY RUN]")
        else:
            time.sleep(0.5)
            for attempt in range(5):
                try:
                    resp = session.post(f"{BASE}/astar-island/submit", json={
                        "round_id": round_id,
                        "seed_index": seed_idx,
                        "prediction": pred.tolist(),
                    })
                    resp.raise_for_status()
                    log(f"  SUBMITTED")
                    break
                except requests.HTTPError as e:
                    if e.response and e.response.status_code == 429:
                        wait = 5 * (attempt + 1)
                        log(f"  Rate limited, waiting {wait}s...")
                        time.sleep(wait)
                        continue
                    log(f"  FAILED: {e}")
                    break

    log("\nChef v9 done!")


def main():
    parser = argparse.ArgumentParser(description="Chef v9 — Back to Basics + Smell Test")
    parser.add_argument("--token", required=True)
    parser.add_argument("--phase", required=True, choices=["smell", "stack", "submit", "all"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    session = get_session(args.token)
    active = None
    for r in session.get(f"{BASE}/astar-island/rounds").json():
        if r["status"] == "active":
            active = r
            break
    if not active:
        log("No active round.")
        return

    round_id = active["id"]
    round_num = active["round_number"]
    closes = datetime.fromisoformat(active["closes_at"])
    remaining = (closes - datetime.now(timezone.utc)).total_seconds() / 60
    detail = session.get(f"{BASE}/astar-island/rounds/{round_id}").json()
    budget = session.get(f"{BASE}/astar-island/budget").json()

    log(f"Round #{round_num}, weight {active['round_weight']:.4f}, "
        f"{remaining:.0f} min left, queries {budget['queries_used']}/50")

    if args.phase == "all":
        log("\n" + "=" * 50)
        log("CHEF V9: BACK TO BASICS + SMELL TEST")
        log("=" * 50)

        if budget["queries_used"] >= budget["queries_max"]:
            log("Budget exhausted. Loading existing observations...")
            oc = np.load(DATA_DIR / f"obs_counts_r{round_num}_seed0_stacked.npy")
            ot = np.load(DATA_DIR / f"obs_total_r{round_num}_seed0_stacked.npy")
            rp = DATA_DIR / f"regime_r{round_num}.json"
            regime = json.load(open(rp))["regime"] if rp.exists() else "stable"
        else:
            oc, ot, regime, q = smell_test(session, round_id, detail, round_num)
            log("\n" + "-" * 50)
            oc, ot = deep_stack_seed0(session, round_id, detail, round_num, oc, ot, q)

        log("\n" + "-" * 50)
        predict_and_submit(session, round_id, detail, round_num,
                           oc, ot, regime, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
