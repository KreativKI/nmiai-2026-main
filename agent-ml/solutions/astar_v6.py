#!/usr/bin/env python3
"""
Astar Island v6 — Phased Observation Strategy

Executes in phases with analysis between each phase:
  Phase 1: Full overview of seed 0 (9 queries, 3x3 tiling)
  Phase 2: Analyze dynamics, identify high-uncertainty zones (0 queries)
  Phase 3: Stack queries on dynamic zones for multi-sample estimates (20-25 queries)
  Phase 4: Cover seeds 1-2 for cross-seed validation (16 queries)
  Phase 5: Build final predictions & submit all 5 seeds

Each phase can be run independently or all at once.

Usage:
  python astar_v6.py --token TOKEN --phase overview    # Phase 1: overview
  python astar_v6.py --token TOKEN --phase analyze     # Phase 2: analyze
  python astar_v6.py --token TOKEN --phase stack       # Phase 3: stack queries
  python astar_v6.py --token TOKEN --phase secondary   # Phase 4: seeds 1-2
  python astar_v6.py --token TOKEN --phase submit      # Phase 5: build & submit
  python astar_v6.py --token TOKEN --phase all         # Run all phases
  python astar_v6.py --token TOKEN --phase post-round  # Post-round analysis
"""

import argparse
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

import numpy as np
import requests

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
    s.headers["User-Agent"] = "astar-v6/nmiai-2026"
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
    """Generate non-overlapping viewports that tile the full map."""
    viewports = []
    for vy in range(0, height, vsize):
        for vx in range(0, width, vsize):
            vh = min(vsize, height - vy)
            vw = min(vsize, width - vx)
            viewports.append((vx, vy, vw, vh))
    return viewports


def save_observations(obs_counts, obs_total, round_num, label=""):
    """Save observation arrays to disk for persistence between phases."""
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


def learn_historical_transitions(session):
    """Learn from ALL completed rounds' ground truth."""
    rounds = session.get(f"{BASE}/astar-island/rounds").json()
    completed = [r for r in rounds if r["status"] == "completed"]
    if not completed:
        return None

    sums = {k: np.zeros((NUM_CLASSES, NUM_CLASSES)) for k in ["global", "near", "far"]}
    counts = {k: np.zeros(NUM_CLASSES) for k in ["global", "near", "far"]}

    for r in completed:
        round_id = r["id"]
        detail = session.get(f"{BASE}/astar-island/rounds/{round_id}").json()
        for seed_idx in range(detail.get("seeds_count", 5)):
            resp = session.get(f"{BASE}/astar-island/analysis/{round_id}/{seed_idx}")
            if resp.status_code != 200:
                continue
            data = resp.json()
            ig = data["initial_grid"]
            gt = np.array(data["ground_truth"])
            h, w = len(ig), len(ig[0])
            for y in range(h):
                for x in range(w):
                    cls = TERRAIN_TO_CLASS.get(ig[y][x], 0)
                    sums["global"][cls] += gt[y][x]
                    counts["global"][cls] += 1
                    has_adj = any(
                        0 <= y+dy < h and 0 <= x+dx < w
                        and TERRAIN_TO_CLASS.get(ig[y+dy][x+dx], 0) in (1, 2)
                        for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                        if (dy, dx) != (0, 0)
                    )
                    key = "near" if has_adj else "far"
                    sums[key][cls] += gt[y][x]
                    counts[key][cls] += 1
        log(f"  Learned from round {r['round_number']}")

    def normalize(s, c):
        mat = np.full((NUM_CLASSES, NUM_CLASSES), PROB_FLOOR)
        for i in range(NUM_CLASSES):
            if c[i] > 0:
                mat[i] = s[i] / c[i]
        mat = np.maximum(mat, PROB_FLOOR)
        return mat / mat.sum(axis=1, keepdims=True)

    return {k: normalize(sums[k], counts[k]) for k in ["global", "near", "far"]}


