#!/usr/bin/env python3
"""
Self-Improving Overnight Runner v2 for Astar Island.

Runs Chef v8 every round, then improves Brain V3 between rounds.

Cycle:
1. DETECT round state (active/completed/scoring)
2. If new round: Chef v8 pipeline (smell test + observe + predict + submit)
3. If round just closed: self-improvement loop
   a. Cache ground truth
   b. Retrain Brain on ALL rounds
   c. Re-fit per-terrain alphas (scipy.optimize)
   d. Re-fit entropy-aware temperatures
   e. Backtest new vs old Brain
   f. Deploy if better
4. Sleep 5 min, repeat

Usage:
  python overnight_v2.py --token TOKEN                  # Single cycle
  python overnight_v2.py --token TOKEN --continuous      # Loop until competition ends
  python overnight_v2.py --token TOKEN --test-improve    # Test self-improvement on cached data
"""

import argparse
import json
import os
import tempfile
import time
import traceback
from pathlib import Path
from datetime import datetime, timezone, timedelta

import numpy as np
import requests
from scipy.optimize import minimize
from scipy.ndimage import gaussian_filter

import sys
sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    load_cached_rounds, score_prediction, get_session, cache_round,
    TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, PROB_FLOOR, CLASS_NAMES, BASE,
)
from regime_model import RegimeModel, classify_round

DATA_DIR = Path(__file__).parent / "data"
STATE_FILE = Path(__file__).parent.parent / "overnight_state.json"
LOG_FILE = Path.home() / "overnight_v2.log"
PARAMS_FILE = DATA_DIR / "brain_v3_params.json"

COMPETITION_END = datetime(2026, 3, 22, 14, 0, 0, tzinfo=timezone.utc)


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    # Write only to log file (stdout redirected there by nohup, avoid duplicates)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        print(line, flush=True)


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"submitted_rounds": [], "cached_rounds": [], "improvements": [],
            "last_model_rounds": 0}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def load_params():
    defaults = ({0: 8.0, 1: 4.0, 2: 3.0, 3: 3.0, 4: 10.0, 5: 50.0},
                {"low": 0.9, "mid": 1.1, "high": 1.3})
    if PARAMS_FILE.exists():
        for attempt in range(3):
            try:
                with open(PARAMS_FILE) as f:
                    p = json.load(f)
                alphas = {int(k): v for k, v in p.get("alphas", {}).items()}
                temps = p.get("temps", {"low": 0.9, "mid": 1.1, "high": 1.3})
                return alphas, temps
            except (json.JSONDecodeError, ValueError):
                if attempt < 2:
                    time.sleep(0.1)  # Brief wait for atomic rename to complete
                    continue
                log("  WARNING: brain_v3_params.json corrupt, using defaults")
                return defaults
    return defaults


