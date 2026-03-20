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
# PHASE 3: Adaptive stacking with hindsight
# ──────────────────────────────────────────────
def compute_surprise(obs_counts, obs_total, grid, hist_trans, height, width):
    """Compute per-cell surprise: how much observations disagree with model prior.

    Returns a surprise map (H x W) where high values = model was most wrong.
    These cells benefit most from additional observations.
    """
    surprise = np.zeros((height, width))
    for y in range(height):
        for x in range(width):
            if obs_total[y, x] == 0:
                continue
            terrain = grid[y][x]
            if terrain in STATIC_TERRAIN:
                continue

            cls = TERRAIN_TO_CLASS.get(terrain, 0)
            prior = hist_trans["global"][cls]

            # Empirical distribution from observations
            empirical = obs_counts[y, x] / obs_total[y, x]

            # KL-like surprise: sum of |empirical - prior| weighted by prior entropy
            diff = np.abs(empirical - prior)
            surprise[y, x] = diff.sum()

            # Extra weight for settlement/port cells (high-scoring)
            if cls in (1, 2, 3):
                surprise[y, x] *= 3.0
    return surprise


def select_viewports_by_surprise(surprise, height, width, n_viewports=8,
                                  obs_total=None, min_samples_threshold=3):
    """Select viewports that cover the highest-surprise areas.

    Prioritizes areas with: high surprise AND low sample count.
    """
    # Combine surprise with "need more samples" signal
    need = surprise.copy()
    if obs_total is not None:
        # Cells with few samples that are also surprising need more queries
        low_sample_bonus = np.maximum(0, min_samples_threshold - obs_total)
        need += low_sample_bonus * 0.5

    viewports = []
    used = np.zeros((height, width), dtype=bool)
    for _ in range(n_viewports):
        best_score = -1
        best_vp = None
        for vy in range(0, max(1, height - 14), 3):
            for vx in range(0, max(1, width - 14), 3):
                region = need[vy:vy+15, vx:vx+15]
                region_used = used[vy:vy+15, vx:vx+15]
                score = region[~region_used].sum() if (~region_used).any() else 0
                if score > best_score:
                    best_score = score
                    best_vp = (vx, vy, 15, 15)
        if best_vp and best_score > 0:
            viewports.append(best_vp)
            vx, vy, _, _ = best_vp
            used[vy:vy+15, vx:vx+15] = True

    return viewports


