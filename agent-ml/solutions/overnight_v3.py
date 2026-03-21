#!/usr/bin/env python3
"""
Self-Improving Overnight Runner v3 for Astar Island.

Upgrades from v2:
1. DUAL-TRACK: Blends V2 (global) and V3 (regime) predictions, weighted by backtest
2. SETTLEMENT STATS: Captures population/food/wealth/defense from /simulate
3. CALIBRATED SCORING: Regime-aware score weighting in self-improvement

Cycle:
1. DETECT round state (active/completed/scoring)
2. If new round: observe (capturing settlement stats) + dual predict + submit
3. If round just closed: self-improvement loop with V2/V3 comparison
4. Sleep 5 min, repeat

Usage:
  python overnight_v3.py --token TOKEN --continuous
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
from learned_model import NeighborhoodModel

DATA_DIR = Path(__file__).parent / "data"
STATE_FILE = Path(__file__).parent.parent / "overnight_state.json"
LOG_FILE = Path.home() / "overnight_v3.log"
PARAMS_FILE = DATA_DIR / "brain_v3_params.json"
WEIGHTS_FILE = DATA_DIR / "model_weights.json"
STATS_DIR = DATA_DIR / "settlement_stats"

COMPETITION_END = datetime(2026, 3, 22, 14, 0, 0, tzinfo=timezone.utc)

# Calibration offsets by regime (backtest - actual)
# Positive = backtest overshoots reality
CALIBRATION = {"death": 20.0, "stable": 7.0, "growth": -5.0}


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        print(line, flush=True)


# ──────────────────────────────────────────────
# State Management
# ──────────────────────────────────────────────

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
                    time.sleep(0.1)
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


def load_model_weights():
    """Load V2/V3 blend weights. Returns (v3_weight, v2_weight)."""
    if WEIGHTS_FILE.exists():
        try:
            w = json.load(open(WEIGHTS_FILE))
            v3w = w.get("v3_weight", 0.7)
            return v3w, 1.0 - v3w
        except Exception:
            pass
    return 0.7, 0.3  # Default: lean V3


def save_model_weights(v3_weight, v2_avg, v3_avg, details=""):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(WEIGHTS_FILE, "w") as f:
        json.dump({
            "v3_weight": round(v3_weight, 3),
            "v2_weight": round(1.0 - v3_weight, 3),
            "v2_avg": round(v2_avg, 2),
            "v3_avg": round(v3_avg, 2),
            "details": details,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, f, indent=2)


# ──────────────────────────────────────────────
# Settlement Stats (NEW in v3)
# ──────────────────────────────────────────────

def save_settlement_stats(round_num, seed_idx, settlements):
    """Save settlement stats from /simulate response."""
    if not settlements:
        return
    STATS_DIR.mkdir(parents=True, exist_ok=True)
    path = STATS_DIR / f"r{round_num}_seed{seed_idx}.jsonl"
    with open(path, "a") as f:
        for s in settlements:
            f.write(json.dumps(s) + "\n")


def analyze_settlement_stats(round_num):
    """Analyze settlement stats to improve regime detection.
    Returns regime hint based on settlement health indicators."""
    stats = []
    for p in STATS_DIR.glob(f"r{round_num}_seed*.jsonl"):
        with open(p) as f:
            for line in f:
                try:
                    stats.append(json.loads(line))
                except Exception:
                    pass
    if not stats:
        return None

    alive_count = sum(1 for s in stats if s.get("alive", False))
    total = len(stats)
    avg_food = np.mean([s.get("food", 0.5) for s in stats]) if stats else 0.5
    avg_pop = np.mean([s.get("population", 0.5) for s in stats]) if stats else 0.5
    avg_defense = np.mean([s.get("defense", 0.5) for s in stats]) if stats else 0.5

    survival_rate = alive_count / max(1, total)

    # Enhanced regime detection using settlement health
    if survival_rate < 0.15:
        regime_hint = "death"
    elif survival_rate > 0.60 and avg_food > 0.4:
        regime_hint = "growth"
    elif avg_food < 0.2 and avg_defense < 0.2:
        regime_hint = "death"
    elif survival_rate > 0.40:
        regime_hint = "growth" if avg_pop > 0.3 else "stable"
    else:
        regime_hint = "stable"

    log(f"  Stats: {alive_count}/{total} alive, food={avg_food:.2f}, "
        f"pop={avg_pop:.2f}, def={avg_defense:.2f} -> {regime_hint}")
    return regime_hint


# ──────────────────────────────────────────────
# Observation Queries
# ──────────────────────────────────────────────

def query_viewport(session, round_id, seed_idx, x, y, w=15, h=15, round_num=None):
    resp = session.post(f"{BASE}/astar-island/simulate", json={
        "round_id": round_id, "seed_index": seed_idx,
        "viewport_x": x, "viewport_y": y, "viewport_w": w, "viewport_h": h,
    })
    resp.raise_for_status()
    time.sleep(0.22)
    data = resp.json()
    # Capture settlement stats
    if round_num is not None and "settlements" in data:
        save_settlement_stats(round_num, seed_idx, data["settlements"])
    return data


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


# ──────────────────────────────────────────────
# Prediction: V3 (regime) pipeline
# ──────────────────────────────────────────────

def predict_v3(detail, seed_idx, regime, all_obs, r_trans, alphas, temps):
    """V3 prediction: regime-specific model + per-terrain Dirichlet + entropy temp."""
    height, width = detail["map_height"], detail["map_width"]
    grid = detail["initial_states"][seed_idx]["grid"]

    brain = RegimeModel()
    for rd in load_cached_rounds():
        brain.add_training_data(rd)
    brain.finalize()

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

    # Collapse
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
    return pred


# ──────────────────────────────────────────────
# Prediction: V2 (global) pipeline
# ──────────────────────────────────────────────

def predict_v2(detail, seed_idx, all_obs):
    """V2 prediction: global model + Dirichlet + global temperature.
    This is what won R9 (82.6)."""
    height, width = detail["map_height"], detail["map_width"]
    grid = detail["initial_states"][seed_idx]["grid"]

    brain = NeighborhoodModel()
    for rd in load_cached_rounds():
        brain.add_training_data(rd)
    brain.finalize()

    pred = brain.predict_grid(detail, seed_idx)

    # Dirichlet blending with observations (global alpha, like R9's ps=12)
    if seed_idx in all_obs:
        oc, ot = all_obs[seed_idx]
        ps = 12.0  # Prior strength (what won R9)
        for y in range(height):
            for x in range(width):
                if ot[y, x] == 0:
                    continue
                alpha = ps * pred[y, x]
                alpha = np.maximum(alpha, PROB_FLOOR)
                pred[y, x] = (alpha + oc[y, x]) / (alpha.sum() + ot[y, x])

    # Port constraint
    oa = compute_ocean_adjacency(grid, height, width)
    for y in range(height):
        for x in range(width):
            if oa[y, x] == 0:
                pred[y, x, 2] = PROB_FLOOR

    # Global temperature (R9 used T=1.12)
    pred = pred ** (1.0 / 1.12)

    # Collapse
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
    return pred


# ──────────────────────────────────────────────
# Blended Prediction (NEW in v3)
# ──────────────────────────────────────────────

def predict_blended(detail, seed_idx, regime, all_obs, r_trans, alphas, temps):
    """Generate blended V2+V3 prediction, weighted by backtest performance."""
    pred_v3 = predict_v3(detail, seed_idx, regime, all_obs, r_trans, alphas, temps)
    pred_v2 = predict_v2(detail, seed_idx, all_obs)

    v3_w, v2_w = load_model_weights()

    pred = v3_w * pred_v3 + v2_w * pred_v2
    pred = np.maximum(pred, PROB_FLOOR)
    pred = pred / pred.sum(axis=-1, keepdims=True)
    return pred


# ──────────────────────────────────────────────
# Chef v3: Smell Test + Observe + Dual Predict + Submit
# ──────────────────────────────────────────────

def run_chef_v3(session, round_id, detail, round_num):
    """Full Chef v3 pipeline with settlement stats + dual-track prediction."""
    height, width = detail["map_height"], detail["map_width"]
    seeds_count = detail["seeds_count"]

    # Check budget
    budget = session.get(f"{BASE}/astar-island/budget").json()
    remaining = budget["queries_max"] - budget["queries_used"]
    if remaining <= 0:
        log("  Budget exhausted. Predicting from existing observations...")
        # Load existing obs and predict with blend
        all_obs = _load_all_obs(round_num, seeds_count, height, width)
        regime_info = _load_regime_info(round_num)
        _submit_blended(session, round_id, detail, round_num, all_obs, regime_info)
        return regime_info

    ig0 = detail["initial_states"][0]["grid"]
    settle_cells = find_settlement_cells(ig0, height, width)
    viewports = tile_viewports(height, width, 15)

    # ── SMELL TEST with settlement stats ──
    log("Phase 1: Smell test")
    obs_counts = np.zeros((height, width, NUM_CLASSES))
    obs_total = np.zeros((height, width))

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
            obs = query_viewport(session, round_id, 0, vx, vy, vw, vh, round_num=round_num)
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

    if needs_confirm:
        for vx, vy, vw, vh in test_vps[:5]:
            try:
                obs = query_viewport(session, round_id, 0, vx, vy, vw, vh, round_num=round_num)
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

    # Cross-check with settlement stats
    stats_hint = analyze_settlement_stats(round_num)
    if stats_hint and stats_hint != regime:
        log(f"  Stats disagree: smell={regime}, stats={stats_hint}. Using smell test.")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    regime_info = {"regime": regime, "queries_used": queries_used, "stats_hint": stats_hint}
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
            obs = query_viewport(session, round_id, 0, vx, vy, vw, vh, round_num=round_num)
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
                obs = query_viewport(session, round_id, si, vx, vy, vw, vh, round_num=round_num)
                for dy, row in enumerate(obs["grid"]):
                    for dx, terrain in enumerate(row):
                        ya, xa = obs["viewport"]["y"] + dy, obs["viewport"]["x"] + dx
                        oc[ya, xa, TERRAIN_TO_CLASS.get(terrain, 0)] += 1
                        ot[ya, xa] += 1
                sb -= 1
                rem -= 1
            except Exception:
                break
        np.save(DATA_DIR / f"obs_counts_r{round_num}_seed{si}_overview.npy", oc)
        np.save(DATA_DIR / f"obs_total_r{round_num}_seed{si}_overview.npy", ot)
        all_obs[si] = (oc, ot)
        log(f"  Seed {si}: {(ot > 0).sum()}/{height*width} cells")

    # ── DUAL PREDICT & SUBMIT ──
    _submit_blended(session, round_id, detail, round_num, all_obs, regime_info)
    return regime_info


def _submit_blended(session, round_id, detail, round_num, all_obs, regime_info):
    """Generate blended V2+V3 predictions and submit all seeds."""
    height, width = detail["map_height"], detail["map_width"]
    seeds_count = detail["seeds_count"]
    regime = regime_info.get("regime", "stable")
    alphas, temps = load_params()
    v3_w, v2_w = load_model_weights()

    log(f"Phase 3: Dual predict & submit (regime={regime}, V3={v3_w:.0%}/V2={v2_w:.0%})")

    # Build round-specific transitions from observations
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
        pred = predict_blended(detail, seed_idx, regime, all_obs, r_trans, alphas, temps)

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


def _load_all_obs(round_num, seeds_count, height, width):
    """Load all observations from disk."""
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
    return all_obs


def _load_regime_info(round_num):
    regime_path = DATA_DIR / f"regime_r{round_num}.json"
    if regime_path.exists():
        with open(regime_path) as f:
            return json.load(f)
    return {"regime": "stable"}


# ──────────────────────────────────────────────
# Self-Improvement Loop (upgraded with V2/V3 comparison)
# ──────────────────────────────────────────────

def self_improve(session, state):
    """Run after a round completes. Retrain, compare V2 vs V3, set weights."""
    log("=" * 50)
    log("SELF-IMPROVEMENT LOOP (V3)")
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
    log(f"  Current Brain V3 score: {baseline_score:.2f}")

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
        log(f"  IMPROVED V3: {baseline_score:.2f} -> {temp_score:.2f} (+{temp_score - baseline_score:.2f})")
        state["improvements"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "old_score": round(float(baseline_score), 2),
            "new_score": round(float(temp_score), 2),
            "n_rounds": n_rounds,
        })
    else:
        log(f"  V3 no improvement ({temp_score:.2f} vs {baseline_score:.2f}). Keeping current params.")

    # ── V2 vs V3 COMPARISON (NEW) ──
    log("  Comparing V2 (global) vs V3 (regime)...")
    v2_scores_by_regime = {"death": [], "growth": [], "stable": []}
    v3_scores_by_regime = {"death": [], "growth": [], "stable": []}

    test_rounds = all_rounds[-5:] if len(all_rounds) > 5 else all_rounds
    for rd in test_rounds:
        if not rd.get("seeds"):
            continue
        rn = rd["round_number"]
        regime, _ = classify_round(rd)
        h, w = rd["map_height"], rd["map_width"]

        # Train V3
        brain_v3 = RegimeModel()
        for other in all_rounds:
            if other["round_number"] != rn:
                brain_v3.add_training_data(other)
        brain_v3.finalize()

        # Train V2
        brain_v2 = NeighborhoodModel()
        for other in all_rounds:
            if other["round_number"] != rn:
                brain_v2.add_training_data(other)
        brain_v2.finalize()

        for si_str, sd in rd["seeds"].items():
            si = int(si_str)
            gt = np.array(sd["ground_truth"])
            ig = rd["initial_states"][si]["grid"]

            # V3
            p3 = brain_v3.predict_grid(rd, si, regime=regime)
            p3 = np.maximum(p3, PROB_FLOOR)
            p3 /= p3.sum(axis=-1, keepdims=True)
            s3 = score_prediction(gt, p3, initial_grid=ig)["score"]

            # V2
            p2 = brain_v2.predict_grid(rd, si)
            p2 = p2 ** (1.0 / 1.12)
            p2 = np.maximum(p2, PROB_FLOOR)
            p2 /= p2.sum(axis=-1, keepdims=True)
            s2 = score_prediction(gt, p2, initial_grid=ig)["score"]

            v3_scores_by_regime[regime].append(s3)
            v2_scores_by_regime[regime].append(s2)

    # Compute calibrated averages
    v2_all, v3_all = [], []
    for regime in ["death", "growth", "stable"]:
        v2s = v2_scores_by_regime[regime]
        v3s = v3_scores_by_regime[regime]
        if v2s:
            cal_offset = CALIBRATION.get(regime, 7.0)
            v2_cal = [s - cal_offset for s in v2s]
            v3_cal = [s - cal_offset for s in v3s]
            v2_all.extend(v2_cal)
            v3_all.extend(v3_cal)
            log(f"    {regime}: V2={np.mean(v2s):.1f}(cal:{np.mean(v2_cal):.1f}) "
                f"V3={np.mean(v3s):.1f}(cal:{np.mean(v3_cal):.1f})")

    v2_avg = np.mean(v2_all) if v2_all else 0
    v3_avg = np.mean(v3_all) if v3_all else 0

    # Set blend weights proportional to calibrated scores
    total = max(v2_avg + v3_avg, 1.0)
    if total > 0 and v2_avg > 0 and v3_avg > 0:
        v3_weight = v3_avg / total
        v3_weight = max(0.3, min(0.9, v3_weight))  # Clamp to [0.3, 0.9]
    elif v3_avg >= v2_avg:
        v3_weight = 0.7
    else:
        v3_weight = 0.3

    save_model_weights(v3_weight, v2_avg, v3_avg,
                       f"V2_cal={v2_avg:.1f} V3_cal={v3_avg:.1f}")
    log(f"  Model weights: V3={v3_weight:.0%} V2={1-v3_weight:.0%} "
        f"(V2_cal={v2_avg:.1f} V3_cal={v3_avg:.1f})")

    state["last_model_rounds"] = n_rounds
    save_state(state)
    log("  Self-improvement complete.\n")


def _backtest_score(rounds_data, alphas, temps):
    """Leave-one-out backtest with V3 model."""
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
    """Quick alpha fitting."""
    def objective(params):
        alphas = {i: max(0.5, params[i]) for i in range(NUM_CLASSES)}
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

def run_cycle(session, state):
    """One cycle: check rounds, submit, improve, resubmit."""
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

    # Run self-improvement if new data available
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

    # Already submitted: resubmit if brain improved
    if round_num in state["submitted_rounds"]:
        params_updated = False
        if PARAMS_FILE.exists():
            params_mtime = PARAMS_FILE.stat().st_mtime
            last_resubmit_time = state.get("last_resubmit_time", 0)
            if params_mtime > last_resubmit_time:
                params_updated = True

        # Also check if model weights changed
        weights_updated = False
        if WEIGHTS_FILE.exists():
            weights_mtime = WEIGHTS_FILE.stat().st_mtime
            if weights_mtime > state.get("last_resubmit_time", 0):
                weights_updated = True

        n_cached = len(load_cached_rounds())
        new_data = n_cached > state.get("last_model_rounds", 0)

        if remaining > 20 and (params_updated or new_data or weights_updated):
            reason = []
            if params_updated:
                reason.append("new params")
            if weights_updated:
                reason.append("new blend weights")
            if new_data:
                reason.append("new ground truth")
            log(f"  R{round_num} submitted but {remaining:.0f} min left. Resubmitting ({', '.join(reason)})...")

            if new_data:
                try:
                    self_improve(session, state)
                except Exception as e:
                    log(f"  Improvement failed: {e}")

            # Reload observations and resubmit with blended model
            detail = session.get(f"{BASE}/astar-island/rounds/{round_id}").json()
            seeds_count = detail.get("seeds_count", 5)
            h, w = detail["map_height"], detail["map_width"]
            all_obs = _load_all_obs(round_num, seeds_count, h, w)
            regime_info = _load_regime_info(round_num)

            try:
                _submit_blended(session, round_id, detail, round_num, all_obs, regime_info)
                state["last_resubmit_round"] = round_num
                state["last_resubmit_time"] = time.time()
                save_state(state)
                log(f"  R{round_num} RESUBMITTED with blended V2+V3")
            except Exception as e:
                log(f"  Resubmit failed: {e}")
        else:
            log(f"  R{round_num} already submitted and resubmitted.")
        return True

    # New round: run Chef v3
    log(f"  NEW ROUND {round_num}! Running Chef v3...")
    detail = session.get(f"{BASE}/astar-island/rounds/{round_id}").json()

    try:
        run_chef_v3(session, round_id, detail, round_num)
        state["submitted_rounds"].append(round_num)
        save_state(state)
        log(f"  R{round_num} SUBMITTED SUCCESSFULLY (blended V2+V3)")
    except Exception as e:
        log(f"  Chef v3 FAILED: {e}")
        traceback.print_exc()

    return True


def main():
    parser = argparse.ArgumentParser(description="Self-Improving Overnight Runner v3")
    parser.add_argument("--token", required=True)
    parser.add_argument("--continuous", action="store_true")
    parser.add_argument("--interval", type=int, default=300)
    args = parser.parse_args()

    session = get_session(args.token)
    state = load_state()

    log("=" * 60)
    log("OVERNIGHT RUNNER V3 — DUAL-TRACK + SETTLEMENT STATS")
    v3_w, v2_w = load_model_weights()
    log(f"  Blend: V3={v3_w:.0%} V2={v2_w:.0%}")
    log(f"  State: submitted={state['submitted_rounds']}")
    log(f"  Cached: {state['cached_rounds']}")
    log(f"  Improvements: {len(state.get('improvements', []))}")
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
