#!/usr/bin/env python3
"""
Astar Island v7 — Multi-Seed + Regime Calibration

Key changes from v6:
- Taste ALL 5 kitchens (9 queries each = 45 total)
- Detect round regime from seed 0 (death/quiet/growth)
- Apply death calibration when detected
- Use remaining 5 queries on highest-value cells
- Port constraint: zero port probability on non-coastal cells

Usage:
  python astar_v7.py --token TOKEN --phase all         # Full pipeline
  python astar_v7.py --token TOKEN --phase observe     # Observe all seeds (45 queries)
  python astar_v7.py --token TOKEN --phase stack       # Use remaining queries (5)
  python astar_v7.py --token TOKEN --phase submit      # Build & submit predictions
  python astar_v7.py --token TOKEN --phase all --dry-run  # Dry run (no submission)
"""

import argparse
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

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


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def get_session(token: str) -> requests.Session:
    s = requests.Session()
    s.cookies.set("access_token", token, domain="api.ainm.no")
    s.headers["User-Agent"] = "astar-v7/nmiai-2026"
    return s


def get_active_round(session):
    rounds = session.get(f"{BASE}/astar-island/rounds").json()
    for r in rounds:
        if r["status"] == "active":
            return r
    return None


def get_round_detail(session, round_id):
    return session.get(f"{BASE}/astar-island/rounds/{round_id}").json()


def get_budget(session):
    return session.get(f"{BASE}/astar-island/budget").json()


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


def tile_viewports(height, width, vsize=15):
    viewports = []
    for vy in range(0, height, vsize):
        for vx in range(0, width, vsize):
            vh = min(vsize, height - vy)
            vw = min(vsize, width - vx)
            viewports.append((vx, vy, vw, vh))
    return viewports


def save_observations(obs_counts, obs_total, round_num, label=""):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tag = f"r{round_num}_{label}" if label else f"r{round_num}"
    np.save(DATA_DIR / f"obs_counts_{tag}.npy", obs_counts)
    np.save(DATA_DIR / f"obs_total_{tag}.npy", obs_total)
    log(f"  Saved observations: {tag}")


def load_observations(round_num, label=""):
    tag = f"r{round_num}_{label}" if label else f"r{round_num}"
    p_counts = DATA_DIR / f"obs_counts_{tag}.npy"
    p_total = DATA_DIR / f"obs_total_{tag}.npy"
    if p_counts.exists() and p_total.exists():
        return np.load(p_counts), np.load(p_total)
    return None, None


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
# PHASE 1: Observe ALL 5 seeds (9 queries each = 45 total)
# ──────────────────────────────────────────────
def phase_observe(session, round_id, detail, round_num):
    """Overview all 5 seeds. 9 queries per seed, 45 total."""
    height, width = detail["map_height"], detail["map_width"]
    seeds_count = detail["seeds_count"]
    viewports = tile_viewports(height, width, 15)  # 9 viewports

    log(f"Phase 1: Overview ALL {seeds_count} seeds ({len(viewports)} queries each)")

    all_settlement_stats = {}

    for seed_idx in range(seeds_count):
        grid = detail["initial_states"][seed_idx]["grid"]
        obs_counts = np.zeros((height, width, NUM_CLASSES))
        obs_total = np.zeros((height, width))
        settlement_stats = []

        for i, (vx, vy, vw, vh) in enumerate(viewports):
            try:
                obs = query_viewport(session, round_id, seed_idx, vx, vy, vw, vh)
                for dy, row in enumerate(obs["grid"]):
                    for dx, terrain in enumerate(row):
                        ya, xa = obs["viewport"]["y"] + dy, obs["viewport"]["x"] + dx
                        cls = TERRAIN_TO_CLASS.get(terrain, 0)
                        obs_counts[ya, xa, cls] += 1
                        obs_total[ya, xa] += 1
                for s in obs.get("settlements", []):
                    settlement_stats.append(s)
                budget = obs["queries_used"]
            except Exception as e:
                log(f"  Seed {seed_idx} [{i+1}] FAILED: {e}")
                break

        save_observations(obs_counts, obs_total, round_num, f"seed{seed_idx}_overview")
        all_settlement_stats[seed_idx] = settlement_stats

        # Log summary
        alive = [s for s in settlement_stats if s.get("alive")]
        changes = 0
        for y in range(height):
            for x in range(width):
                if obs_total[y, x] == 0:
                    continue
                initial_cls = TERRAIN_TO_CLASS.get(grid[y][x], 0)
                if obs_counts[y, x].argmax() != initial_cls:
                    changes += 1

        log(f"  Seed {seed_idx}: {len(alive)} settlements alive, "
            f"{changes} terrain changes, budget {budget}/50")

    # Save all settlement stats
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_DIR / f"settlement_stats_r{round_num}.json", "w") as f:
        json.dump(all_settlement_stats, f, default=str)

    # Detect regime from seed 0
    oc0, ot0 = load_observations(round_num, "seed0_overview")
    regime_info = detect_regime(oc0, ot0, detail["initial_states"][0]["grid"], height, width)
    log(f"\n  REGIME DETECTED: {regime_info['regime']}")
    log(f"  Settlement survival: {regime_info['survival_rate']:.0%}")
    log(f"  New settlements: {regime_info['new_settlements']} "
        f"(growth rate: {regime_info['growth_rate']:.2f})")

    # Save regime info
    with open(DATA_DIR / f"regime_r{round_num}.json", "w") as f:
        json.dump(regime_info, f, default=str)


