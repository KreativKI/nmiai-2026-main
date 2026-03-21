#!/usr/bin/env python3
"""
Autonomous Round Handler v4 for Astar Island.

Single file that runs 24/7 on GCP. Handles everything:
1. Detects rounds (active/completed)
2. Observes (deep stack, rotating seed)
3. Trains V4 (32-feature LightGBM from master dataset)
4. Submits predictions
5. After round: caches GT, downloads replay, rebuilds dataset, calibrates
6. Resubmits if churn finds better params during window

Usage:
  python overnight_v4.py --token TOKEN --continuous
"""

import argparse
import json
import time
import traceback
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import requests
import lightgbm as lgb

import sys
sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    load_cached_rounds, get_session, cache_round,
    TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, PROB_FLOOR, BASE,
)
from build_dataset import (
    build_master_dataset, FEATURE_NAMES, extract_cell_features,
    _compute_trajectory_features,
)

OCEAN_RAW = {10, 11}
SKIP_CELLS = STATIC_TERRAIN | OCEAN_RAW  # cells that never change class
DATA_DIR = Path(__file__).parent / "data"
REPLAY_DIR = DATA_DIR / "replays"
STATE_FILE = Path(__file__).parent.parent / "overnight_v4_state.json"
LOG_FILE = Path.home() / "overnight_v4.log"
PARAMS_FILE = DATA_DIR / "brain_v4_params.json"
CAL_FILE = DATA_DIR / "calibration_v4_32feat.json"

COMPETITION_END = datetime(2026, 3, 22, 14, 0, 0, tzinfo=timezone.utc)

# Default params (overridden by churn if brain_v4_params.json exists)
DEFAULT_PARAMS = {
    "n_estimators": 50, "num_leaves": 31, "learning_rate": 0.05,
    "min_child_samples": 20, "subsample": 0.8, "colsample_bytree": 0.8,
    "alpha_dirichlet": 20.0,
}


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        print(line, file=sys.stderr, flush=True)


# -- State --

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"submitted_rounds": [], "cached_rounds": [], "deep_seed_offset": 0}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def load_lgb_params():
    """Load best LightGBM params from churn, or use defaults."""
    if PARAMS_FILE.exists():
        try:
            with open(PARAMS_FILE) as f:
                p = json.load(f)
            return {k: p[k] for k in DEFAULT_PARAMS if k in p}
        except Exception:
            pass
    return DEFAULT_PARAMS.copy()


# -- Observation --

def accumulate_obs(obs, obs_counts, obs_total):
    """Accumulate a viewport observation into counts and totals."""
    vp = obs["viewport"]
    for dy, row in enumerate(obs["grid"]):
        for dx, terrain in enumerate(row):
            ya, xa = vp["y"] + dy, vp["x"] + dx
            obs_counts[ya, xa, TERRAIN_TO_CLASS.get(terrain, 0)] += 1
            obs_total[ya, xa] += 1


def query_viewport(session, round_id, seed_idx, x, y, w=15, h=15):
    resp = session.post(f"{BASE}/astar-island/simulate", json={
        "round_id": round_id, "seed_index": seed_idx,
        "viewport_x": x, "viewport_y": y, "viewport_w": w, "viewport_h": h,
    })
    resp.raise_for_status()
    time.sleep(0.22)
    return resp.json()


def classify_regime(alive, checked):
    """Classify round regime from smell test survival ratio."""
    survival = alive / max(1, checked)
    if survival < 0.15:
        return "death"
    elif survival > 0.60:
        return "growth"
    else:
        return "stable"