def save_params(alphas, temps, score, baseline):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    params = {
        "alphas": {str(k): round(float(v), 2) for k, v in alphas.items()},
        "temps": {k: round(float(v), 3) for k, v in temps.items()},
        "v3_score": round(float(score), 2),
        "baseline": round(float(baseline), 2),
        "delta": round(float(score - baseline), 2),
        "fitted_at": datetime.now(timezone.utc).isoformat(),
    }
    # Atomic write: write to temp file then rename to avoid partial reads
    fd, tmp_path = tempfile.mkstemp(dir=str(DATA_DIR), suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(params, f, indent=2)
        os.replace(tmp_path, str(PARAMS_FILE))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ──────────────────────────────────────────────
# Chef v8: Smell Test + Observe + Predict + Submit
# ──────────────────────────────────────────────

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


def run_chef_v8(session, round_id, detail, round_num):
    """Full Chef v8 pipeline: smell test + observe all seeds + predict + submit."""
    height, width = detail["map_height"], detail["map_width"]
    seeds_count = detail["seeds_count"]

    # Check budget
    budget = session.get(f"{BASE}/astar-island/budget").json()
    remaining = budget["queries_max"] - budget["queries_used"]
    if remaining <= 0:
        log("  Budget exhausted. Loading existing observations...")
        return _load_existing_obs(round_num, seeds_count)

    ig0 = detail["initial_states"][0]["grid"]
    settle_cells = find_settlement_cells(ig0, height, width)
    viewports = tile_viewports(height, width, 15)

    # ── SMELL TEST ──
    log("Phase 1: Smell test")
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
    for vx, vy, vw, vh in test_vps[:5]:
        try:
            obs = query_viewport(session, round_id, 0, vx, vy, vw, vh)
            for dy, row in enumerate(obs["grid"]):
                for dx, terrain in enumerate(row):
                    ya, xa = obs["viewport"]["y"] + dy, obs["viewport"]["x"] + dx
                    obs_counts[ya, xa, TERRAIN_TO_CLASS.get(terrain, 0)] += 1
                    obs_total[ya, xa] += 1
            queries_used += 1
        except Exception as e:
            log(f"  Smell query failed: {e}")
            break

    alive, dead = 0, 0
    for sy, sx in test_cells:
        if obs_total[sy, sx] == 0:
            continue
        if obs_counts[sy, sx, 1] + obs_counts[sy, sx, 2] > 0:
            alive += 1
        else:
            dead += 1
    checked = alive + dead
    log(f"  First sniff: {alive}/{checked} alive")

    # Assess confidence
    needs_confirm = False
    if checked > 0 and alive == 0:
        regime = "death"
        log(f"  CONFIDENT: death (0/{checked} alive)")
    elif checked > 0 and alive == checked:
        regime = "growth"
        log(f"  CONFIDENT: growth ({checked}/{checked} alive)")
    else:
        needs_confirm = True
        log(f"  UNCERTAIN ({alive}/{checked}). Confirming...")

    # Confirmation round if needed
    if needs_confirm:
        for vx, vy, vw, vh in test_vps[:5]:
            try:
                obs = query_viewport(session, round_id, 0, vx, vy, vw, vh)
                for dy, row in enumerate(obs["grid"]):
                    for dx, terrain in enumerate(row):
                        ya, xa = obs["viewport"]["y"] + dy, obs["viewport"]["x"] + dx
                        obs_counts[ya, xa, TERRAIN_TO_CLASS.get(terrain, 0)] += 1
                        obs_total[ya, xa] += 1
                queries_used += 1
            except Exception as e:
                log(f"  Confirm query failed: {e}")
                break

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

    # Save regime
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    regime_info = {"regime": regime, "queries_used": queries_used}
    with open(DATA_DIR / f"regime_r{round_num}.json", "w") as f:
        json.dump(regime_info, f)

    # ── OBSERVE ALL SEEDS ──
    log(f"Phase 2: Observe (regime={regime}, {queries_used} queries used)")
    budget = session.get(f"{BASE}/astar-island/budget").json()
    rem = budget["queries_max"] - budget["queries_used"]

    all_obs = {0: (obs_counts.copy(), obs_total.copy())}

    # Complete seed 0
    for vx, vy, vw, vh in viewports:
        if rem <= 0:
            break
        if obs_total[vy, vx] > 0:
            continue
        try:
            obs = query_viewport(session, round_id, 0, vx, vy, vw, vh)
            oc, ot = all_obs[0]
            for dy, row in enumerate(obs["grid"]):
                for dx, terrain in enumerate(row):
                    ya, xa = obs["viewport"]["y"] + dy, obs["viewport"]["x"] + dx
                    oc[ya, xa, TERRAIN_TO_CLASS.get(terrain, 0)] += 1
                    ot[ya, xa] += 1
            rem -= 1
        except Exception as e:
            log(f"  Seed 0 failed: {e}")
            break

    np.save(DATA_DIR / f"obs_counts_r{round_num}_seed0_overview.npy", all_obs[0][0])
    np.save(DATA_DIR / f"obs_total_r{round_num}_seed0_overview.npy", all_obs[0][1])
    log(f"  Seed 0: {(all_obs[0][1] > 0).sum()}/{height*width} cells")

    # Seeds 1-4
    per_seed = rem // max(1, seeds_count - 1)
    for si in range(1, seeds_count):
        if rem <= 0:
            break
        oc = np.zeros((height, width, NUM_CLASSES))
        ot = np.zeros((height, width))
        sb = min(per_seed, rem)
        for vx, vy, vw, vh in viewports:
            if sb <= 0:
                break
            try:
                obs = query_viewport(session, round_id, si, vx, vy, vw, vh)
                for dy, row in enumerate(obs["grid"]):
                    for dx, terrain in enumerate(row):
                        ya, xa = obs["viewport"]["y"] + dy, obs["viewport"]["x"] + dx
                        oc[ya, xa, TERRAIN_TO_CLASS.get(terrain, 0)] += 1
                        ot[ya, xa] += 1
                sb -= 1
                rem -= 1
            except Exception as e:
                break
        np.save(DATA_DIR / f"obs_counts_r{round_num}_seed{si}_overview.npy", oc)
        np.save(DATA_DIR / f"obs_total_r{round_num}_seed{si}_overview.npy", ot)
        all_obs[si] = (oc, ot)
        log(f"  Seed {si}: {(ot > 0).sum()}/{height*width} cells")

    # ── PREDICT & SUBMIT ──
    log(f"Phase 3: Predict & submit (regime={regime})")
    alphas, temps = load_params()

    brain = RegimeModel()
    for rd in load_cached_rounds():
        brain.add_training_data(rd)
    brain.finalize()
    log(f"  Brain trained: {brain.training_info}")

    # Round-specific transitions from observations
    r_trans = {}
    for si in all_obs:
        oc, ot = all_obs[si]
        ig = detail["initial_states"][si]["grid"]
        for y in range(height):
            for x in range(width):
                if ot[y, x] == 0 or int(ig[y][x]) in STATIC_TERRAIN:
                    continue
                init_cls = TERRAIN_TO_CLASS.get(int(ig[y][x]), 0)
                final_cls = oc[y, x].argmax()
                if init_cls not in r_trans:
                    r_trans[init_cls] = np.zeros(NUM_CLASSES)
                r_trans[init_cls][final_cls] += 1
    for cls in r_trans:
        if r_trans[cls].sum() > 0:
            r_trans[cls] /= r_trans[cls].sum()

    for seed_idx in range(seeds_count):
        grid = detail["initial_states"][seed_idx]["grid"]
        pred = brain.predict_grid(detail, seed_idx, regime=regime)

        # Per-terrain Dirichlet blending
        if seed_idx in all_obs:
            oc, ot = all_obs[seed_idx]
            for y in range(height):
                for x in range(width):
                    if ot[y, x] == 0:
                        continue
                    init_cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)
                    av = alphas.get(init_cls, 8.0)
                    alpha = av * pred[y, x]
                    alpha = np.maximum(alpha, PROB_FLOOR)
                    pred[y, x] = (alpha + oc[y, x]) / (alpha.sum() + ot[y, x])

        # Round-specific calibration for settlement/port
        for y in range(height):
            for x in range(width):
                if grid[y][x] in STATIC_TERRAIN:
                    continue
                init_cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)
                if init_cls in (1, 2) and init_cls in r_trans:
                    rp = r_trans[init_cls].copy()
                    if seed_idx in all_obs and all_obs[seed_idx][1][y, x] > 0:
                        od = all_obs[seed_idx][0][y, x] / all_obs[seed_idx][1][y, x]
                        pred[y, x] = 0.7 * od + 0.15 * pred[y, x] + 0.15 * rp
                    else:
                        pred[y, x] = 0.5 * rp + 0.5 * pred[y, x]

        # Port constraint
        oa = compute_ocean_adjacency(grid, height, width)
        for y in range(height):
            for x in range(width):
                if oa[y, x] == 0:
                    pred[y, x, 2] = PROB_FLOOR

        # Entropy-aware temperature
        for y in range(height):
            for x in range(width):
                if grid[y][x] in STATIC_TERRAIN:
                    continue
                p = np.maximum(pred[y, x], 1e-10)
                ent = -np.sum(p * np.log(p))
                t = temps["low"] if ent < 0.3 else (temps["mid"] if ent < 1.0 else temps["high"])
                pred[y, x] = pred[y, x] ** (1.0 / t)

        # Fixed collapse
        for y in range(height):
            for x in range(width):
                if grid[y][x] in STATIC_TERRAIN:
                    continue
                probs = pred[y, x]
                mask = probs < 0.016
                if mask.any() and not mask.all():
                    probs[mask] = PROB_FLOOR
                    pred[y, x] = probs / probs.sum()

        # Smooth
        sm = np.copy(pred)
        for c in range(NUM_CLASSES):
            sm[:, :, c] = gaussian_filter(pred[:, :, c], sigma=0.3)
        for y in range(height):
            for x in range(width):
                if grid[y][x] in STATIC_TERRAIN:
                    sm[y, x] = pred[y, x]
        pred = sm
        pred = np.maximum(pred, PROB_FLOOR)
        pred = pred / pred.sum(axis=-1, keepdims=True)

        assert pred.shape == (height, width, NUM_CLASSES)
        assert np.allclose(pred.sum(axis=-1), 1.0, atol=0.01)

        conf = pred.max(axis=-1).mean()
        obs_n = int(all_obs[seed_idx][1].sum()) if seed_idx in all_obs else 0
        log(f"  Seed {seed_idx}: conf={conf:.3f} obs={obs_n}")

        for attempt in range(5):
            try:
                resp = session.post(f"{BASE}/astar-island/submit", json={
                    "round_id": round_id, "seed_index": seed_idx,
                    "prediction": pred.tolist(),
                })
                resp.raise_for_status()
                log(f"  Seed {seed_idx} SUBMITTED")
                break
            except requests.HTTPError as e:
                if e.response and e.response.status_code == 429:
                    wait = 3 * (attempt + 1)
                    log(f"  Seed {seed_idx} rate limited, waiting {wait}s...")
                    time.sleep(wait)
                    continue
                log(f"  Seed {seed_idx} FAILED: {e}")
                break

    return regime_info


