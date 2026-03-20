#!/usr/bin/env python3
"""
Astar Island Overnight Autonomous Runner

Runs every 5 minutes on GCP VM. Handles the full round lifecycle:
1. Check for active rounds
2. If new round: observe all seeds, detect regime, submit predictions
3. If round just closed: cache ground truth, retrain model
4. Log everything to overnight_log.txt

Usage:
  python overnight_runner.py --token TOKEN               # Single check
  python overnight_runner.py --token TOKEN --continuous   # Run loop (5 min interval)

Safety:
  - Floors all probabilities at 0.01
  - Validates predictions before submitting
  - Logs every action
  - Falls back to model-only if observations fail
"""

import argparse
import json
import time
import traceback
from pathlib import Path
from datetime import datetime, timezone, timedelta

import numpy as np
import requests
from scipy.ndimage import gaussian_filter

import sys
sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    load_cached_rounds, score_prediction, get_session, cache_round,
    TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, PROB_FLOOR, BASE,
)
from churn import NeighborhoodModelV2

DATA_DIR = Path(__file__).parent / "data"
STATE_FILE = Path(__file__).parent.parent / "overnight_state.json"
LOG_FILE = Path.home() / "overnight_log.txt"


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"submitted_rounds": [], "cached_rounds": [], "last_model_rounds": 0}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def compute_ocean_adjacency(grid, h, w):
    adj = np.zeros((h, w), dtype=int)
    for y in range(h):
        for x in range(w):
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if (dy, dx) == (0, 0):
                        continue
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and int(grid[ny][nx]) == 10:
                        adj[y, x] += 1
    return adj


def tile_viewports(height, width, vsize=15):
    viewports = []
    for vy in range(0, height, vsize):
        for vx in range(0, width, vsize):
            vh = min(vsize, height - vy)
            vw = min(vsize, width - vx)
            viewports.append((vx, vy, vw, vh))
    return viewports


def find_settlement_cells(grid, h, w):
    cells = []
    for y in range(h):
        for x in range(w):
            cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)
            if cls in (1, 2):
                cells.append((y, x))
    return cells


def query_viewport(session, round_id, seed_idx, x, y, w=15, h=15):
    resp = session.post(f"{BASE}/astar-island/simulate", json={
        "round_id": round_id,
        "seed_index": seed_idx,
        "viewport_x": x, "viewport_y": y,
        "viewport_w": w, "viewport_h": h,
    })
    resp.raise_for_status()
    time.sleep(0.22)
    return resp.json()


def load_existing_observations(round_num, seeds_count):
    """Load any existing observation files for this round."""
    all_obs = {}
    for si in range(seeds_count):
        for label in [f"seed{si}_stacked", f"seed{si}_overview"]:
            pc = DATA_DIR / f"obs_counts_r{round_num}_{label}.npy"
            pt = DATA_DIR / f"obs_total_r{round_num}_{label}.npy"
            if pc.exists() and pt.exists():
                oc, ot = np.load(pc), np.load(pt)
                if si in all_obs:
                    prev_oc, prev_ot = all_obs[si]
                    mask = ot > prev_ot
                    prev_oc[mask] = oc[mask]
                    prev_ot[mask] = ot[mask]
                else:
                    all_obs[si] = (oc.copy(), ot.copy())
    return all_obs