def observe_round(session, round_id, detail, round_num, deep_seed):
    """Smell test + deep stack one seed. Returns (obs_counts, obs_total, regime)."""
    h, w = detail["map_height"], detail["map_width"]
    ig = detail["initial_states"][deep_seed]["grid"]

    obs_counts = np.zeros((h, w, NUM_CLASSES))
    obs_total = np.zeros((h, w))

    # Viewport tiling
    viewports = []
    for vy in range(0, h, 15):
        for vx in range(0, w, 15):
            viewports.append((vx, vy, min(15, w - vx), min(15, h - vy)))

    # Smell test: up to 5 queries on settlement/port cells
    settle_cells = [(y, x) for y in range(h) for x in range(w)
                    if TERRAIN_TO_CLASS.get(int(ig[y][x]), 0) in (1, 2)]
    sample_indices = np.linspace(0, max(0, len(settle_cells) - 1), min(5, len(settle_cells)), dtype=int)
    test_cells = [settle_cells[i] for i in sample_indices]

    test_vps = []
    used = set()
    for sy, sx in test_cells:
        vx = max(0, min(sx - 7, w - 15))
        vy = max(0, min(sy - 7, h - 15))
        if (vx, vy) not in used:
            used.add((vx, vy))
            test_vps.append((vx, vy, 15, 15))

    for vx, vy, vw, vh in test_vps[:5]:
        try:
            obs = query_viewport(session, round_id, deep_seed, vx, vy, vw, vh)
            accumulate_obs(obs, obs_counts, obs_total)
        except Exception as e:
            log(f"  Smell query failed: {e}")
            break

    alive = sum(1 for sy, sx in test_cells if obs_total[sy, sx] > 0
                and (obs_counts[sy, sx, 1] + obs_counts[sy, sx, 2]) > 0)
    dead = sum(1 for sy, sx in test_cells if obs_total[sy, sx] > 0
               and (obs_counts[sy, sx, 1] + obs_counts[sy, sx, 2]) == 0)
    regime = classify_regime(alive, alive + dead)
    log(f"  Smell: {alive}/{alive + dead} alive = {regime}")

    # Deep stack: all remaining queries on deep_seed
    budget = {"queries_max": 50, "queries_used": 5}
    for _retry in range(3):
        try:
            resp = session.get(f"{BASE}/astar-island/budget")
            resp.raise_for_status()
            budget = resp.json()
            break
        except Exception as e:
            log(f"  Budget check failed (attempt {_retry+1}): {e}")
            time.sleep(2)
    rem = budget["queries_max"] - budget["queries_used"]

    # Pass 1: fill gaps (cells with no observations yet)
    for vx, vy, vw, vh in viewports:
        if rem <= 0:
            break
        if obs_total[vy, vx] > 0:
            continue
        try:
            obs = query_viewport(session, round_id, deep_seed, vx, vy, vw, vh)
            accumulate_obs(obs, obs_counts, obs_total)
            rem -= 1
        except Exception:
            break

    # Pass 2+: multi-sample (stack additional observations)
    while rem > 0:
        queries_this_pass = 0
        for vx, vy, vw, vh in viewports:
            if rem <= 0:
                break
            try:
                obs = query_viewport(session, round_id, deep_seed, vx, vy, vw, vh)
                accumulate_obs(obs, obs_counts, obs_total)
                rem -= 1
                queries_this_pass += 1
            except Exception as e:
                log(f"  Deep stack query error: {e}")
                time.sleep(1)
                continue
        if queries_this_pass == 0:
            break

    avg_obs = obs_total[obs_total > 0].mean() if (obs_total > 0).any() else 0
    log(f"  Deep stack seed {deep_seed}: {(obs_total > 0).sum()}/1600 cells, "
        f"avg {avg_obs:.1f} obs/cell")

    np.save(DATA_DIR / f"obs_counts_r{round_num}_seed{deep_seed}_stacked.npy", obs_counts)
    np.save(DATA_DIR / f"obs_total_r{round_num}_seed{deep_seed}_stacked.npy", obs_total)

    return obs_counts, obs_total, regime


# -- Prediction --

def count_terrain_classes(grid, h, w):
    """Count settlements and ports in initial grid (single pass)."""
    total_s, total_p = 0, 0
    for y in range(h):
        for x in range(w):
            cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)
            if cls == 1:
                total_s += 1
            elif cls == 2:
                total_p += 1
    return total_s, total_p