def detect_regime(obs_counts, obs_total, grid, h, w):
    """Detect round regime from observations."""
    init_settlements = 0
    survived = 0
    new_settlements = 0

    for y in range(h):
        for x in range(w):
            if obs_total[y, x] == 0:
                continue
            cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)
            n = obs_total[y, x]
            if cls in (1, 2):
                init_settlements += 1
                sp_frac = (obs_counts[y, x, 1] + obs_counts[y, x, 2]) / n
                if sp_frac > 0.2:
                    survived += 1
            elif cls in (0, 4):
                sp_frac = (obs_counts[y, x, 1] + obs_counts[y, x, 2]) / n
                if sp_frac > 0.2:
                    new_settlements += 1

    survival_rate = survived / max(1, init_settlements)
    growth_rate = new_settlements / max(1, init_settlements)

    if survival_rate < 0.05:
        regime = "death"
    elif growth_rate > 1.0:
        regime = "growth"
    else:
        regime = "quiet"

    return {
        "survival_rate": float(survival_rate),
        "growth_rate": float(growth_rate),
        "regime": regime,
        "init_settlements": init_settlements,
        "survived": survived,
        "new_settlements": new_settlements,
    }


# ──────────────────────────────────────────────
# PHASE 2: Stack remaining queries on highest-value cells
# ──────────────────────────────────────────────
def phase_stack(session, round_id, detail, round_num, max_queries=5):
    """Use remaining queries on seed 0's highest-surprise cells."""
    height, width = detail["map_height"], detail["map_width"]
    budget = get_budget(session)
    remaining = budget["queries_max"] - budget["queries_used"]
    n_queries = min(remaining, max_queries)

    if n_queries <= 0:
        log("Phase 2: No queries remaining.")
        return

    log(f"Phase 2: Stacking {n_queries} queries on seed 0 high-value cells")

    # Load seed 0 overview observations
    obs_counts, obs_total = load_observations(round_num, "seed0_overview")
    if obs_counts is None:
        log("  No seed 0 overview data found. Skip.")
        return

    grid = detail["initial_states"][0]["grid"]

    # Compute surprise: where did observation differ most from prior?
    # Target settlements and dynamic areas
    heat = np.zeros((height, width))
    for y in range(height):
        for x in range(width):
            if grid[y][x] in STATIC_TERRAIN:
                continue
            cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)
            if cls in (1, 2):
                heat[y, x] += 5  # settlements highest priority
            elif cls in (0, 4):
                # Check if observation showed change
                if obs_total[y, x] > 0:
                    observed = obs_counts[y, x].argmax()
                    if observed != cls:
                        heat[y, x] += 3  # terrain changed

    # Select viewports by heat
    used = np.zeros((height, width), dtype=bool)
    for i in range(n_queries):
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
            break

        vx, vy, vw, vh = best_vp
        try:
            obs = query_viewport(session, round_id, 0, vx, vy, vw, vh)
            for dy, row in enumerate(obs["grid"]):
                for dx, terrain in enumerate(row):
                    ya, xa = obs["viewport"]["y"] + dy, obs["viewport"]["x"] + dx
                    c = TERRAIN_TO_CLASS.get(terrain, 0)
                    obs_counts[ya, xa, c] += 1
                    obs_total[ya, xa] += 1
            used[vy:vy+15, vx:vx+15] = True
            b = obs["queries_used"]
            log(f"  [{i+1}/{n_queries}] ({vx},{vy}) — budget {b}/50")
        except Exception as e:
            log(f"  [{i+1}] FAILED: {e}")
            break

    save_observations(obs_counts, obs_total, round_num, "seed0_stacked")
    multi = (obs_total >= 2).sum()
    log(f"  Seed 0 now has {multi} cells with 2+ samples")