def _load_existing_obs(round_num, seeds_count):
    """Load observations from disk when budget is exhausted."""
    all_obs = {}
    for si in range(seeds_count):
        for label in [f"seed{si}_stacked", f"seed{si}_overview"]:
            pc = DATA_DIR / f"obs_counts_r{round_num}_{label}.npy"
            pt = DATA_DIR / f"obs_total_r{round_num}_{label}.npy"
            if pc.exists() and pt.exists():
                oc, ot = np.load(pc), np.load(pt)
                if si in all_obs:
                    p_oc, p_ot = all_obs[si]
                    mask = ot > p_ot
                    p_oc[mask] = oc[mask]
                    p_ot[mask] = ot[mask]
                else:
                    all_obs[si] = (oc.copy(), ot.copy())
    regime_path = DATA_DIR / f"regime_r{round_num}.json"
    if regime_path.exists():
        with open(regime_path) as f:
            return json.load(f)
    return {"regime": "stable"}


# ──────────────────────────────────────────────
# Self-Improvement Loop
# ──────────────────────────────────────────────

def self_improve(session, state):
    """Run after a round completes. Retrain Brain, re-fit params, deploy if better."""
    log("=" * 50)
    log("SELF-IMPROVEMENT LOOP")
    log("=" * 50)

    # Cache any new completed rounds
    rounds = session.get(f"{BASE}/astar-island/rounds").json()
    completed = [r for r in rounds if r["status"] == "completed"]
    for r in completed:
        rn = r["round_number"]
        if rn not in state["cached_rounds"]:
            log(f"  Caching R{rn}...")
            try:
                cache_round(session, r)
                state["cached_rounds"].append(rn)
                save_state(state)
            except Exception as e:
                log(f"  Cache failed: {e}")

    all_rounds = load_cached_rounds()
    n_rounds = len(all_rounds)
    log(f"  Training data: {n_rounds} rounds")

    if n_rounds <= state.get("last_model_rounds", 0):
        log("  No new data. Skipping improvement.")
        return

    # Current baseline
    old_alphas, old_temps = load_params()
    baseline_score = _backtest_score(all_rounds, old_alphas, old_temps)
    log(f"  Current Brain score: {baseline_score:.2f}")

    # Re-fit alphas
    log("  Fitting per-terrain alphas...")
    best_alphas, alpha_score = _fit_alphas_quick(all_rounds)
    log(f"  Fitted alphas: {[round(best_alphas.get(i, 8), 1) for i in range(6)]} -> {alpha_score:.2f}")

    # Re-fit temps with best alphas
    log("  Fitting entropy temps...")
    best_temps, temp_score = _fit_temps_quick(all_rounds, best_alphas)
    log(f"  Fitted temps: low={best_temps['low']:.2f} mid={best_temps['mid']:.2f} high={best_temps['high']:.2f} -> {temp_score:.2f}")

    # Deploy if better
    if temp_score > baseline_score:
        save_params(best_alphas, best_temps, temp_score, baseline_score)
        log(f"  IMPROVED: {baseline_score:.2f} -> {temp_score:.2f} (+{temp_score - baseline_score:.2f})")
        state["improvements"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "old_score": round(float(baseline_score), 2),
            "new_score": round(float(temp_score), 2),
            "n_rounds": n_rounds,
        })
    else:
        log(f"  No improvement ({temp_score:.2f} vs {baseline_score:.2f}). Keeping current params.")

    state["last_model_rounds"] = n_rounds
    save_state(state)
    log("  Self-improvement complete.\n")