# ──────────────────────────────────────────────
# PHASE 1: Full overview of seed 0
# ──────────────────────────────────────────────
def phase_overview(session, round_id, detail, round_num):
    """Tile seed 0 with 3x3 viewports (9 queries) for full map overview."""
    height, width = detail["map_height"], detail["map_width"]
    grid = detail["initial_states"][0]["grid"]
    viewports = tile_viewports(height, width, 15)

    log(f"Phase 1: Overview of seed 0 ({len(viewports)} viewports)")
    obs_counts = np.zeros((height, width, NUM_CLASSES))
    obs_total = np.zeros((height, width))
    settlement_stats = []  # Capture settlement stats from observations

    for i, (vx, vy, vw, vh) in enumerate(viewports):
        try:
            obs = query_viewport(session, round_id, 0, vx, vy, vw, vh)
            for dy, row in enumerate(obs["grid"]):
                for dx, terrain in enumerate(row):
                    ya, xa = obs["viewport"]["y"] + dy, obs["viewport"]["x"] + dx
                    cls = TERRAIN_TO_CLASS.get(terrain, 0)
                    obs_counts[ya, xa, cls] += 1
                    obs_total[ya, xa] += 1
            # Capture settlement stats (population, food, wealth, defense, faction)
            for s in obs.get("settlements", []):
                settlement_stats.append(s)
            budget = obs["queries_used"]
            log(f"  [{i+1}/{len(viewports)}] ({vx},{vy}) {vw}x{vh} — budget {budget}/50")
        except Exception as e:
            log(f"  [{i+1}] FAILED: {e}")
            break

    # Log settlement stats summary
    alive = [s for s in settlement_stats if s.get("alive")]
    dead = [s for s in settlement_stats if not s.get("alive")]
    if alive:
        avg_food = np.mean([s.get("food", 0) for s in alive])
        avg_pop = np.mean([s.get("population", 0) for s in alive])
        factions = set(s.get("owner_id") for s in alive)
        log(f"  Settlements: {len(alive)} alive, {len(dead)} dead, "
            f"{len(factions)} factions, avg food={avg_food:.2f}, avg pop={avg_pop:.2f}")
    # Save settlement stats
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_DIR / f"settlement_stats_r{round_num}.json", "w") as f:
        json.dump(settlement_stats, f)

    # Compare with initial terrain
    changes = 0
    change_details = Counter()
    for y in range(height):
        for x in range(width):
            if obs_total[y, x] == 0:
                continue
            initial_cls = TERRAIN_TO_CLASS.get(grid[y][x], 0)
            observed_cls = obs_counts[y, x].argmax()
            if initial_cls != observed_cls:
                changes += 1
                change_details[(CLASS_NAMES[initial_cls], CLASS_NAMES[observed_cls])] += 1

    log(f"\n  Overview results: {int(obs_total.sum())} cells observed")
    log(f"  Terrain changes from initial: {changes}")
    for (frm, to), cnt in change_details.most_common(10):
        log(f"    {frm} -> {to}: {cnt}")

    save_observations(obs_counts, obs_total, round_num, "seed0_overview")
    return obs_counts, obs_total