def observe_all_seeds(session, round_id, detail, round_num):
    """Regime-first observation: 5 settlement queries + overview all seeds."""
    height, width = detail["map_height"], detail["map_width"]
    seeds_count = detail["seeds_count"]

    # Check budget FIRST: if exhausted, load existing observations
    budget_info = session.get(f"{BASE}/astar-island/budget").json()
    remaining = budget_info["queries_max"] - budget_info["queries_used"]
    if remaining <= 0:
        log(f"  Budget exhausted ({budget_info['queries_used']}/{budget_info['queries_max']}). Loading existing observations...")
        all_obs = load_existing_observations(round_num, seeds_count)
        # Load regime from disk
        regime_path = DATA_DIR / f"regime_r{round_num}.json"
        if regime_path.exists():
            with open(regime_path) as f:
                regime_info = json.load(f)
            log(f"  Loaded regime from disk: {regime_info['regime']}")
        else:
            regime_info = {"regime": "stable", "survival_rate": 0.4}
            log(f"  No regime file found, defaulting to stable")
        return all_obs, regime_info

    viewports = tile_viewports(height, width, 15)
    ig0 = detail["initial_states"][0]["grid"]
    settle_cells = find_settlement_cells(ig0, height, width)

    # Step A: 5 regime-detection queries on seed 0
    log(f"  Regime detection: {len(settle_cells)} known settlements")
    obs_counts_0 = np.zeros((height, width, NUM_CLASSES))
    obs_total_0 = np.zeros((height, width))
    queried_vps = set()

    for sy, sx in settle_cells:
        if len(queried_vps) >= 5:
            break
        vx = max(0, min(sx - 7, width - 15))
        vy = max(0, min(sy - 7, height - 15))
        vp_key = (vx, vy)
        if vp_key in queried_vps:
            continue
        queried_vps.add(vp_key)
        try:
            obs = query_viewport(session, round_id, 0, vx, vy, 15, 15)
            for dy, row in enumerate(obs["grid"]):
                for dx, terrain in enumerate(row):
                    ya, xa = obs["viewport"]["y"] + dy, obs["viewport"]["x"] + dx
                    cls = TERRAIN_TO_CLASS.get(terrain, 0)
                    obs_counts_0[ya, xa, cls] += 1
                    obs_total_0[ya, xa] += 1
        except Exception as e:
            log(f"  Regime query failed: {e}")
            break

    # Detect regime
    alive, dead, new_s = 0, 0, 0
    for sy, sx in settle_cells:
        if obs_total_0[sy, sx] == 0:
            continue
        sp = obs_counts_0[sy, sx, 1] + obs_counts_0[sy, sx, 2]
        if sp > 0:
            alive += 1
        else:
            dead += 1
    for y in range(height):
        for x in range(width):
            if obs_total_0[y, x] == 0:
                continue
            cls = TERRAIN_TO_CLASS.get(int(ig0[y][x]), 0)
            if cls not in (1, 2) and ig0[y][x] not in STATIC_TERRAIN:
                if obs_counts_0[y, x, 1] + obs_counts_0[y, x, 2] > 0:
                    new_s += 1

    total_checked = alive + dead
    survival_rate = alive / max(1, total_checked)
    if survival_rate < 0.10 and new_s <= 2:
        regime = "extinction"
    elif new_s > total_checked * 0.5:
        regime = "growth"
    else:
        regime = "stable"

    log(f"  REGIME: {regime} (survival={survival_rate:.0%}, alive={alive}, dead={dead}, new={new_s})")

    # Step B: Complete seed 0 + overview seeds 1-4
    budget_info = session.get(f"{BASE}/astar-island/budget").json()
    remaining = budget_info["queries_max"] - budget_info["queries_used"]

    # Complete seed 0
    for vx, vy, vw, vh in viewports:
        if remaining <= 0:
            break
        if obs_total_0[vy, vx] > 0:
            continue
        try:
            obs = query_viewport(session, round_id, 0, vx, vy, vw, vh)
            for dy, row in enumerate(obs["grid"]):
                for dx, terrain in enumerate(row):
                    ya, xa = obs["viewport"]["y"] + dy, obs["viewport"]["x"] + dx
                    c = TERRAIN_TO_CLASS.get(terrain, 0)
                    obs_counts_0[ya, xa, c] += 1
                    obs_total_0[ya, xa] += 1
            remaining -= 1
        except Exception as e:
            log(f"  Seed 0 fill failed: {e}")
            break

    # Save seed 0
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    np.save(DATA_DIR / f"obs_counts_r{round_num}_seed0_overview.npy", obs_counts_0)
    np.save(DATA_DIR / f"obs_total_r{round_num}_seed0_overview.npy", obs_total_0)

    all_obs = {0: (obs_counts_0, obs_total_0)}

    # Overview seeds 1-4
    for seed_idx in range(1, seeds_count):
        if remaining <= 0:
            break
        grid = detail["initial_states"][seed_idx]["grid"]
        obs_counts = np.zeros((height, width, NUM_CLASSES))
        obs_total = np.zeros((height, width))

        for vx, vy, vw, vh in viewports:
            if remaining <= 0:
                break
            try:
                obs = query_viewport(session, round_id, seed_idx, vx, vy, vw, vh)
                for dy, row in enumerate(obs["grid"]):
                    for dx, terrain in enumerate(row):
                        ya, xa = obs["viewport"]["y"] + dy, obs["viewport"]["x"] + dx
                        c = TERRAIN_TO_CLASS.get(terrain, 0)
                        obs_counts[ya, xa, c] += 1
                        obs_total[ya, xa] += 1
                remaining -= 1
            except Exception as e:
                log(f"  Seed {seed_idx} failed: {e}")
                break

        np.save(DATA_DIR / f"obs_counts_r{round_num}_seed{seed_idx}_overview.npy", obs_counts)
        np.save(DATA_DIR / f"obs_total_r{round_num}_seed{seed_idx}_overview.npy", obs_total)
        all_obs[seed_idx] = (obs_counts, obs_total)
        covered = (obs_total > 0).sum()
        log(f"  Seed {seed_idx}: {covered}/{height*width} cells covered")

    # Save regime
    regime_info = {
        "regime": regime,
        "survival_rate": float(survival_rate),
        "growth_rate": float(new_s / max(1, total_checked)),
        "init_settlements": len(settle_cells),
        "survived": alive,
        "new_settlements": new_s,
    }
    with open(DATA_DIR / f"regime_r{round_num}.json", "w") as f:
        json.dump(regime_info, f, default=str)

    budget_info = session.get(f"{BASE}/astar-island/budget").json()
    log(f"  Budget: {budget_info['queries_used']}/{budget_info['queries_max']}")

    return all_obs, regime_info