def predict_and_submit(session, round_id, detail, round_num, deep_seed,
                       obs_counts, obs_total, regime):
    """Train V4 on 32-feat master dataset, predict all seeds, submit."""
    h, w = detail["map_height"], detail["map_width"]
    seeds_count = detail["seeds_count"]

    lgb_params = load_lgb_params()
    alpha = lgb_params.pop("alpha_dirichlet", 20)
    lgb_params["objective"] = "regression"
    lgb_params["metric"] = "mse"
    lgb_params["verbose"] = -1

    # Train one regressor per terrain class on master dataset
    rounds_data = load_cached_rounds()
    X, Y, _ = build_master_dataset(rounds_data)
    log(f"  Training: {X.shape[0]} rows, {X.shape[1]} features, "
        f"n_est={lgb_params.get('n_estimators', 50)}")

    models = {}
    for cls in range(NUM_CLASSES):
        m = lgb.LGBMRegressor(**lgb_params)
        m.fit(X, Y[:, cls])
        models[cls] = m

    # Round-level features (computed once from seed 0)
    total_s, total_p = count_terrain_classes(detail["initial_states"][0]["grid"], h, w)

    regime_flags = {
        "regime_death": 1 if regime == "death" else 0,
        "regime_growth": 1 if regime == "growth" else 0,
        "regime_stable": 1 if regime == "stable" else 0,
    }

    for seed_idx in range(seeds_count):
        ig = detail["initial_states"][seed_idx]["grid"]

        # Load replay if available (completed rounds only, free API call)
        replay_path = REPLAY_DIR / f"r{round_num}_seed{seed_idx}.json"
        replay_data = None
        if replay_path.exists():
            try:
                with open(replay_path) as f:
                    replay_data = json.load(f)
            except Exception:
                pass
        traj = _compute_trajectory_features(replay_data, total_s)
        round_feats = {**regime_flags, "total_settlements": total_s, "total_ports": total_p, **traj}

        # Extract features for dynamic cells
        cells, coords = [], []
        for y in range(h):
            for x in range(w):
                if int(ig[y][x]) in STATIC_TERRAIN:
                    continue
                fd = extract_cell_features(ig, y, x, h, w, replay_data=replay_data)
                fd.update(round_feats)
                cells.append([fd.get(n, 0) for n in FEATURE_NAMES])
                coords.append((y, x))

        # Predict dynamic cells
        pred = np.zeros((h, w, NUM_CLASSES))
        if cells:
            Xp = np.array(cells, dtype=np.float32)
            coord_y = [c[0] for c in coords]
            coord_x = [c[1] for c in coords]
            for cls in range(NUM_CLASSES):
                pred[coord_y, coord_x, cls] = models[cls].predict(Xp)

        # Static cells: near-certain prediction
        for y in range(h):
            for x in range(w):
                if int(ig[y][x]) in STATIC_TERRAIN:
                    cls = TERRAIN_TO_CLASS.get(int(ig[y][x]), 0)
                    pred[y, x] = PROB_FLOOR
                    pred[y, x, cls] = 1.0 - (NUM_CLASSES - 1) * PROB_FLOOR

        # Dirichlet blending on deep-stacked seed
        if seed_idx == deep_seed:
            for y in range(h):
                for x in range(w):
                    if obs_total[y, x] == 0:
                        continue
                    a = alpha * pred[y, x]
                    a = np.maximum(a, PROB_FLOOR)
                    pred[y, x] = (a + obs_counts[y, x]) / (a.sum() + obs_total[y, x])

        # Hard constraints from deep analysis (validated on 75 replays)
        for y in range(h):
            for x in range(w):
                if int(ig[y][x]) in SKIP_CELLS:
                    continue
                # H4: Ports ONLY form on coastal cells (1834/1834 = 100%)
                has_ocean = any(
                    0 <= y + dy < h and 0 <= x + dx < w
                    and int(ig[y + dy][x + dx]) in OCEAN_RAW
                    for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                    if (dy, dx) != (0, 0)
                )
                if not has_ocean:
                    pred[y, x, 2] = PROB_FLOOR
                # H5: Ruin never dominant at year 50 (avg lifespan 1 year)
                pred[y, x, 3] = min(pred[y, x, 3], 0.05)

        pred = np.maximum(pred, PROB_FLOOR)
        pred /= pred.sum(axis=-1, keepdims=True)

        # Submit with retry on rate limit
        conf = pred.max(axis=-1).mean()
        tag = "deep-stacked" if seed_idx == deep_seed else "model-only"
        for attempt in range(5):
            try:
                resp = session.post(f"{BASE}/astar-island/submit", json={
                    "round_id": round_id, "seed_index": seed_idx,
                    "prediction": pred.tolist(),
                })
                resp.raise_for_status()
                log(f"  Seed {seed_idx}: SUBMITTED ({tag}, conf={conf:.3f})")
                break
            except requests.HTTPError as e:
                if e.response and e.response.status_code == 429:
                    time.sleep(3 * (attempt + 1))
                    continue
                log(f"  Seed {seed_idx}: FAILED - {e}")
                break
        time.sleep(0.5)