def _backtest_score(rounds_data, alphas, temps):
    """Quick leave-one-out backtest with given params."""
    scores = []
    for rd in rounds_data:
        if not rd.get("seeds"):
            continue
        rn = rd["round_number"]
        regime, _ = classify_round(rd)
        brain = RegimeModel()
        for other in rounds_data:
            if other["round_number"] != rn:
                brain.add_training_data(other)
        brain.finalize()
        h, w = rd["map_height"], rd["map_width"]

        for si_str, sd in rd["seeds"].items():
            si = int(si_str)
            gt = np.array(sd["ground_truth"])
            ig = rd["initial_states"][si]["grid"]
            pred = brain.predict_grid(rd, si, regime=regime)

            # Apply entropy-aware temperature
            for y in range(h):
                for x in range(w):
                    if ig[y][x] in STATIC_TERRAIN:
                        continue
                    p = np.maximum(pred[y, x], 1e-10)
                    ent = -np.sum(p * np.log(p))
                    t = temps["low"] if ent < 0.3 else (temps["mid"] if ent < 1.0 else temps["high"])
                    pred[y, x] = pred[y, x] ** (1.0 / t)

            pred = np.maximum(pred, PROB_FLOOR)
            pred /= pred.sum(axis=-1, keepdims=True)
            scores.append(score_prediction(gt, pred, initial_grid=ig)["score"])

    return np.mean(scores) if scores else 0.0