def build_and_submit(session, round_id, detail, round_num, all_obs, regime_info, model):
    """Build predictions with V2 model + regime calibration, submit all seeds."""
    height, width = detail["map_height"], detail["map_width"]
    seeds_count = detail["seeds_count"]

    for seed_idx in range(seeds_count):
        grid = detail["initial_states"][seed_idx]["grid"]

        pred = model.predict_grid_with_obs(
            detail, seed_idx,
            obs_counts=all_obs[seed_idx][0] if seed_idx in all_obs else None,
            obs_total=all_obs[seed_idx][1] if seed_idx in all_obs else None,
            prior_strength=12.0,
        )

        # Regime calibration
        if regime_info["regime"] in ("death", "extinction"):
            for y in range(height):
                for x in range(width):
                    if grid[y][x] in STATIC_TERRAIN:
                        continue
                    cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)
                    if cls in (1, 2):
                        pred[y, x, 0] = 0.65
                        pred[y, x, 1] = 0.02
                        pred[y, x, 2] = 0.01
                        pred[y, x, 3] = 0.02
                        pred[y, x, 4] = 0.28
                        pred[y, x, 5] = 0.01
                    pred[y, x, 1] *= 0.05
                    pred[y, x, 2] *= 0.05

        # Port constraint
        ocean_adj = compute_ocean_adjacency(grid, height, width)
        for y in range(height):
            for x in range(width):
                if ocean_adj[y, x] == 0:
                    pred[y, x, 2] = PROB_FLOOR

        # Temperature scaling
        pred = pred ** (1.0 / 1.12)

        # Collapse thresholding
        for y in range(height):
            for x in range(width):
                if grid[y][x] in STATIC_TERRAIN:
                    continue
                probs = pred[y, x]
                mask = probs < 0.016
                if mask.any() and not mask.all():
                    probs[mask] = PROB_FLOOR
                    pred[y, x] = probs / probs.sum()

        # Spatial smoothing
        smoothed = np.copy(pred)
        for cls in range(NUM_CLASSES):
            smoothed[:, :, cls] = gaussian_filter(pred[:, :, cls], sigma=0.3)
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
        obs_str = f", {int(all_obs[seed_idx][1].sum())} obs" if seed_idx in all_obs else ""
        log(f"  Seed {seed_idx}: conf {avg_conf:.3f}{obs_str}")

        # Submit
        for attempt in range(3):
            try:
                resp = session.post(f"{BASE}/astar-island/submit", json={
                    "round_id": round_id,
                    "seed_index": seed_idx,
                    "prediction": pred.tolist(),
                })
                resp.raise_for_status()
                log(f"  Seed {seed_idx} SUBMITTED")
                break
            except requests.HTTPError as e:
                if e.response and e.response.status_code == 429:
                    time.sleep(2)
                    continue
                log(f"  Seed {seed_idx} FAILED: {e}")
                break


def train_model(session):
    """Train V2 model on all cached ground truth."""
    rounds_data = load_cached_rounds()

    # Also try caching any newly completed rounds
    try:
        api_rounds = session.get(f"{BASE}/astar-island/rounds").json()
        completed = [r for r in api_rounds if r["status"] == "completed"]
        cached_nums = {rd["round_number"] for rd in rounds_data}
        for r in completed:
            if r["round_number"] not in cached_nums:
                log(f"  Caching new round {r['round_number']}...")
                cache_round(session, r)
        rounds_data = load_cached_rounds()
    except Exception as e:
        log(f"  Cache update failed: {e}")

    model = NeighborhoodModelV2()
    for rd in rounds_data:
        model.add_training_data(rd)
    model.finalize()
    log(f"  Model: {model.total_cells} cells from {len(model.training_rounds)} rounds")
    return model