# ──────────────────────────────────────────────
# PHASE 2: Analyze dynamics
# ──────────────────────────────────────────────
def phase_analyze(detail, round_num):
    """Analyze overview data, identify high-uncertainty zones. No queries spent."""
    height, width = detail["map_height"], detail["map_width"]
    grid = detail["initial_states"][0]["grid"]

    obs_counts, obs_total = load_observations(round_num, "seed0_overview")
    if obs_counts is None:
        log("Phase 2: No overview data found. Run phase 'overview' first.")
        return None

    log("Phase 2: Analyzing dynamics from overview...")

    # Build round-specific transition from single observation
    transition = np.zeros((NUM_CLASSES, NUM_CLASSES))
    trans_counts = np.zeros(NUM_CLASSES)
    dynamic_cells = []

    for y in range(height):
        for x in range(width):
            if obs_total[y, x] == 0:
                continue
            initial_cls = TERRAIN_TO_CLASS.get(grid[y][x], 0)
            observed_cls = int(obs_counts[y, x].argmax())
            transition[initial_cls][observed_cls] += 1
            trans_counts[initial_cls] += 1

            # Track cells that changed (these are dynamic/uncertain)
            if initial_cls != observed_cls:
                dynamic_cells.append((y, x, initial_cls, observed_cls))

    # Normalize transition
    for i in range(NUM_CLASSES):
        if trans_counts[i] > 0:
            transition[i] = transition[i] / trans_counts[i]
        else:
            transition[i] = PROB_FLOOR
    transition = np.maximum(transition, PROB_FLOOR)
    transition = transition / transition.sum(axis=1, keepdims=True)

    log("  Round-specific transitions (from 1 observation):")
    for i, name in enumerate(CLASS_NAMES):
        if trans_counts[i] > 5:
            top = sorted(range(NUM_CLASSES), key=lambda j: transition[i][j], reverse=True)[:3]
            s = ", ".join(f"{CLASS_NAMES[j]}:{transition[i][j]:.3f}" for j in top)
            log(f"    {name} ({int(trans_counts[i])} cells) -> {s}")

    log(f"\n  Dynamic cells (changed from initial): {len(dynamic_cells)}")
    # Group dynamic cells by region for targeted stacking
    if dynamic_cells:
        ys = [c[0] for c in dynamic_cells]
        xs = [c[1] for c in dynamic_cells]
        log(f"    Y range: {min(ys)}-{max(ys)}, X range: {min(xs)}-{max(xs)}")

    # Identify stacking targets: regions with highest dynamic cell density
    # Use a heatmap approach
    heat = np.zeros((height, width))
    for y, x, _, _ in dynamic_cells:
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                ny, nx = y + dy, x + dx
                if 0 <= ny < height and 0 <= nx < width:
                    heat[ny, nx] += 1.0 / (abs(dy) + abs(dx) + 1)

    # Also add priority for cells near settlements/ports (even if they didn't change
    # in THIS observation, they're stochastic)
    for y in range(height):
        for x in range(width):
            cls = TERRAIN_TO_CLASS.get(grid[y][x], 0)
            if cls in (1, 2):
                heat[y, x] += 3
            elif cls == 3:
                heat[y, x] += 2
            elif grid[y][x] not in STATIC_TERRAIN:
                # Empty/forest near settlements
                has_adj = any(
                    0 <= y+dy < height and 0 <= x+dx < width
                    and TERRAIN_TO_CLASS.get(grid[y+dy][x+dx], 0) in (1, 2)
                    for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                    if (dy, dx) != (0, 0)
                )
                if has_adj:
                    heat[y, x] += 2

    # Select top viewport positions for stacking
    stack_targets = []
    used = np.zeros((height, width), dtype=bool)
    for _ in range(8):  # Up to 8 stacking viewports
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
        if best_vp and best_score > 0:
            stack_targets.append(best_vp)
            vx, vy, _, _ = best_vp
            used[vy:vy+15, vx:vx+15] = True

    log(f"\n  Recommended stacking targets ({len(stack_targets)} viewports):")
    for i, (vx, vy, vw, vh) in enumerate(stack_targets):
        region_heat = heat[vy:vy+vh, vx:vx+vw].sum()
        log(f"    [{i+1}] ({vx},{vy}) {vw}x{vh} — heat: {region_heat:.1f}")

    # Save analysis results
    np.save(DATA_DIR / f"heat_r{round_num}.npy", heat)
    with open(DATA_DIR / f"stack_targets_r{round_num}.json", "w") as f:
        json.dump(stack_targets, f)
    np.save(DATA_DIR / f"transition_round_{round_num}_obs.npy", transition)

    return stack_targets