def _fit_alphas_quick(rounds_data):
    """Quick alpha fitting with reduced iterations."""
    def objective(params):
        alphas = {i: max(0.5, params[i]) for i in range(NUM_CLASSES)}
        # Test on 3 random rounds for speed
        test_rounds = rounds_data[-3:] if len(rounds_data) > 3 else rounds_data
        scores = []
        for rd in test_rounds:
            if not rd.get("seeds"):
                continue
            rn = rd["round_number"]
            regime, _ = classify_round(rd)
            brain = RegimeModel()
            for other in rounds_data:
                if other["round_number"] != rn:
                    brain.add_training_data(other)
            brain.finalize()
            h, w = rd["map_height"], rd["map_width"]
            for si_str, sd in rd["seeds"].items():
                si = int(si_str)
                gt = np.array(sd["ground_truth"])
                ig = rd["initial_states"][si]["grid"]
                pred = brain.predict_grid(rd, si, regime=regime)
                pred = np.maximum(pred, PROB_FLOOR)
                pred /= pred.sum(axis=-1, keepdims=True)
                scores.append(score_prediction(gt, pred, initial_grid=ig)["score"])
        return -np.mean(scores) if scores else 0.0

    x0 = [8.0, 4.0, 3.0, 3.0, 10.0, 50.0]
    result = minimize(objective, x0, method="Nelder-Mead",
                      options={"maxiter": 80, "xatol": 1.0, "fatol": 0.2})
    best = {i: max(0.5, result.x[i]) for i in range(NUM_CLASSES)}
    return best, -result.fun