# ──────────────────────────────────────────────
# PHASE 3: Build predictions & submit
# ──────────────────────────────────────────────
def phase_submit(session, round_id, detail, round_num, dry_run=False):
    """Build predictions with V2 model + regime calibration, submit all seeds."""
    height, width = detail["map_height"], detail["map_width"]
    seeds_count = detail["seeds_count"]

    # Load observations for ALL seeds
    all_obs = {}
    for seed_idx in range(seeds_count):
        # Try stacked first (seed 0), then overview
        for label in [f"seed{seed_idx}_stacked", f"seed{seed_idx}_overview"]:
            oc, ot = load_observations(round_num, label)
            if oc is not None:
                if seed_idx in all_obs:
                    prev_oc, prev_ot = all_obs[seed_idx]
                    mask = ot > prev_ot
                    prev_oc[mask] = oc[mask]
                    prev_ot[mask] = ot[mask]
                else:
                    all_obs[seed_idx] = (oc.copy(), ot.copy())

    obs_seeds = list(all_obs.keys())
    log(f"Loaded observations for seeds: {obs_seeds}")

    # Load regime info
    regime_path = DATA_DIR / f"regime_r{round_num}.json"
    regime_info = None
    if regime_path.exists():
        with open(regime_path) as f:
            regime_info = json.load(f)
        log(f"Regime: {regime_info['regime']} (survival={regime_info['survival_rate']:.0%})")
    else:
        log("No regime info found, using default (quiet)")
        regime_info = {"regime": "quiet", "survival_rate": 0.4}

    # Train V2 model on all completed rounds
    from churn import NeighborhoodModelV2
    learned = NeighborhoodModelV2()
    rounds = session.get(f"{BASE}/astar-island/rounds").json()
    completed = [r for r in rounds if r["status"] == "completed"]

    for r in completed:
        rd_id = r["id"]
        rd_detail = session.get(f"{BASE}/astar-island/rounds/{rd_id}").json()
        rd_data = {
            "round_number": r["round_number"],
            "map_height": rd_detail["map_height"],
            "map_width": rd_detail["map_width"],
            "initial_states": rd_detail["initial_states"],
            "seeds": {},
        }
        for si in range(rd_detail.get("seeds_count", 5)):
            resp = session.get(f"{BASE}/astar-island/analysis/{rd_id}/{si}")
            if resp.status_code == 200:
                rd_data["seeds"][str(si)] = resp.json()
        if rd_data["seeds"]:
            learned.add_training_data(rd_data)
    learned.finalize()
    learned.stats()

    # Build and submit predictions
    log(f"\nBuilding predictions for {seeds_count} seeds...")
    for seed_idx in range(seeds_count):
        grid = detail["initial_states"][seed_idx]["grid"]

        # V2 model prediction with observations
        pred = learned.predict_grid_with_obs(
            detail, seed_idx,
            obs_counts=all_obs[seed_idx][0] if seed_idx in all_obs else None,
            obs_total=all_obs[seed_idx][1] if seed_idx in all_obs else None,
            prior_strength=12.0,
        )

        # REGIME CALIBRATION
        if regime_info["regime"] == "death":
            # Death round: all settlements die
            for y in range(height):
                for x in range(width):
                    if grid[y][x] in STATIC_TERRAIN:
                        continue
                    cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)
                    if cls in (1, 2):
                        pred[y, x, 0] = 0.65  # empty
                        pred[y, x, 1] = 0.02  # settlement
                        pred[y, x, 2] = 0.01  # port
                        pred[y, x, 3] = 0.02  # ruin
                        pred[y, x, 4] = 0.28  # forest
                        pred[y, x, 5] = 0.01
                    # Non-settlement: very unlikely to become settlement
                    pred[y, x, 1] *= 0.05
                    pred[y, x, 2] *= 0.05

        # PORT CONSTRAINT: no ports far from ocean
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
                    probs[mask] = 0.0
                    probs[:] = np.maximum(probs, PROB_FLOOR)
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

        # Stats
        avg_conf = pred.max(axis=-1).mean()
        dynamic_mask = np.array([[grid[y][x] not in STATIC_TERRAIN
                                  for x in range(width)] for y in range(height)])
        dyn_conf = pred.max(axis=-1)[dynamic_mask].mean()
        obs_str = f", {int(all_obs[seed_idx][1].sum())} obs" if seed_idx in all_obs else ""
        log(f"Seed {seed_idx}: conf {avg_conf:.3f} (dyn {dyn_conf:.3f}){obs_str}")

        if dry_run:
            log(f"  [DRY RUN]")
        else:
            for attempt in range(3):
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
                        time.sleep(2)
                        continue
                    log(f"  Failed: {e}")
                    break

    log("\nDone!")