# ──────────────────────────────────────────────
# PHASE 3: Stack queries on dynamic zones
# ──────────────────────────────────────────────
def phase_stack(session, round_id, detail, round_num, max_queries=25):
    """Stack 2-3 queries on each high-uncertainty zone for multi-sample estimates."""
    height, width = detail["map_height"], detail["map_width"]

    # Load stacking targets from phase 2
    targets_path = DATA_DIR / f"stack_targets_r{round_num}.json"
    if not targets_path.exists():
        log("Phase 3: No stacking targets. Run phase 'analyze' first.")
        return None, None

    with open(targets_path) as f:
        targets = json.load(f)

    # Load existing observations
    obs_counts, obs_total = load_observations(round_num, "seed0_overview")
    if obs_counts is None:
        obs_counts = np.zeros((height, width, NUM_CLASSES))
        obs_total = np.zeros((height, width))

    budget = get_budget(session)
    available = budget["queries_max"] - budget["queries_used"]
    n_queries = min(max_queries, available)

    if n_queries <= 0:
        log("Phase 3: No queries available.")
        return obs_counts, obs_total

    # Distribute queries: 4 passes over top targets for ~5 samples/cell
    query_plan = []
    passes = 4
    for p in range(passes):
        for vp in targets:
            if len(query_plan) >= n_queries:
                break
            query_plan.append((0, vp))  # All on seed 0
        if len(query_plan) >= n_queries:
            break

    log(f"Phase 3: Stacking {len(query_plan)} queries on seed 0 "
        f"({len(targets)} zones, {passes} passes)")

    for i, (seed_idx, (vx, vy, vw, vh)) in enumerate(query_plan):
        try:
            obs = query_viewport(session, round_id, seed_idx, vx, vy, vw, vh)
            for dy, row in enumerate(obs["grid"]):
                for dx, terrain in enumerate(row):
                    ya = obs["viewport"]["y"] + dy
                    xa = obs["viewport"]["x"] + dx
                    cls = TERRAIN_TO_CLASS.get(terrain, 0)
                    obs_counts[ya, xa, cls] += 1
                    obs_total[ya, xa] += 1
            log(f"  [{i+1}/{len(query_plan)}] seed {seed_idx} ({vx},{vy}) — "
                f"budget {obs['queries_used']}/50")
        except requests.HTTPError as e:
            if e.response and e.response.status_code == 429:
                log(f"  Budget exhausted at query {i+1}")
                break
            log(f"  Failed: {e}")
            continue

    multi = int((obs_total > 1).sum())
    max_samples = int(obs_total.max())
    log(f"\n  After stacking: {multi} cells with 2+ samples, max {max_samples} samples")

    save_observations(obs_counts, obs_total, round_num, "seed0_stacked")
    return obs_counts, obs_total


# ──────────────────────────────────────────────
# PHASE 4: Cover seeds 1-2
# ──────────────────────────────────────────────
def phase_secondary(session, round_id, detail, round_num, max_queries=16):
    """Cover seeds 1-2 for cross-seed validation."""
    height, width = detail["map_height"], detail["map_width"]

    budget = get_budget(session)
    available = budget["queries_max"] - budget["queries_used"]
    n_queries = min(max_queries, available)

    if n_queries <= 0:
        log("Phase 4: No queries available.")
        return {}

    # Allocate: seed 1 gets 9 (full), seed 2 gets remainder
    seed1_budget = min(9, n_queries)
    seed2_budget = n_queries - seed1_budget

    results = {}
    for seed_idx, seed_budget in [(1, seed1_budget), (2, seed2_budget)]:
        if seed_budget <= 0:
            continue

        obs_counts = np.zeros((height, width, NUM_CLASSES))
        obs_total = np.zeros((height, width))

        if seed_budget >= 9:
            viewports = tile_viewports(height, width, 15)[:seed_budget]
        else:
            # Partial coverage: use stacking targets from phase 2
            targets_path = DATA_DIR / f"stack_targets_r{round_num}.json"
            if targets_path.exists():
                with open(targets_path) as f:
                    viewports = json.load(f)[:seed_budget]
            else:
                viewports = tile_viewports(height, width, 15)[:seed_budget]

        log(f"  Seed {seed_idx}: {len(viewports)} viewports")
        for i, (vx, vy, vw, vh) in enumerate(viewports):
            try:
                obs = query_viewport(session, round_id, seed_idx, vx, vy, vw, vh)
                for dy, row in enumerate(obs["grid"]):
                    for dx, terrain in enumerate(row):
                        ya = obs["viewport"]["y"] + dy
                        xa = obs["viewport"]["x"] + dx
                        cls = TERRAIN_TO_CLASS.get(terrain, 0)
                        obs_counts[ya, xa, cls] += 1
                        obs_total[ya, xa] += 1
                log(f"    [{i+1}/{len(viewports)}] ({vx},{vy}) — "
                    f"budget {obs['queries_used']}/50")
            except requests.HTTPError as e:
                if e.response and e.response.status_code == 429:
                    log(f"    Budget exhausted")
                    break
                log(f"    Failed: {e}")
                continue

        save_observations(obs_counts, obs_total, round_num, f"seed{seed_idx}")
        results[seed_idx] = (obs_counts, obs_total)
        log(f"  Seed {seed_idx}: {int((obs_total > 0).sum())} cells observed")

    return results