def _fit_temps_quick(rounds_data, alphas):
    """Quick temperature fitting."""
    def objective(params):
        temps = {"low": max(0.3, params[0]), "mid": max(0.3, params[1]), "high": max(0.3, params[2])}
        return -_backtest_score(rounds_data[-3:] if len(rounds_data) > 3 else rounds_data,
                                alphas, temps)

    x0 = [0.9, 1.1, 1.3]
    result = minimize(objective, x0, method="Nelder-Mead",
                      options={"maxiter": 50, "xatol": 0.1, "fatol": 0.2})
    best = {"low": max(0.3, result.x[0]), "mid": max(0.3, result.x[1]), "high": max(0.3, result.x[2])}
    return best, -result.fun


# ──────────────────────────────────────────────
# Main Loop
# ──────────────────────────────────────────────

def resubmit_with_improved_brain(session, round_id, detail, round_num, all_obs, regime_info):
    """Resubmit predictions using the latest Brain params. Called during improvement window."""
    height, width = detail["map_height"], detail["map_width"]
    seeds_count = detail["seeds_count"]
    regime = regime_info.get("regime", "stable")
    alphas, temps = load_params()

    brain = RegimeModel()
    for rd in load_cached_rounds():
        brain.add_training_data(rd)
    brain.finalize()

    # Round-specific transitions
    r_trans = {}
    for si in all_obs:
        oc, ot = all_obs[si]
        ig = detail["initial_states"][si]["grid"]
        for y in range(height):
            for x in range(width):
                if ot[y, x] == 0 or int(ig[y][x]) in STATIC_TERRAIN:
                    continue
                init_cls = TERRAIN_TO_CLASS.get(int(ig[y][x]), 0)
                final_cls = oc[y, x].argmax()
                if init_cls not in r_trans:
                    r_trans[init_cls] = np.zeros(NUM_CLASSES)
                r_trans[init_cls][final_cls] += 1
    for cls in r_trans:
        if r_trans[cls].sum() > 0:
            r_trans[cls] /= r_trans[cls].sum()

    for seed_idx in range(seeds_count):
        grid = detail["initial_states"][seed_idx]["grid"]
        pred = brain.predict_grid(detail, seed_idx, regime=regime)

        if seed_idx in all_obs:
            oc, ot = all_obs[seed_idx]
            for y in range(height):
                for x in range(width):
                    if ot[y, x] == 0:
                        continue
                    init_cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)
                    av = alphas.get(init_cls, 8.0)
                    alpha = av * pred[y, x]
                    alpha = np.maximum(alpha, PROB_FLOOR)
                    pred[y, x] = (alpha + oc[y, x]) / (alpha.sum() + ot[y, x])

        for y in range(height):
            for x in range(width):
                if grid[y][x] in STATIC_TERRAIN:
                    continue
                init_cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)
                if init_cls in (1, 2) and init_cls in r_trans:
                    rp = r_trans[init_cls].copy()
                    if seed_idx in all_obs and all_obs[seed_idx][1][y, x] > 0:
                        od = all_obs[seed_idx][0][y, x] / all_obs[seed_idx][1][y, x]
                        pred[y, x] = 0.7 * od + 0.15 * pred[y, x] + 0.15 * rp
                    else:
                        pred[y, x] = 0.5 * rp + 0.5 * pred[y, x]

        oa = compute_ocean_adjacency(grid, height, width)
        for y in range(height):
            for x in range(width):
                if oa[y, x] == 0:
                    pred[y, x, 2] = PROB_FLOOR

        for y in range(height):
            for x in range(width):
                if grid[y][x] in STATIC_TERRAIN:
                    continue
                p = np.maximum(pred[y, x], 1e-10)
                ent = -np.sum(p * np.log(p))
                t = temps["low"] if ent < 0.3 else (temps["mid"] if ent < 1.0 else temps["high"])
                pred[y, x] = pred[y, x] ** (1.0 / t)

        for y in range(height):
            for x in range(width):
                if grid[y][x] in STATIC_TERRAIN:
                    continue
                probs = pred[y, x]
                mask = probs < 0.016
                if mask.any() and not mask.all():
                    probs[mask] = PROB_FLOOR
                    pred[y, x] = probs / probs.sum()

        sm = np.copy(pred)
        for c in range(NUM_CLASSES):
            sm[:, :, c] = gaussian_filter(pred[:, :, c], sigma=0.3)
        for y in range(height):
            for x in range(width):
                if grid[y][x] in STATIC_TERRAIN:
                    sm[y, x] = pred[y, x]
        pred = np.maximum(sm, PROB_FLOOR)
        pred = pred / pred.sum(axis=-1, keepdims=True)

        time.sleep(0.5)  # Rate limit spacing between seeds
        for attempt in range(5):
            try:
                resp = session.post(f"{BASE}/astar-island/submit", json={
                    "round_id": round_id, "seed_index": seed_idx,
                    "prediction": pred.tolist(),
                })
                resp.raise_for_status()
                log(f"  Seed {seed_idx} RESUBMITTED (conf={pred.max(axis=-1).mean():.3f})")
                break
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    wait = 5 * (attempt + 1)
                    log(f"  Seed {seed_idx} rate limited, waiting {wait}s (attempt {attempt + 1}/5)")
                    time.sleep(wait)
                    continue
                log(f"  Seed {seed_idx} FAILED: {e}")
                break


