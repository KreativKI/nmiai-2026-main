#!/usr/bin/env python3
"""
Autonomous Round Handler v5 for Astar Island.

Key change from v4: multi-seed observation strategy.
Instead of deep-stacking 50 queries on 1 seed, spreads 9 queries per seed
across all 5 seeds for full grid coverage. No seed runs blind.

Usage:
  python overnight_v5.py --token TOKEN --continuous
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
SKIP_CELLS = STATIC_TERRAIN | OCEAN_RAW
DATA_DIR = Path(__file__).parent / "data"
REPLAY_DIR = DATA_DIR / "replays"
STATE_FILE = Path(__file__).parent.parent / "overnight_v5_state.json"
LOG_FILE = Path.home() / "overnight_v5.log"
PARAMS_FILE = DATA_DIR / "brain_v4_params.json"
CAL_FILE = DATA_DIR / "calibration_v5.json"

COMPETITION_END = datetime(2026, 3, 22, 14, 0, 0, tzinfo=timezone.utc)

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
    return {"submitted_rounds": [], "cached_rounds": []}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def load_lgb_params():
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


def observe_round_v2(session, round_id, detail, round_num):
    """Observe ALL 5 seeds with full grid coverage (9 queries each)."""
    h, w = detail["map_height"], detail["map_width"]
    seeds_count = detail.get("seeds_count", 5)

    viewports = []
    for vy in range(0, h, 15):
        for vx in range(0, w, 15):
            viewports.append((vx, vy, min(15, w - vx), min(15, h - vy)))

    per_seed_obs = {}
    budget_used = 0

    for seed_idx in range(seeds_count):
        oc = np.zeros((h, w, NUM_CLASSES))
        ot = np.zeros((h, w))

        for vx, vy, vw, vh in viewports:
            if budget_used >= 50:
                break
            try:
                obs = query_viewport(session, round_id, seed_idx, vx, vy, vw, vh)
                accumulate_obs(obs, oc, ot)
                budget_used += 1
            except Exception as e:
                log(f"  Query failed seed {seed_idx} ({vx},{vy}): {e}")
                continue

        per_seed_obs[seed_idx] = (oc, ot)
        np.save(DATA_DIR / f"obs_counts_r{round_num}_seed{seed_idx}_full.npy", oc)
        np.save(DATA_DIR / f"obs_total_r{round_num}_seed{seed_idx}_full.npy", ot)
        covered = int((ot > 0).sum())
        log(f"  Seed {seed_idx}: {covered}/1600 cells covered ({budget_used} queries used)")

    # Extra queries on seed 0
    remaining = 50 - budget_used
    if remaining > 0 and 0 in per_seed_obs:
        oc0, ot0 = per_seed_obs[0]
        for i in range(remaining):
            if budget_used >= 50:
                break
            try:
                vx, vy, vw, vh = viewports[i % len(viewports)]
                obs = query_viewport(session, round_id, 0, vx, vy, vw, vh)
                accumulate_obs(obs, oc0, ot0)
                budget_used += 1
            except Exception:
                break
        log(f"  Seed 0 extra: {int(ot0.mean()):.1f} avg obs/cell ({budget_used} total queries)")

    # Compute per-seed growth ratios
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

    avg_growth = np.mean(growth_ratios)
    if avg_growth < 0.9:
        regime = "death"
    elif avg_growth > 1.4:
        regime = "growth"
    else:
        regime = "stable"

    log(f"  Multi-seed regime: {regime} (avg_growth={avg_growth:.2f}, "
        f"per_seed=[{', '.join(f'{g:.1f}' for g in growth_ratios)}])")

    return per_seed_obs, regime, growth_ratios


# -- Prediction --

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


def predict_and_submit_v2(session, round_id, detail, round_num,
                          per_seed_obs, regime, growth_ratios):
    """Train on master dataset, predict ALL seeds with per-seed obs data, submit."""
    h, w = detail["map_height"], detail["map_width"]
    seeds_count = detail["seeds_count"]

    lgb_params = load_lgb_params()
    base_alpha = lgb_params.pop("alpha_dirichlet", 20)
    lgb_params["objective"] = "regression"
    lgb_params["metric"] = "mse"
    lgb_params["verbose"] = -1

    rounds_data = load_cached_rounds()
    X, Y, _ = build_master_dataset(rounds_data)
    log(f"  Training: {X.shape[0]} rows, {X.shape[1]} features")

    models = {}
    for cls in range(NUM_CLASSES):
        m = lgb.LGBMRegressor(**lgb_params)
        m.fit(X, Y[:, cls])
        models[cls] = m

    total_s, total_p, init_forest = count_terrain_classes(
        detail["initial_states"][0]["grid"], h, w)

    # Per-regime Dirichlet alpha
    alpha = {"death": 5, "stable": 30, "growth": 15}.get(regime, base_alpha)

    regime_flags = {
        "regime_death": 1 if regime == "death" else 0,
        "regime_growth": 1 if regime == "growth" else 0,
        "regime_stable": 1 if regime == "stable" else 0,
    }

    for seed_idx in range(seeds_count):
        ig = detail["initial_states"][seed_idx]["grid"]

        # Load replay if available
        replay_path = REPLAY_DIR / f"r{round_num}_seed{seed_idx}.json"
        replay_data = None
        if replay_path.exists():
            try:
                with open(replay_path) as f:
                    replay_data = json.load(f)
            except Exception:
                pass
        traj = _compute_trajectory_features(replay_data, total_s)

        # Obs-derived proxy for this seed (works for ALL seeds now)
        if not replay_data and seed_idx in per_seed_obs:
            oc_s, ot_s = per_seed_obs[seed_idx]
            if (ot_s > 0).any():
                obs_argmax = oc_s.argmax(axis=2)
                observed = ot_s > 0
                obs_settle = int(((obs_argmax == 1) | (obs_argmax == 2))[observed].sum())
                # Use THIS seed's initial settlement count, not seed 0's
                seed_init_s = sum(1 for y in range(h) for x in range(w)
                                  if TERRAIN_TO_CLASS.get(int(ig[y][x]), 0) in (1, 2))
                obs_growth = obs_settle / max(seed_init_s, 1)
                if obs_growth <= 9.7:
                    traj["settle_growth_y25"] = obs_growth
                    traj["settle_growth_y10"] = min(obs_growth, 4.1)

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

        # Dirichlet blending on THIS seed's observations
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
        skip_cells = STATIC_TERRAIN | OCEAN_RAW
        for y in range(h):
            for x in range(w):
                if int(ig[y][x]) in skip_cells:
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

        pred = np.maximum(pred, PROB_FLOOR)
        pred /= pred.sum(axis=-1, keepdims=True)

        conf = pred.max(axis=-1).mean()
        has_obs = "obs" if seed_idx in per_seed_obs else "blind"
        for attempt in range(5):
            try:
                resp = session.post(f"{BASE}/astar-island/submit", json={
                    "round_id": round_id, "seed_index": seed_idx,
                    "prediction": pred.tolist(),
                })
                resp.raise_for_status()
                log(f"  Seed {seed_idx}: SUBMITTED ({has_obs}, conf={conf:.3f})")
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
    rn = round_data["round_number"]
    if rn in state["cached_rounds"]:
        return

    log(f"  Post-round pipeline for R{rn}...")

    try:
        cache_round(session, round_data)
        state["cached_rounds"].append(rn)
        log(f"  R{rn} ground truth cached")
    except Exception as e:
        log(f"  R{rn} cache failed: {e}")
        return

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

    try:
        rounds_data = load_cached_rounds()
        X, Y, _ = build_master_dataset(rounds_data)
        np.savez_compressed(DATA_DIR / "master_dataset.npz", X=X, Y=Y)
        log(f"  Master dataset rebuilt: {X.shape[0]} rows")
    except Exception as e:
        log(f"  Dataset rebuild failed: {e}")

    try:
        my_rounds = session.get(f"{BASE}/astar-island/my-rounds").json()
        for rd in my_rounds:
            if rd.get("round_number") == rn:
                actual = rd.get("round_score")
                rank = rd.get("rank")
                weighted = actual * rd.get("round_weight", 0) if actual else 0
                log(f"  R{rn} SCORE: {actual} rank={rank} weighted={weighted:.1f}")
                break
    except Exception as e:
        log(f"  Score fetch failed: {e}")

    save_state(state)


# -- Main Loop --

def parse_closes_at(closes_at_str):
    closes = datetime.fromisoformat(closes_at_str.replace("Z", "+00:00"))
    if closes.tzinfo is None:
        closes = closes.replace(tzinfo=timezone.utc)
    return closes


def run_cycle(session, state):
    now = datetime.now(timezone.utc)
    if now >= COMPETITION_END:
        log("COMPETITION ENDED.")
        return False

    try:
        resp = session.get(f"{BASE}/astar-island/rounds")
        resp.raise_for_status()
        rounds = resp.json()
    except Exception as e:
        log(f"  API error: {e}")
        return True

    for r in rounds:
        if r["status"] == "completed" and r["round_number"] not in state["cached_rounds"]:
            try:
                post_round_pipeline(session, r, state)
            except Exception as e:
                log(f"  Pipeline R{r['round_number']} failed: {e}")

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
        # Check for replay resubmit opportunity
        if remaining > 10:
            replay_exists = (REPLAY_DIR / f"r{round_num}_seed0.json").exists()
            obs_exists = (DATA_DIR / f"obs_counts_r{round_num}_seed0_full.npy").exists()
            if replay_exists and obs_exists and not state.get(f"replay_resubmit_r{round_num}"):
                log(f"  Replay data available, resubmitting with full features...")
                detail = session.get(f"{BASE}/astar-island/rounds/{round_id}").json()
                per_seed_obs = {}
                for si in range(5):
                    oc_path = DATA_DIR / f"obs_counts_r{round_num}_seed{si}_full.npy"
                    ot_path = DATA_DIR / f"obs_total_r{round_num}_seed{si}_full.npy"
                    if oc_path.exists() and ot_path.exists():
                        per_seed_obs[si] = (np.load(oc_path), np.load(ot_path))
                regime = state.get(f"regime_r{round_num}", "stable")
                growth_ratios = state.get(f"growth_ratios_r{round_num}", [1.0] * 5)
                predict_and_submit_v2(session, round_id, detail, round_num,
                                      per_seed_obs, regime, growth_ratios)
                state[f"replay_resubmit_r{round_num}"] = True
                save_state(state)
                log(f"  R{round_num} RESUBMITTED with replay-enhanced features")
        else:
            log(f"  R{round_num} already submitted.")
        return True

    # New round
    log(f"  NEW ROUND {round_num}! (v5 multi-seed)")
    detail = session.get(f"{BASE}/astar-island/rounds/{round_id}").json()

    try:
        per_seed_obs, regime, growth_ratios = observe_round_v2(
            session, round_id, detail, round_num)
        state[f"regime_r{round_num}"] = regime
        state[f"growth_ratios_r{round_num}"] = [round(float(g), 2) for g in growth_ratios]
        predict_and_submit_v2(session, round_id, detail, round_num,
                              per_seed_obs, regime, growth_ratios)
        state["submitted_rounds"].append(round_num)
        save_state(state)
        log(f"  R{round_num} SUBMITTED (v5 multi-seed, regime={regime})")
    except Exception as e:
        log(f"  R{round_num} FAILED: {e}")
        traceback.print_exc()

    return True


def main():
    parser = argparse.ArgumentParser(description="Autonomous Round Handler v5")
    parser.add_argument("--token", required=True)
    parser.add_argument("--continuous", action="store_true")
    parser.add_argument("--interval", type=int, default=300)
    args = parser.parse_args()

    session = get_session(args.token)
    state = load_state()

    log("=" * 60)
    log("OVERNIGHT V5 -- MULTI-SEED OBSERVATION")
    log(f"  Features: {len(FEATURE_NAMES)}")
    log(f"  Strategy: 9 queries/seed x 5 seeds + 5 extra on seed 0")
    log(f"  Submitted: {state['submitted_rounds']}")
    log(f"  Cached: {state['cached_rounds']}")
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