# -- Post-Round Pipeline --

def post_round_pipeline(session, round_data, state):
    """After a round closes: cache GT, download replay, rebuild dataset, calibrate."""
    rn = round_data["round_number"]
    if rn in state["cached_rounds"]:
        return

    log(f"  Post-round pipeline for R{rn}...")

    # 1. Cache ground truth
    try:
        cache_round(session, round_data)
        state["cached_rounds"].append(rn)
        log(f"  R{rn} ground truth cached")
    except Exception as e:
        log(f"  R{rn} cache failed: {e}")
        return

    # 2. Download replays
    REPLAY_DIR.mkdir(parents=True, exist_ok=True)
    for si in range(5):
        path = REPLAY_DIR / f"r{rn}_seed{si}.json"
        if path.exists():
            continue
        try:
            r = session.post(f"{BASE}/astar-island/replay", json={
                "round_id": round_data["id"], "seed_index": si
            })
            if r.status_code == 200:
                with open(path, "w") as f:
                    json.dump(r.json(), f)
            time.sleep(1)
        except Exception:
            pass
    log(f"  R{rn} replays downloaded")

    # 3. Rebuild master dataset
    try:
        rounds_data = load_cached_rounds()
        X, Y, _ = build_master_dataset(rounds_data)
        np.savez_compressed(DATA_DIR / "master_dataset.npz", X=X, Y=Y)
        log(f"  Master dataset rebuilt: {X.shape[0]} rows")
    except Exception as e:
        log(f"  Dataset rebuild failed: {e}")

    # 4. Calibrate: compare backtest vs actual
    try:
        my_rounds = session.get(f"{BASE}/astar-island/my-rounds").json()
        for rd in my_rounds:
            if rd.get("round_number") == rn:
                actual = rd.get("round_score")
                rank = rd.get("rank")
                weighted = actual * rd.get("round_weight", 0) if actual else 0
                log(f"  R{rn} SCORE: {actual} rank={rank} weighted={weighted:.1f}")

                if actual and CAL_FILE.exists():
                    with open(CAL_FILE) as f:
                        cal = json.load(f)
                    cal["rounds"] = [r for r in cal.get("rounds", []) if r["round"] != rn]
                    cal["rounds"].append({
                        "round": rn, "actual": actual,
                        "regime": "unknown",
                    })
                    with open(CAL_FILE, "w") as f:
                        json.dump(cal, f, indent=2)
                break
    except Exception as e:
        log(f"  Calibration update failed: {e}")

    save_state(state)


# -- Main Loop --

def parse_closes_at(closes_at_str):
    """Parse ISO timestamp string to timezone-aware datetime."""
    closes = datetime.fromisoformat(closes_at_str.replace("Z", "+00:00"))
    if closes.tzinfo is None:
        closes = closes.replace(tzinfo=timezone.utc)
    return closes