def run_cycle(session, state):
    """One cycle: check rounds, submit, improve, resubmit. Uses the full round window."""
    now = datetime.now(timezone.utc)
    if now >= COMPETITION_END:
        log("COMPETITION ENDED. Stopping.")
        return False

    rounds = session.get(f"{BASE}/astar-island/rounds").json()

    # Cache completed rounds
    completed = [r for r in rounds if r["status"] == "completed"]
    new_completed = False
    for r in completed:
        rn = r["round_number"]
        if rn not in state["cached_rounds"]:
            try:
                log(f"Caching R{rn} ground truth...")
                cache_round(session, r)
                state["cached_rounds"].append(rn)
                save_state(state)
                new_completed = True
            except Exception as e:
                log(f"  Cache R{rn} failed: {e}")

    # Run self-improvement if new data available (between rounds)
    if new_completed:
        try:
            self_improve(session, state)
        except Exception as e:
            log(f"  Self-improvement failed: {e}")
            traceback.print_exc()

    # Find active round
    active = None
    for r in rounds:
        if r["status"] == "active":
            active = r
            break

    if active is None:
        log("No active round. Waiting...")
        return True

    round_id = active["id"]
    round_num = active["round_number"]
    closes = datetime.fromisoformat(active["closes_at"])
    remaining = (closes - now).total_seconds() / 60

    log(f"R{round_num} active, {remaining:.0f} min left, weight={active['round_weight']:.4f}")

    # Already submitted: use remaining time to improve and resubmit
    if round_num in state["submitted_rounds"]:
        # Check if Brain params were updated by parallel experiments
        params_updated = False
        if PARAMS_FILE.exists():
            params_mtime = PARAMS_FILE.stat().st_mtime
            last_resubmit_time = state.get("last_resubmit_time", 0)
            if params_mtime > last_resubmit_time:
                params_updated = True

        n_cached = len(load_cached_rounds())
        new_data = n_cached > state.get("last_model_rounds", 0)

        if remaining > 20 and (params_updated or new_data):
            reason = "new params from parallel experiments" if params_updated else "new ground truth data"
            log(f"  R{round_num} submitted but {remaining:.0f} min left. Resubmitting ({reason})...")

            # Run self-improvement if new ground truth data is available
            if new_data:
                try:
                    self_improve(session, state)
                except Exception as e:
                    log(f"  Improvement failed: {e}")

            # Reload observations and resubmit (runs for BOTH new_data and params_updated)
            detail = session.get(f"{BASE}/astar-island/rounds/{round_id}").json()
            seeds_count = detail.get("seeds_count", 5)
            all_obs = {}
            for si in range(seeds_count):
                for label in [f"seed{si}_stacked", f"seed{si}_overview"]:
                    pc = DATA_DIR / f"obs_counts_r{round_num}_{label}.npy"
                    pt = DATA_DIR / f"obs_total_r{round_num}_{label}.npy"
                    if pc.exists() and pt.exists():
                        oc, ot = np.load(pc), np.load(pt)
                        if si in all_obs:
                            p_oc, p_ot = all_obs[si]
                            mask = ot > p_ot
                            p_oc[mask] = oc[mask]
                            p_ot[mask] = ot[mask]
                        else:
                            all_obs[si] = (oc.copy(), ot.copy())

            regime_path = DATA_DIR / f"regime_r{round_num}.json"
            regime_info = {"regime": "stable"}
            if regime_path.exists():
                with open(regime_path) as f:
                    regime_info = json.load(f)

            try:
                resubmit_with_improved_brain(session, round_id, detail, round_num, all_obs, regime_info)
                state["last_resubmit_round"] = round_num
                state["last_resubmit_time"] = time.time()
                save_state(state)
                log(f"  R{round_num} RESUBMITTED with improved Brain")
            except Exception as e:
                log(f"  Resubmit failed: {e}")
        else:
            log(f"  R{round_num} already submitted and resubmitted.")
        return True

    # New round: run Chef v8
    log(f"  NEW ROUND {round_num}! Running Chef v8...")
    detail = session.get(f"{BASE}/astar-island/rounds/{round_id}").json()

    try:
        run_chef_v8(session, round_id, detail, round_num)
        state["submitted_rounds"].append(round_num)
        save_state(state)
        log(f"  R{round_num} SUBMITTED SUCCESSFULLY")
    except Exception as e:
        log(f"  Chef v8 FAILED: {e}")
        traceback.print_exc()

    return True