# ──────────────────────────────────────────────
# PHASE 5: Build predictions & submit
# ──────────────────────────────────────────────
def phase_submit(session, round_id, detail, round_num, hist_trans, dry_run=False):
    """Build final predictions and submit all 5 seeds."""
    height, width = detail["map_height"], detail["map_width"]
    seeds_count = detail["seeds_count"]

    # Load all observation data
    all_obs = {}
    for label_seed in [(0, "seed0_stacked"), (0, "seed0_overview"),
                        (1, "seed1"), (2, "seed2")]:
        seed_idx, label = label_seed
        oc, ot = load_observations(round_num, label)
        if oc is not None:
            if seed_idx in all_obs:
                # Merge: stacked has more data than overview
                prev_oc, prev_ot = all_obs[seed_idx]
                # Use whichever has more data per cell
                mask = ot > prev_ot
                prev_oc[mask] = oc[mask]
                prev_ot[mask] = ot[mask]
            else:
                all_obs[seed_idx] = (oc, ot)

    log(f"Loaded observations for seeds: {list(all_obs.keys())}")

    # Build round-specific transitions from all observed data
    round_trans_sums = {k: np.zeros((NUM_CLASSES, NUM_CLASSES))
                        for k in ["global", "near", "far"]}
    round_trans_counts = {k: np.zeros(NUM_CLASSES)
                          for k in ["global", "near", "far"]}

    for seed_idx, (oc, ot) in all_obs.items():
        grid = detail["initial_states"][seed_idx]["grid"]
        for y in range(height):
            for x in range(width):
                if ot[y, x] == 0:
                    continue
                cls = TERRAIN_TO_CLASS.get(grid[y][x], 0)
                empirical = oc[y, x] / ot[y, x]

                round_trans_sums["global"][cls] += empirical
                round_trans_counts["global"][cls] += 1

                has_adj = any(
                    0 <= y+dy < height and 0 <= x+dx < width
                    and TERRAIN_TO_CLASS.get(grid[y+dy][x+dx], 0) in (1, 2)
                    for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                    if (dy, dx) != (0, 0)
                )
                key = "near" if has_adj else "far"
                round_trans_sums[key][cls] += empirical
                round_trans_counts[key][cls] += 1

    def normalize(s, c):
        mat = np.full((NUM_CLASSES, NUM_CLASSES), PROB_FLOOR)
        for i in range(NUM_CLASSES):
            if c[i] > 0:
                mat[i] = s[i] / c[i]
        mat = np.maximum(mat, PROB_FLOOR)
        return mat / mat.sum(axis=1, keepdims=True)

    round_trans = {k: normalize(round_trans_sums[k], round_trans_counts[k])
                   for k in ["global", "near", "far"]}

    # Blend round-specific with historical
    # More round observations = trust round-specific more
    total_round_obs = sum(round_trans_counts["global"])
    has_round_obs = total_round_obs > 50
    if has_round_obs:
        # Scale: 50 obs -> 70%, 1000 obs -> 85%, 3000+ obs -> 90%
        blend_w = min(0.9, 0.7 + (total_round_obs - 50) / 10000)
        log(f"Blending transitions: {blend_w:.0%} round-specific ({int(total_round_obs)} obs), "
            f"{1-blend_w:.0%} historical")
    else:
        blend_w = 0.0
        log("No round observations. Using historical transitions only.")

    final_trans = {}
    for k in ["global", "near", "far"]:
        final_trans[k] = blend_w * round_trans[k] + (1 - blend_w) * hist_trans[k]
        final_trans[k] = np.maximum(final_trans[k], PROB_FLOOR)
        final_trans[k] = final_trans[k] / final_trans[k].sum(axis=1, keepdims=True)

    # Log key transitions
    log("Final transitions (global):")
    for i, name in enumerate(CLASS_NAMES):
        top = sorted(range(NUM_CLASSES), key=lambda j: final_trans["global"][i][j],
                      reverse=True)[:3]
        s = ", ".join(f"{CLASS_NAMES[j]}:{final_trans['global'][i][j]:.3f}" for j in top)
        log(f"  {name} -> {s}")

    # Build and submit predictions
    log(f"\nBuilding predictions for {seeds_count} seeds...")
    for seed_idx in range(seeds_count):
        grid = detail["initial_states"][seed_idx]["grid"]
        pred = np.full((height, width, NUM_CLASSES), PROB_FLOOR)

        # Precompute settlement positions for distance calculation
        settlement_positions = []
        for y in range(height):
            for x in range(width):
                if TERRAIN_TO_CLASS.get(grid[y][x], 0) in (1, 2):
                    settlement_positions.append((y, x))

        # Precompute distance-to-nearest-settlement for every cell
        dist_map = np.full((height, width), 99)
        for sy, sx in settlement_positions:
            for y in range(height):
                for x in range(width):
                    d = abs(y - sy) + abs(x - sx)
                    dist_map[y, x] = min(dist_map[y, x], d)

        for y in range(height):
            for x in range(width):
                terrain = grid[y][x]
                cls = TERRAIN_TO_CLASS.get(terrain, 0)

                if terrain in STATIC_TERRAIN:
                    pred[y, x] = final_trans["global"][cls]
                    continue

                # Distance-weighted blending between near and far transitions
                # Lowered from 0.8/0.6/0.3: backtest BT-001 test 9 showed +0.8 avg
                dist = dist_map[y, x]
                if dist <= 1:
                    w_near = 0.6
                elif dist <= 3:
                    w_near = 0.4
                elif dist <= 5:
                    w_near = 0.2
                else:
                    w_near = 0.0

                base = w_near * final_trans["near"][cls] + \
                       (1 - w_near) * final_trans["far"][cls]

                pred[y, x] = base

        # Blend with direct observations for this seed
        # Key: high-entropy cells (settlements, ports) benefit most from observations
        # Low-entropy cells (forests, plains) are already well-predicted by transition model
        if seed_idx in all_obs:
            oc, ot = all_obs[seed_idx]
            has_obs = ot > 0
            if has_obs.any():
                ot_3d = ot[..., np.newaxis]
                empirical = oc / np.maximum(ot_3d, 1)

                # Terrain-aware observation weight:
                # Settlements/Ports: trust observations heavily (0.5 to 0.95)
                # Forests/Plains: trust observations less (0.1 to 0.4)
                obs_w = np.zeros((height, width, 1))
                for y in range(height):
                    for x in range(width):
                        if ot[y, x] == 0:
                            continue
                        terrain = grid[y][x]
                        cls = TERRAIN_TO_CLASS.get(terrain, 0)
                        n = ot[y, x]
                        if cls in (1, 2, 3):  # Settlement, Port, Ruin: high value
                            obs_w[y, x, 0] = min(0.95, 0.5 + n / 15.0)
                        elif cls == 4:  # Forest: moderate value
                            obs_w[y, x, 0] = min(0.4, 0.1 + n / 20.0)
                        else:  # Empty/Plains: low value
                            obs_w[y, x, 0] = min(0.35, 0.1 + n / 25.0)

                pred = np.where(
                    has_obs[..., np.newaxis],
                    obs_w * empirical + (1 - obs_w) * pred,
                    pred
                )

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
        obs_str = ""
        if seed_idx in all_obs:
            obs_str = f", {int(all_obs[seed_idx][1].sum())} obs"
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
    parser = argparse.ArgumentParser(description="Astar Island v6 — Phased Strategy")
    parser.add_argument("--token", required=True)
    parser.add_argument("--phase", required=True,
                        choices=["overview", "analyze", "stack", "secondary",
                                 "submit", "all", "post-round"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-stack", type=int, default=32,
                        help="Max queries for stacking phase (default: 32 for 4 passes over 8 zones)")
    parser.add_argument("--max-secondary", type=int, default=9,
                        help="Max queries for secondary seeds (default: 9 = seed 1 full coverage)")
    args = parser.parse_args()

    session = get_session(args.token)

    # Learn historical transitions
    log("Learning from completed rounds...")
    hist_trans = learn_historical_transitions(session)
    if hist_trans is None:
        hist_trans = {k: np.full((NUM_CLASSES, NUM_CLASSES), 1/NUM_CLASSES)
                      for k in ["global", "near", "far"]}

    # Find active round
    active = get_active_round(session)
    if not active and args.phase != "post-round":
        log("No active round.")
        return

    if active:
        round_id = active["id"]
        round_num = active["round_number"]
        closes = datetime.fromisoformat(active["closes_at"])
        remaining = (closes - datetime.now(timezone.utc)).total_seconds() / 60
        detail = get_round_detail(session, round_id)
        budget = get_budget(session)
        log(f"Round #{round_num}, weight {active['round_weight']:.4f}, "
            f"{remaining:.0f} min left, queries {budget['queries_used']}/50")

    if args.phase == "overview":
        phase_overview(session, round_id, detail, round_num)
    elif args.phase == "analyze":
        phase_analyze(detail, round_num)
    elif args.phase == "stack":
        phase_stack(session, round_id, detail, round_num, args.max_stack)
    elif args.phase == "secondary":
        phase_secondary(session, round_id, detail, round_num, args.max_secondary)
    elif args.phase == "submit":
        phase_submit(session, round_id, detail, round_num, hist_trans,
                     dry_run=args.dry_run)
    elif args.phase == "all":
        log("\n" + "="*50)
        log("RUNNING ALL PHASES")
        log("="*50)
        phase_overview(session, round_id, detail, round_num)
        log("\n" + "-"*50)
        phase_analyze(detail, round_num)
        log("\n" + "-"*50)
        phase_stack(session, round_id, detail, round_num, args.max_stack)
        log("\n" + "-"*50)
        phase_secondary(session, round_id, detail, round_num, args.max_secondary)
        log("\n" + "-"*50)
        phase_submit(session, round_id, detail, round_num, hist_trans,
                     dry_run=args.dry_run)
    elif args.phase == "post-round":
        rounds = session.get(f"{BASE}/astar-island/rounds").json()
        completed = [r for r in rounds if r["status"] == "completed"]
        for r in sorted(completed, key=lambda r: r["round_number"]):
            d = get_round_detail(session, r["id"])
            log(f"\n=== Round {r['round_number']} (weight {r['round_weight']:.4f}) ===")
            for si in range(d.get("seeds_count", 5)):
                resp = session.get(f"{BASE}/astar-island/analysis/{r['id']}/{si}")
                if resp.status_code != 200:
                    continue
                data = resp.json()
                log(f"  Seed {si}: score = {data.get('score', 'N/A')}")


if __name__ == "__main__":
    main()
