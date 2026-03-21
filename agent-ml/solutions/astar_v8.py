#!/usr/bin/env python3
"""
Chef v8 — Astar Island Prediction Pipeline

Improvements over v7:
- Smell Test Protocol: 5+5 queries for reliable regime detection
- Brain V3: regime-specific tables, per-terrain Dirichlet alpha, entropy-aware temperature
- Fixed collapse thresholding (was no-op in v7)
- Round-specific calibration from cross-seed observations
- Option B: cover all 5 seeds with remaining budget

Usage:
  python astar_v8.py --token TOKEN --phase all
  python astar_v8.py --token TOKEN --phase all --dry-run
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
CLASS_NAMES = ["Empty", "Settlement", "Port", "Ruin", "Forest", "Mountain"]

# Default Brain V3 params (updated by self-improving loop)
DEFAULT_ALPHAS = {0: 8.0, 1: 4.0, 2: 3.0, 3: 3.0, 4: 10.0, 5: 50.0}
DEFAULT_TEMPS = {"low": 0.9, "mid": 1.1, "high": 1.3}
DEFAULT_COLLAPSE = 0.016
DEFAULT_SIGMA = 0.3


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def get_session(token):
    s = requests.Session()
    s.cookies.set("access_token", token, domain="api.ainm.no")
    s.headers["User-Agent"] = "chef-v8/nmiai-2026"
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


def load_brain_params():
    """Load fitted Brain V3 params if available, else defaults."""
    params_file = DATA_DIR / "brain_v3_params.json"
    if params_file.exists():
        with open(params_file) as f:
            p = json.load(f)
        alphas = {int(k): v for k, v in p.get("alphas", {}).items()}
        temps = p.get("temps", DEFAULT_TEMPS)
        log(f"  Loaded fitted params: alphas={[round(alphas.get(i,8),1) for i in range(6)]}")
        return alphas, temps
    return DEFAULT_ALPHAS.copy(), DEFAULT_TEMPS.copy()


# ──────────────────────────────────────────────
# PHASE 1: Smell Test — Regime Detection
# ──────────────────────────────────────────────
def smell_test(session, round_id, detail, round_num):
    """Reliable regime detection with confirmation when uncertain.

    Step 1: 5 queries on 5 settlement cells (1 sample each)
    Step 2: If 0/5 alive -> DEATH (96% conf). If 5/5 alive -> GROWTH (84% conf).
    Step 3: If 1-4/5 alive -> UNCERTAIN. Re-sample same 5 cells (5 more queries).
    """
    height, width = detail["map_height"], detail["map_width"]
    ig0 = detail["initial_states"][0]["grid"]
    settle_cells = find_settlement_cells(ig0, height, width)

    obs_counts = np.zeros((height, width, NUM_CLASSES))
    obs_total = np.zeros((height, width))

    # Pick 5 settlement cells spread across the map
    if len(settle_cells) > 5:
        indices = np.linspace(0, len(settle_cells) - 1, 5, dtype=int)
        test_cells = [settle_cells[i] for i in indices]
    else:
        test_cells = settle_cells[:5]

    # Build viewports centered on test cells
    test_viewports = []
    used_vps = set()
    for sy, sx in test_cells:
        vx = max(0, min(sx - 7, width - 15))
        vy = max(0, min(sy - 7, height - 15))
        vp_key = (vx, vy)
        if vp_key not in used_vps:
            used_vps.add(vp_key)
            test_viewports.append((vx, vy, 15, 15))

    # Step 1: First sniff (5 queries)
    log(f"Smell test: {len(test_viewports)} queries on {len(settle_cells)} known settlements")
    queries_used = 0
    for vx, vy, vw, vh in test_viewports[:5]:
        try:
            obs = query_viewport(session, round_id, 0, vx, vy, vw, vh)
            for dy, row in enumerate(obs["grid"]):
                for dx, terrain in enumerate(row):
                    ya, xa = obs["viewport"]["y"] + dy, obs["viewport"]["x"] + dx
                    cls = TERRAIN_TO_CLASS.get(terrain, 0)
                    obs_counts[ya, xa, cls] += 1
                    obs_total[ya, xa] += 1
            queries_used += 1
        except Exception as e:
            log(f"  Query failed: {e}")
            break

    # Count alive settlements
    alive = 0
    dead = 0
    for sy, sx in test_cells:
        if obs_total[sy, sx] == 0:
            continue
        sp = obs_counts[sy, sx, 1] + obs_counts[sy, sx, 2]
        if sp > 0:
            alive += 1
        else:
            dead += 1
    checked = alive + dead

    log(f"  First sniff: {alive}/{checked} alive")

    # Step 2: Assess confidence
    if checked > 0 and alive == 0:
        regime = "death"
        confidence = 0.96
        log(f"  CONFIDENT: {regime} ({confidence:.0%})")
    elif checked > 0 and alive == checked:
        regime = "growth"
        confidence = 0.84
        log(f"  CONFIDENT: {regime} ({confidence:.0%})")
    else:
        # UNCERTAIN: re-sample same cells for confirmation
        log(f"  UNCERTAIN ({alive}/{checked}). Re-sampling for confirmation...")
        for vx, vy, vw, vh in test_viewports[:5]:
            try:
                obs = query_viewport(session, round_id, 0, vx, vy, vw, vh)
                for dy, row in enumerate(obs["grid"]):
                    for dx, terrain in enumerate(row):
                        ya, xa = obs["viewport"]["y"] + dy, obs["viewport"]["x"] + dx
                        cls = TERRAIN_TO_CLASS.get(terrain, 0)
                        obs_counts[ya, xa, cls] += 1
                        obs_total[ya, xa] += 1
                queries_used += 1
            except Exception as e:
                log(f"  Confirmation query failed: {e}")
                break

        # Re-count with 2 samples per cell
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
        checked2 = alive2 + dead2
        survival_rate = alive2 / max(1, checked2)
        log(f"  Confirmed: {alive2}/{checked2} alive (survival={survival_rate:.0%})")

        if survival_rate < 0.15:
            regime = "death"
        elif survival_rate > 0.60:
            regime = "growth"
        else:
            regime = "stable"
        confidence = 0.85

    log(f"  REGIME: {regime} (conf={confidence:.0%}, used {queries_used} queries)")

    # Save regime info
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    regime_info = {
        "regime": regime,
        "confidence": float(confidence),
        "alive": alive,
        "checked": checked,
        "queries_used": queries_used,
    }
    with open(DATA_DIR / f"regime_r{round_num}.json", "w") as f:
        json.dump(regime_info, f)

    return obs_counts, obs_total, regime_info, queries_used


# ──────────────────────────────────────────────
# PHASE 2: Observe — Cover all 5 seeds (Option B)
# ──────────────────────────────────────────────
def observe_all_seeds(session, round_id, detail, round_num,
                      initial_obs_counts, initial_obs_total, queries_spent):
    """Cover all 5 seeds with remaining budget. Option B: spread evenly."""
    height, width = detail["map_height"], detail["map_width"]
    seeds_count = detail["seeds_count"]
    viewports = tile_viewports(height, width, 15)

    budget_info = session.get(f"{BASE}/astar-island/budget").json()
    remaining = budget_info["queries_max"] - budget_info["queries_used"]
    log(f"Observe: {remaining} queries left for {seeds_count} seeds")

    all_obs = {0: (initial_obs_counts.copy(), initial_obs_total.copy())}

    # Complete seed 0 first (partially covered by smell test)
    for vx, vy, vw, vh in viewports:
        if remaining <= 0:
            break
        if initial_obs_total[vy, vx] > 0:
            continue
        try:
            obs = query_viewport(session, round_id, 0, vx, vy, vw, vh)
            oc, ot = all_obs[0]
            for dy, row in enumerate(obs["grid"]):
                for dx, terrain in enumerate(row):
                    ya, xa = obs["viewport"]["y"] + dy, obs["viewport"]["x"] + dx
                    c = TERRAIN_TO_CLASS.get(terrain, 0)
                    oc[ya, xa, c] += 1
                    ot[ya, xa] += 1
            remaining -= 1
        except Exception as e:
            log(f"  Seed 0 query failed: {e}")
            break

    np.save(DATA_DIR / f"obs_counts_r{round_num}_seed0_overview.npy", all_obs[0][0])
    np.save(DATA_DIR / f"obs_total_r{round_num}_seed0_overview.npy", all_obs[0][1])
    s0_covered = (all_obs[0][1] > 0).sum()
    log(f"  Seed 0: {s0_covered}/{height*width} cells")

    # Seeds 1-4: distribute remaining queries evenly
    per_seed = remaining // (seeds_count - 1) if seeds_count > 1 else remaining
    for seed_idx in range(1, seeds_count):
        if remaining <= 0:
            break
        oc = np.zeros((height, width, NUM_CLASSES))
        ot = np.zeros((height, width))
        seed_budget = min(per_seed, remaining)

        for vx, vy, vw, vh in viewports:
            if seed_budget <= 0:
                break
            try:
                obs = query_viewport(session, round_id, seed_idx, vx, vy, vw, vh)
                for dy, row in enumerate(obs["grid"]):
                    for dx, terrain in enumerate(row):
                        ya, xa = obs["viewport"]["y"] + dy, obs["viewport"]["x"] + dx
                        c = TERRAIN_TO_CLASS.get(terrain, 0)
                        oc[ya, xa, c] += 1
                        ot[ya, xa] += 1
                seed_budget -= 1
                remaining -= 1
            except Exception as e:
                log(f"  Seed {seed_idx} query failed: {e}")
                break

        np.save(DATA_DIR / f"obs_counts_r{round_num}_seed{seed_idx}_overview.npy", oc)
        np.save(DATA_DIR / f"obs_total_r{round_num}_seed{seed_idx}_overview.npy", ot)
        all_obs[seed_idx] = (oc, ot)
        covered = (ot > 0).sum()
        log(f"  Seed {seed_idx}: {covered}/{height*width} cells")

    budget_info = session.get(f"{BASE}/astar-island/budget").json()
    log(f"  Budget: {budget_info['queries_used']}/{budget_info['queries_max']}")
    return all_obs


# ──────────────────────────────────────────────
# PHASE 3: Predict & Submit — Brain V3
# ──────────────────────────────────────────────
def predict_and_submit(session, round_id, detail, round_num,
                       all_obs, regime_info, dry_run=False):
    """Build predictions with Brain V3 and submit all 5 seeds."""
    height, width = detail["map_height"], detail["map_width"]
    seeds_count = detail["seeds_count"]
    regime = regime_info["regime"]

    # Load Brain V3 params
    alphas, temps = load_brain_params()

    # Train Brain (regime-specific model)
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from regime_model import RegimeModel
    brain = RegimeModel()

    # Load all cached rounds for training
    from backtest import load_cached_rounds
    for rd in load_cached_rounds():
        brain.add_training_data(rd)
    brain.finalize()
    brain.stats()

    # Build round-specific transition rates from observations
    r_trans = {}
    for si in all_obs:
        oc, ot = all_obs[si]
        ig = detail["initial_states"][si]["grid"]
        for y in range(height):
            for x in range(width):
                if ot[y, x] == 0:
                    continue
                init_cls = TERRAIN_TO_CLASS.get(int(ig[y][x]), 0)
                if int(ig[y][x]) in STATIC_TERRAIN:
                    continue
                final_cls = oc[y, x].argmax()
                if init_cls not in r_trans:
                    r_trans[init_cls] = np.zeros(NUM_CLASSES)
                r_trans[init_cls][final_cls] += 1
    for cls in r_trans:
        total = r_trans[cls].sum()
        if total > 0:
            r_trans[cls] = r_trans[cls] / total

    log(f"\nPredicting {seeds_count} seeds (regime={regime})...")

    for seed_idx in range(seeds_count):
        grid = detail["initial_states"][seed_idx]["grid"]

        # Brain V3 regime-specific prediction
        pred = brain.predict_grid(detail, seed_idx, regime=regime)

        # Per-terrain Dirichlet observation blending
        if seed_idx in all_obs:
            oc, ot = all_obs[seed_idx]
            for y in range(height):
                for x in range(width):
                    if ot[y, x] == 0:
                        continue
                    init_cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)
                    alpha_val = alphas.get(init_cls, 8.0)
                    alpha = alpha_val * pred[y, x]
                    alpha = np.maximum(alpha, PROB_FLOOR)
                    posterior = (alpha + oc[y, x]) / (alpha.sum() + ot[y, x])
                    pred[y, x] = posterior

        # Round-specific calibration for settlement/port cells
        for y in range(height):
            for x in range(width):
                if grid[y][x] in STATIC_TERRAIN:
                    continue
                init_cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)
                if init_cls in (1, 2) and init_cls in r_trans:
                    round_prior = r_trans[init_cls].copy()
                    if seed_idx in all_obs and all_obs[seed_idx][1][y, x] > 0:
                        obs_dist = all_obs[seed_idx][0][y, x] / all_obs[seed_idx][1][y, x]
                        pred[y, x] = 0.7 * obs_dist + 0.15 * pred[y, x] + 0.15 * round_prior
                    else:
                        pred[y, x] = 0.5 * round_prior + 0.5 * pred[y, x]

        # Port constraint
        ocean_adj = compute_ocean_adjacency(grid, height, width)
        for y in range(height):
            for x in range(width):
                if ocean_adj[y, x] == 0:
                    pred[y, x, 2] = PROB_FLOOR

        # Entropy-aware temperature scaling
        for y in range(height):
            for x in range(width):
                if grid[y][x] in STATIC_TERRAIN:
                    continue
                p = pred[y, x]
                p_safe = np.maximum(p, 1e-10)
                ent = -np.sum(p_safe * np.log(p_safe))
                if ent < 0.3:
                    t = temps.get("low", 0.9)
                elif ent < 1.0:
                    t = temps.get("mid", 1.1)
                else:
                    t = temps.get("high", 1.3)
                pred[y, x] = pred[y, x] ** (1.0 / t)

        # Fixed collapse thresholding
        for y in range(height):
            for x in range(width):
                if grid[y][x] in STATIC_TERRAIN:
                    continue
                probs = pred[y, x]
                mask = probs < DEFAULT_COLLAPSE
                if mask.any() and not mask.all():
                    probs[mask] = PROB_FLOOR
                    pred[y, x] = probs / probs.sum()

        # Spatial smoothing
        smoothed = np.copy(pred)
        for cls in range(NUM_CLASSES):
            smoothed[:, :, cls] = gaussian_filter(pred[:, :, cls], sigma=DEFAULT_SIGMA)
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
        obs_n = int(all_obs[seed_idx][1].sum()) if seed_idx in all_obs else 0
        log(f"Seed {seed_idx}: conf {avg_conf:.3f}, {obs_n} obs")

        if dry_run:
            log(f"  [DRY RUN]")
        else:
            for attempt in range(3):
                try:
                    resp = session.post(f"{BASE}/astar-island/submit", json={
                        "round_id": round_id, "seed_index": seed_idx,
                        "prediction": pred.tolist(),
                    })
                    resp.raise_for_status()
                    log(f"  SUBMITTED")
                    break
                except requests.HTTPError as e:
                    if e.response and e.response.status_code == 429:
                        time.sleep(2)
                        continue
                    log(f"  FAILED: {e}")
                    break

    log("\nChef v8 done!")


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Chef v8 — Astar Island")
    parser.add_argument("--token", required=True)
    parser.add_argument("--phase", required=True, choices=["smell", "observe", "submit", "all"])
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
    h, w = detail["map_height"], detail["map_width"]

    log(f"Round #{round_num}, weight {active['round_weight']:.4f}, "
        f"{remaining:.0f} min left, queries {budget['queries_used']}/50")

    if args.phase == "all":
        log("\n" + "=" * 50)
        log("CHEF V8: SMELL TEST + BRAIN V3")
        log("=" * 50)

        # Check if budget is already spent
        if budget["queries_used"] >= budget["queries_max"]:
            log("Budget exhausted. Loading existing observations...")
            all_obs = {}
            for si in range(detail["seeds_count"]):
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
                    regime_info = json.load(f)
            else:
                regime_info = {"regime": "stable", "confidence": 0.5}
        else:
            # Phase 1: Smell test
            obs_counts, obs_total, regime_info, q_used = smell_test(
                session, round_id, detail, round_num)

            # Phase 2: Observe all seeds
            log("\n" + "-" * 50)
            all_obs = observe_all_seeds(
                session, round_id, detail, round_num,
                obs_counts, obs_total, q_used)

        # Phase 3: Predict & submit
        log("\n" + "-" * 50)
        predict_and_submit(session, round_id, detail, round_num,
                           all_obs, regime_info, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