def test_improvement():
    """Test self-improvement loop on cached data (no API calls)."""
    log("=" * 50)
    log("BLIND TEST: Self-improvement on cached data")
    log("=" * 50)

    rounds_data = load_cached_rounds()
    log(f"Loaded {len(rounds_data)} rounds")

    # Current params
    alphas, temps = load_params()
    baseline = _backtest_score(rounds_data, alphas, temps)
    log(f"Current Brain: {baseline:.2f}")
    log(f"  Alphas: {[round(alphas.get(i, 8), 1) for i in range(6)]}")
    log(f"  Temps: low={temps['low']:.2f} mid={temps['mid']:.2f} high={temps['high']:.2f}")

    # Fit new params
    log("\nFitting alphas...")
    new_alphas, a_score = _fit_alphas_quick(rounds_data)
    log(f"  New alphas: {[round(new_alphas.get(i, 8), 1) for i in range(6)]} -> {a_score:.2f}")

    log("Fitting temps...")
    new_temps, t_score = _fit_temps_quick(rounds_data, new_alphas)
    log(f"  New temps: low={new_temps['low']:.2f} mid={new_temps['mid']:.2f} high={new_temps['high']:.2f} -> {t_score:.2f}")

    # Full backtest with new params
    full_score = _backtest_score(rounds_data, new_alphas, new_temps)
    log(f"\nFull backtest: {full_score:.2f} (was {baseline:.2f}, delta={full_score - baseline:+.2f})")

    if full_score > baseline:
        save_params(new_alphas, new_temps, full_score, baseline)
        log("DEPLOYED new params!")
    else:
        log("Kept old params (no improvement).")

    log("Blind test complete.\n")


def main():
    parser = argparse.ArgumentParser(description="Self-Improving Overnight Runner v2")
    parser.add_argument("--token", required=True)
    parser.add_argument("--continuous", action="store_true")
    parser.add_argument("--test-improve", action="store_true",
                        help="Test self-improvement on cached data (no API)")
    parser.add_argument("--interval", type=int, default=300)
    args = parser.parse_args()

    session = get_session(args.token)
    state = load_state()

    log("=" * 60)
    log("OVERNIGHT RUNNER V2 — SELF-IMPROVING")
    log(f"  State: submitted={state['submitted_rounds']}")
    log(f"  Cached: {state['cached_rounds']}")
    log(f"  Improvements: {len(state.get('improvements', []))}")
    log("=" * 60)

    if args.test_improve:
        test_improvement()
        return

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