def run_cycle(session, state):
    """One cycle: check rounds, observe/submit if needed, cache completed."""
    rounds = session.get(f"{BASE}/astar-island/rounds").json()

    # Find active round
    active = None
    for r in rounds:
        if r["status"] == "active":
            active = r
            break

    # Cache newly completed rounds
    completed = [r for r in rounds if r["status"] == "completed"]
    for r in completed:
        rn = r["round_number"]
        if rn not in state["cached_rounds"]:
            try:
                log(f"Caching R{rn} ground truth...")
                cache_round(session, r)
                state["cached_rounds"].append(rn)
                save_state(state)
            except Exception as e:
                log(f"  Cache R{rn} failed: {e}")

    if active is None:
        log("No active round.")
        return

    round_id = active["id"]
    round_num = active["round_number"]
    closes = datetime.fromisoformat(active["closes_at"])
    now = datetime.now(timezone.utc)
    remaining_min = (closes - now).total_seconds() / 60

    log(f"R{round_num} active, {remaining_min:.0f} min left, weight={active['round_weight']:.4f}")

    # Check if already submitted this round
    if round_num in state["submitted_rounds"]:
        log(f"  R{round_num} already submitted.")

        # Retrain and resubmit if we have new cached rounds
        n_cached = len(load_cached_rounds())
        if n_cached > state.get("last_model_rounds", 0) and remaining_min > 15:
            log(f"  New training data available ({n_cached} vs {state.get('last_model_rounds', 0)} rounds). Retraining...")
            model = train_model(session)
            state["last_model_rounds"] = n_cached
            save_state(state)

            # Load existing observations
            detail = session.get(f"{BASE}/astar-island/rounds/{round_id}").json()
            all_obs = load_existing_observations(round_num, detail["seeds_count"])

            regime_path = DATA_DIR / f"regime_r{round_num}.json"
            if regime_path.exists():
                with open(regime_path) as f:
                    regime_info = json.load(f)
            else:
                regime_info = {"regime": "stable", "survival_rate": 0.4}

            log(f"  Resubmitting R{round_num} with retrained model...")
            build_and_submit(session, round_id, detail, round_num, all_obs, regime_info, model)
            log(f"  R{round_num} resubmitted.")
        return

    # New round: full pipeline
    log(f"  NEW ROUND {round_num}! Starting full pipeline...")

    # Train model on all available data
    model = train_model(session)
    state["last_model_rounds"] = len(load_cached_rounds())

    # Get round details
    detail = session.get(f"{BASE}/astar-island/rounds/{round_id}").json()

    # Observe all seeds
    try:
        all_obs, regime_info = observe_all_seeds(session, round_id, detail, round_num)
    except Exception as e:
        log(f"  Observation failed: {e}")
        traceback.print_exc()
        all_obs = {}
        regime_info = {"regime": "stable", "survival_rate": 0.4}

    # Build and submit
    try:
        build_and_submit(session, round_id, detail, round_num, all_obs, regime_info, model)
        state["submitted_rounds"].append(round_num)
        save_state(state)
        log(f"  R{round_num} SUBMITTED SUCCESSFULLY")
    except Exception as e:
        log(f"  Submission failed: {e}")
        traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(description="Astar Island Overnight Runner")
    parser.add_argument("--token", required=True)
    parser.add_argument("--continuous", action="store_true",
                        help="Run in loop (5 min interval)")
    parser.add_argument("--interval", type=int, default=300,
                        help="Seconds between checks (default: 300)")
    args = parser.parse_args()

    session = get_session(args.token)
    state = load_state()

    log("=" * 60)
    log("OVERNIGHT RUNNER STARTED")
    log(f"  State: submitted={state['submitted_rounds']}, cached={state['cached_rounds']}")
    log("=" * 60)

    if args.continuous:
        while True:
            try:
                run_cycle(session, state)
            except Exception as e:
                log(f"CYCLE ERROR: {e}")
                traceback.print_exc()
            log(f"  Sleeping {args.interval}s...")
            time.sleep(args.interval)
    else:
        run_cycle(session, state)


if __name__ == "__main__":
    main()