def main():
    parser = argparse.ArgumentParser(description="Astar Island v7 — Multi-Seed + Regime Calibration")
    parser.add_argument("--token", required=True)
    parser.add_argument("--phase", required=True,
                        choices=["observe", "stack", "submit", "all"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-stack", type=int, default=5,
                        help="Max extra queries for stacking (default: 5)")
    args = parser.parse_args()

    session = get_session(args.token)

    active = get_active_round(session)
    if not active:
        log("No active round.")
        return

    round_id = active["id"]
    round_num = active["round_number"]
    closes = datetime.fromisoformat(active["closes_at"])
    remaining = (closes - datetime.now(timezone.utc)).total_seconds() / 60
    detail = get_round_detail(session, round_id)
    budget = get_budget(session)
    log(f"Round #{round_num}, weight {active['round_weight']:.4f}, "
        f"{remaining:.0f} min left, queries {budget['queries_used']}/50")

    if args.phase == "observe":
        phase_observe(session, round_id, detail, round_num)
    elif args.phase == "stack":
        phase_stack(session, round_id, detail, round_num, args.max_stack)
    elif args.phase == "submit":
        phase_submit(session, round_id, detail, round_num, dry_run=args.dry_run)
    elif args.phase == "all":
        log("\n" + "=" * 50)
        log("V7: MULTI-SEED + REGIME CALIBRATION")
        log("=" * 50)
        phase_observe(session, round_id, detail, round_num)
        log("\n" + "-" * 50)
        phase_stack(session, round_id, detail, round_num, args.max_stack)
        log("\n" + "-" * 50)
        phase_submit(session, round_id, detail, round_num, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