def run_cycle(session, state):
    """One cycle: check rounds, submit, collect data."""
    now = datetime.now(timezone.utc)
    if now >= COMPETITION_END:
        log("COMPETITION ENDED.")
        return False

    try:
        resp = session.get(f"{BASE}/astar-island/rounds")
        resp.raise_for_status()
        rounds = resp.json()
    except Exception as e:
        log(f"  API error fetching rounds: {e}")
        return True

    # Phase A: collect data from completed rounds
    for r in rounds:
        if r["status"] == "completed" and r["round_number"] not in state["cached_rounds"]:
            try:
                post_round_pipeline(session, r, state)
            except Exception as e:
                log(f"  Pipeline R{r['round_number']} failed: {e}")

    # Phase B: handle active round
    active = next((r for r in rounds if r["status"] == "active"), None)
    if active is None:
        log("No active round. Waiting...")
        return True

    round_id = active["id"]
    round_num = active["round_number"]
    closes = parse_closes_at(active["closes_at"])
    remaining = (closes - now).total_seconds() / 60

    log(f"R{round_num} active, {remaining:.0f} min left, weight={active['round_weight']:.4f}")

    if round_num in state["submitted_rounds"]:
        # Already submitted: check for resubmit opportunity
        if remaining > 30 and PARAMS_FILE.exists():
            mtime = PARAMS_FILE.stat().st_mtime
            if mtime > state.get("last_submit_time", 0):
                log(f"  Churn found new params, resubmitting...")
                detail = session.get(f"{BASE}/astar-island/rounds/{round_id}").json()
                deep_seed = (round_num + state.get("deep_seed_offset", 0)) % 5

                oc_path = DATA_DIR / f"obs_counts_r{round_num}_seed{deep_seed}_stacked.npy"
                ot_path = DATA_DIR / f"obs_total_r{round_num}_seed{deep_seed}_stacked.npy"
                if oc_path.exists() and ot_path.exists():
                    oc = np.load(oc_path)
                    ot = np.load(ot_path)
                    regime = state.get(f"regime_r{round_num}", "stable")
                    predict_and_submit(session, round_id, detail, round_num,
                                       deep_seed, oc, ot, regime)
                    state["last_submit_time"] = time.time()
                    save_state(state)
                    log(f"  R{round_num} RESUBMITTED with new churn params")
        else:
            log(f"  R{round_num} already submitted.")
        return True

    # New round: observe + predict + submit
    log(f"  NEW ROUND {round_num}!")
    detail = session.get(f"{BASE}/astar-island/rounds/{round_id}").json()

    deep_seed = (round_num + state.get("deep_seed_offset", 0)) % 5
    log(f"  Deep stack seed: {deep_seed}")

    try:
        oc, ot, regime = observe_round(session, round_id, detail, round_num, deep_seed)
        state[f"regime_r{round_num}"] = regime
        predict_and_submit(session, round_id, detail, round_num, deep_seed, oc, ot, regime)
        state["submitted_rounds"].append(round_num)
        state["last_submit_time"] = time.time()
        save_state(state)
        log(f"  R{round_num} SUBMITTED (V4 32-feat, deep stack seed {deep_seed})")
    except Exception as e:
        log(f"  R{round_num} FAILED: {e}")
        traceback.print_exc()

    return True


def main():
    parser = argparse.ArgumentParser(description="Autonomous Round Handler v4")
    parser.add_argument("--token", required=True)
    parser.add_argument("--continuous", action="store_true")
    parser.add_argument("--interval", type=int, default=300)
    args = parser.parse_args()

    session = get_session(args.token)
    state = load_state()

    log("=" * 60)
    log("OVERNIGHT V4 -- 32-FEATURE AUTONOMOUS")
    log(f"  Submitted: {state['submitted_rounds']}")
    log(f"  Cached: {state['cached_rounds']}")
    params = load_lgb_params()
    log(f"  LGB params: n_est={params.get('n_estimators')}, leaves={params.get('num_leaves')}")
    log("=" * 60)

    if args.continuous:
        while True:
            try:
                keep_going = run_cycle(session, state)
                if not keep_going:
                    break
            except Exception as e:
                log(f"CYCLE ERROR: {e}")
                traceback.print_exc()
            log(f"  Sleeping {args.interval}s...")
            time.sleep(args.interval)
    else:
        run_cycle(session, state)


if __name__ == "__main__":
    main()