def phase_stack(session, round_id, detail, round_num, max_queries=25):
    """Adaptive stacking: observe in batches, run hindsight after each, re-target.

    Instead of blindly repeating the same viewports, this:
    1. Does first pass over initial targets (from phase_analyze heat map)
    2. Computes per-cell surprise (observation vs model prior)
    3. Re-selects viewports for next pass based on surprise
    4. Repeats until budget exhausted
    """
    height, width = detail["map_height"], detail["map_width"]
    grid = detail["initial_states"][0]["grid"]

    # Load stacking targets from phase 2 (initial heat-based targets)
    targets_path = DATA_DIR / f"stack_targets_r{round_num}.json"
    if not targets_path.exists():
        log("Phase 3: No stacking targets. Run phase 'analyze' first.")
        return None, None

    with open(targets_path) as f:
        initial_targets = json.load(f)

    # Load existing observations and historical transitions
    obs_counts, obs_total = load_observations(round_num, "seed0_overview")
    if obs_counts is None:
        obs_counts = np.zeros((height, width, NUM_CLASSES))
        obs_total = np.zeros((height, width))

    # Load historical transitions for surprise calculation
    trans_path = DATA_DIR / f"transition_round_{round_num}_obs.npy"
    if trans_path.exists():
        round_trans = np.load(trans_path)
        hist_trans = {"global": round_trans}
    else:
        hist_trans = {"global": np.full((NUM_CLASSES, NUM_CLASSES), 1/NUM_CLASSES)}

    budget = get_budget(session)
    available = budget["queries_max"] - budget["queries_used"]
    n_queries = min(max_queries, available)

    if n_queries <= 0:
        log("Phase 3: No queries available.")
        return obs_counts, obs_total

    # Adaptive batching: ~8 queries per batch, then hindsight
    batch_size = min(8, len(initial_targets))
    total_done = 0
    batch_num = 0
    current_targets = initial_targets

    log(f"Phase 3: Adaptive stacking — {n_queries} queries, "
        f"batches of {batch_size}, hindsight between batches")

    while total_done < n_queries:
        batch_num += 1
        batch_budget = min(batch_size, n_queries - total_done)

        # Select viewports for this batch
        batch_vps = current_targets[:batch_budget]

        log(f"\n  --- Batch {batch_num} ({batch_budget} queries) ---")

        for i, (vx, vy, vw, vh) in enumerate(batch_vps):
            try:
                obs = query_viewport(session, round_id, 0, vx, vy, vw, vh)
                for dy, row in enumerate(obs["grid"]):
                    for dx, terrain in enumerate(row):
                        ya = obs["viewport"]["y"] + dy
                        xa = obs["viewport"]["x"] + dx
                        cls = TERRAIN_TO_CLASS.get(terrain, 0)
                        obs_counts[ya, xa, cls] += 1
                        obs_total[ya, xa] += 1
                total_done += 1
                log(f"  [{total_done}/{n_queries}] ({vx},{vy}) — "
                    f"budget {obs['queries_used']}/50")
            except requests.HTTPError as e:
                if e.response and e.response.status_code == 429:
                    log(f"  Budget exhausted at query {total_done}")
                    total_done = n_queries  # exit loop
                    break
                log(f"  Failed: {e}")
                continue

        if total_done >= n_queries:
            break

        # HINDSIGHT: compute surprise after this batch
        surprise = compute_surprise(obs_counts, obs_total, grid, hist_trans,
                                     height, width)
        total_surprise = surprise.sum()
        max_surprise = surprise.max()
        high_surprise_cells = int((surprise > 0.5).sum())

        log(f"  Hindsight: total_surprise={total_surprise:.1f}, "
            f"max={max_surprise:.2f}, high_surprise_cells={high_surprise_cells}")

        # Re-select viewports based on surprise for next batch
        current_targets = select_viewports_by_surprise(
            surprise, height, width, n_viewports=batch_size,
            obs_total=obs_total, min_samples_threshold=4
        )

        if current_targets:
            top_heat = surprise[current_targets[0][1]:current_targets[0][1]+15,
                                current_targets[0][0]:current_targets[0][0]+15].sum()
            log(f"  Re-targeted: top viewport ({current_targets[0][0]},{current_targets[0][1]}) "
                f"surprise={top_heat:.1f}")
        else:
            log("  No more high-surprise areas. Stopping early.")
            break

    multi = int((obs_total > 1).sum())
    max_samples = int(obs_total.max())
    log(f"\n  After adaptive stacking: {multi} cells with 2+ samples, "
        f"max {max_samples} samples, {batch_num} batches")

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
    """Build final predictions and submit all 5 seeds.

    Uses learned neighborhood model (48,000+ cell lookup table) instead of
    hand-crafted transition matrices. Falls back to heuristic if learned
    model fails to load.
    """
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
                prev_oc, prev_ot = all_obs[seed_idx]
                mask = ot > prev_ot
                prev_oc[mask] = oc[mask]
                prev_ot[mask] = ot[mask]
            else:
                all_obs[seed_idx] = (oc, ot)

    log(f"Loaded observations for seeds: {list(all_obs.keys())}")

    # Train learned neighborhood model on all completed rounds
    from churn import NeighborhoodModelV2
    learned = NeighborhoodModelV2()
    rounds = session.get(f"{BASE}/astar-island/rounds").json()
    completed = [r for r in rounds if r["status"] == "completed"]
    learned_ok = False

    if completed:
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
        learned_ok = learned.total_cells > 0

    if not learned_ok:
        log("WARNING: Learned model failed, falling back to heuristic transitions")

    # Build and submit predictions
    log(f"\nBuilding predictions for {seeds_count} seeds...")
    for seed_idx in range(seeds_count):
        grid = detail["initial_states"][seed_idx]["grid"]

        if learned_ok:
            # Use learned neighborhood model
            pred = learned.predict_grid_with_obs(
                detail, seed_idx,
                obs_counts=all_obs[seed_idx][0] if seed_idx in all_obs else None,
                obs_total=all_obs[seed_idx][1] if seed_idx in all_obs else None,
                prior_strength=12.0,  # Dirichlet-Categorical: ps=12 optimal (+1.1 avg)
            )
        else:
            # Fallback: heuristic model (old code path)
            pred = np.full((height, width, NUM_CLASSES), PROB_FLOOR)
            for y in range(height):
                for x in range(width):
                    cls = TERRAIN_TO_CLASS.get(grid[y][x], 0)
                    pred[y, x] = hist_trans["global"][cls]
            pred = np.maximum(pred, PROB_FLOOR)
            pred = pred / pred.sum(axis=-1, keepdims=True)

        # Global temperature scaling: T=1.12 optimal across 39 autoiteration variants
        TEMPERATURE = 1.12
        pred = pred ** (1.0 / TEMPERATURE)

        # Collapse thresholding: zero out tiny probabilities, redistribute
        COLLAPSE_THRESH = 0.016
        for y in range(height):
            for x in range(width):
                if grid[y][x] in STATIC_TERRAIN:
                    continue
                probs = pred[y, x]
                mask = probs < COLLAPSE_THRESH
                if mask.any() and not mask.all():
                    probs[mask] = 0.0
                    probs[:] = np.maximum(probs, PROB_FLOOR)
                    pred[y, x] = probs / probs.sum()

        # Spatial smoothing: light Gaussian blur on dynamic cells
        SMOOTH_SIGMA = 0.3
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
    parser.add_argument("--max-stack", type=int, default=41,
                        help="Max queries for stacking phase (default: 41, all remaining after overview)")
    parser.add_argument("--max-secondary", type=int, default=0,
                        help="Max queries for secondary seeds (default: 0, hindsight showed single-obs hurts)")
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
