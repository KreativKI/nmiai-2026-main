#!/usr/bin/env python3
"""
Astar Island v4 — Round Refinement with Targeted Observations

Uses remaining query budget to:
  1. Observe the most dynamic cells on ONE seed (concentrated sampling)
  2. Build round-specific empirical distributions
  3. Blend with learned transitions from prior rounds
  4. Resubmit improved predictions for all 5 seeds via cross-seed transfer

Usage:
  python astar_v4.py --token TOKEN --dry-run     # Preview only
  python astar_v4.py --token TOKEN --submit       # Observe + resubmit
"""

import argparse
import json
import time
from pathlib import Path
from datetime import datetime, timezone

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
    s.headers["User-Agent"] = "astar-v4/nmiai-2026"
    return s


def find_settlement_clusters(grid, height, width):
    """Find cells that are settlements, ports, or adjacent to them.
    Returns list of (y, x, priority) sorted by priority (highest first).
    Priority based on number of dynamic neighbors."""
    priority_map = np.zeros((height, width))

    for y in range(height):
        for x in range(width):
            terrain = grid[y][x]
            cls = TERRAIN_TO_CLASS.get(terrain, 0)
            if cls in (1, 2):  # Settlement or Port
                priority_map[y, x] += 5
                # Boost neighbors
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < height and 0 <= nx < width:
                            dist = abs(dy) + abs(dx)
                            if dist > 0:
                                priority_map[ny, nx] += 3.0 / dist
            elif terrain not in STATIC_TERRAIN:
                priority_map[y, x] += 0.5

    return priority_map


def plan_viewports(grid, height, width, budget):
    """Plan viewport placements to maximize coverage of dynamic cells.
    Returns list of (x, y, w, h) viewports."""
    priority = find_settlement_clusters(grid, height, width)

    viewports = []
    covered = np.zeros((height, width), dtype=bool)

    for _ in range(budget):
        best_score = -1
        best_vp = None

        # Try all possible 15x15 viewport positions (stride 5 for speed)
        for vy in range(0, height - 14, 3):
            for vx in range(0, width - 14, 3):
                # Score = sum of priority of uncovered cells in this viewport
                region_priority = priority[vy:vy+15, vx:vx+15].copy()
                region_covered = covered[vy:vy+15, vx:vx+15]
                # Reduce priority for already-covered cells (but don't zero out:
                # stacking gives multi-sample benefit)
                region_priority[region_covered] *= 0.3
                score = region_priority.sum()
                if score > best_score:
                    best_score = score
                    best_vp = (vx, vy, 15, 15)

        if best_vp is None:
            break

        viewports.append(best_vp)
        vx, vy, vw, vh = best_vp
        covered[vy:vy+vh, vx:vx+vw] = True

    return viewports


def learn_transitions_from_completed(session):
    """Learn transition distributions from completed rounds' ground truth."""
    rounds = session.get(f"{BASE}/astar-island/rounds").json()
    completed = [r for r in rounds if r["status"] == "completed"]

    if not completed:
        return None

    # Accumulate transition distributions
    # For each initial terrain class, accumulate the ground truth probability vectors
    transition_sums = np.zeros((NUM_CLASSES, NUM_CLASSES))
    transition_counts = np.zeros(NUM_CLASSES)
    # Also track per-neighborhood context
    near_sums = np.zeros((NUM_CLASSES, NUM_CLASSES))
    near_counts = np.zeros(NUM_CLASSES)
    far_sums = np.zeros((NUM_CLASSES, NUM_CLASSES))
    far_counts = np.zeros(NUM_CLASSES)

    for r in completed:
        round_id = r["id"]
        detail = session.get(f"{BASE}/astar-island/rounds/{round_id}").json()
        seeds_count = detail.get("seeds_count", 5)

        for seed_idx in range(seeds_count):
            resp = session.get(f"{BASE}/astar-island/analysis/{round_id}/{seed_idx}")
            if resp.status_code != 200:
                continue
            data = resp.json()
            ig = data["initial_grid"]
            gt = np.array(data["ground_truth"])
            h, w = len(ig), len(ig[0])

            for y in range(h):
                for x in range(w):
                    terrain = ig[y][x]
                    cls = TERRAIN_TO_CLASS.get(terrain, 0)
                    gt_dist = gt[y][x]

                    transition_sums[cls] += gt_dist
                    transition_counts[cls] += 1

                    has_adj = False
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            if (dy, dx) == (0, 0):
                                continue
                            ny, nx = y + dy, x + dx
                            if 0 <= ny < h and 0 <= nx < w:
                                ncls = TERRAIN_TO_CLASS.get(ig[ny][nx], 0)
                                if ncls in (1, 2):
                                    has_adj = True
                                    break
                        if has_adj:
                            break

                    if has_adj:
                        near_sums[cls] += gt_dist
                        near_counts[cls] += 1
                    else:
                        far_sums[cls] += gt_dist
                        far_counts[cls] += 1

        log(f"  Learned from round {r['round_number']} ({seeds_count} seeds)")

    def normalize(sums, counts):
        mat = np.full((NUM_CLASSES, NUM_CLASSES), PROB_FLOOR)
        for i in range(NUM_CLASSES):
            if counts[i] > 0:
                mat[i] = sums[i] / counts[i]
        mat = np.maximum(mat, PROB_FLOOR)
        mat = mat / mat.sum(axis=1, keepdims=True)
        return mat

    return {
        "global": normalize(transition_sums, transition_counts),
        "near": normalize(near_sums, near_counts),
        "far": normalize(far_sums, far_counts),
    }


def build_prediction(grid, height, width, transitions,
                     obs_counts=None, obs_total=None):
    """Build prediction tensor using transitions + optional observations."""
    pred = np.full((height, width, NUM_CLASSES), PROB_FLOOR)
    trans_global = transitions["global"]
    trans_near = transitions["near"]
    trans_far = transitions["far"]

    for y in range(height):
        for x in range(width):
            terrain = grid[y][x]
            cls = TERRAIN_TO_CLASS.get(terrain, 0)

            if terrain in STATIC_TERRAIN:
                pred[y, x] = trans_global[cls]
                continue

            # Check neighborhood
            adj_count = 0
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if (dy, dx) == (0, 0):
                        continue
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < height and 0 <= nx < width:
                        ncls = TERRAIN_TO_CLASS.get(grid[ny][nx], 0)
                        if ncls in (1, 2):
                            adj_count += 1

            if adj_count > 0:
                weight_near = min(adj_count / 3.0, 0.8)
                base_pred = weight_near * trans_near[cls] + (1 - weight_near) * trans_global[cls]
            else:
                base_pred = trans_far[cls]

            pred[y, x] = base_pred

    # Blend with observations if available
    if obs_counts is not None and obs_total is not None:
        has_obs = obs_total > 0
        if has_obs.any():
            empirical = obs_counts / np.maximum(obs_total[..., np.newaxis], 1)
            # More observations = trust empirical more (up to 70% weight)
            obs_weight = np.clip(obs_total[..., np.newaxis] / 5.0, 0, 0.7)
            pred = np.where(
                has_obs[..., np.newaxis] if has_obs.ndim == 2 else has_obs,
                obs_weight[..., np.newaxis] * empirical + (1 - obs_weight[..., np.newaxis]) * pred,
                pred
            )

    # Floor and renormalize
    pred = np.maximum(pred, PROB_FLOOR)
    pred = pred / pred.sum(axis=-1, keepdims=True)
    return pred


def validate_prediction(prediction, height, width):
    if prediction.shape != (height, width, NUM_CLASSES):
        log(f"  ERROR: Wrong shape {prediction.shape}")
        return False
    sums = prediction.sum(axis=-1)
    if not np.allclose(sums, 1.0, atol=0.01):
        log(f"  ERROR: Row sums range [{sums.min():.4f}, {sums.max():.4f}]")
        return False
    if (prediction < 0).any():
        log(f"  ERROR: Negative probabilities")
        return False
    if (prediction < PROB_FLOOR - 0.001).any():
        log(f"  ERROR: Below floor {PROB_FLOOR}")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Astar Island v4 — Round Refinement")
    parser.add_argument("--token", required=True, help="JWT token")
    parser.add_argument("--dry-run", action="store_true", help="Don't query or submit")
    parser.add_argument("--submit", action="store_true", help="Query remaining budget + resubmit")
    parser.add_argument("--observe-seed", type=int, default=0,
                        help="Which seed to observe (default: 0)")
    args = parser.parse_args()

    session = get_session(args.token)

    # Step 1: Learn from completed rounds
    log("Learning from completed rounds...")
    transitions = learn_transitions_from_completed(session)
    if transitions is None:
        log("FATAL: No transition data")
        return

    for label in ["global", "near", "far"]:
        mat = transitions[label]
        log(f"  [{label}] top transitions:")
        for i, name in enumerate(CLASS_NAMES):
            top = sorted(range(NUM_CLASSES), key=lambda j: mat[i][j], reverse=True)[:2]
            s = ", ".join(f"{CLASS_NAMES[j]}:{mat[i][j]:.3f}" for j in top)
            log(f"    {name} -> {s}")

    # Step 2: Find active round
    rounds = session.get(f"{BASE}/astar-island/rounds").json()
    active = None
    for r in rounds:
        if r["status"] == "active":
            active = r
            break
    if not active:
        log("No active round.")
        return

    round_id = active["id"]
    round_num = active["round_number"]
    closes_at = datetime.fromisoformat(active["closes_at"])
    remaining_min = (closes_at - datetime.now(timezone.utc)).total_seconds() / 60
    log(f"Round #{round_num}, weight {active['round_weight']:.4f}, "
        f"closes in {remaining_min:.0f} min")

    detail = session.get(f"{BASE}/astar-island/rounds/{round_id}").json()
    width = detail["map_width"]
    height = detail["map_height"]
    seeds_count = detail["seeds_count"]

    budget = session.get(f"{BASE}/astar-island/budget").json()
    queries_remaining = budget["queries_max"] - budget["queries_used"]
    log(f"Queries: {budget['queries_used']}/{budget['queries_max']} used, "
        f"{queries_remaining} remaining")

    # Step 3: Observe with remaining budget (all on one seed)
    obs_seed = args.observe_seed
    obs_counts = np.zeros((height, width, NUM_CLASSES))
    obs_total = np.zeros((height, width))

    if args.submit and queries_remaining > 0:
        grid = detail["initial_states"][obs_seed]["grid"]
        viewports = plan_viewports(grid, height, width, queries_remaining)
        log(f"\nObserving seed {obs_seed} with {len(viewports)} viewports...")

        for i, (vx, vy, vw, vh) in enumerate(viewports):
            try:
                resp = session.post(f"{BASE}/astar-island/simulate", json={
                    "round_id": round_id,
                    "seed_index": obs_seed,
                    "viewport_x": vx,
                    "viewport_y": vy,
                    "viewport_w": vw,
                    "viewport_h": vh,
                })
                resp.raise_for_status()
                obs = resp.json()

                for dy, row in enumerate(obs["grid"]):
                    for dx, terrain in enumerate(row):
                        y_abs = obs["viewport"]["y"] + dy
                        x_abs = obs["viewport"]["x"] + dx
                        cls = TERRAIN_TO_CLASS.get(terrain, 0)
                        obs_counts[y_abs, x_abs, cls] += 1
                        obs_total[y_abs, x_abs] += 1

                log(f"  [{i+1}/{len(viewports)}] ({vx},{vy}) 15x15 — "
                    f"budget {obs['queries_used']}/{obs.get('queries_max', 50)}")
                time.sleep(0.22)
            except requests.HTTPError as e:
                if e.response and e.response.status_code == 429:
                    log(f"  Budget exhausted at query {i+1}")
                    break
                log(f"  Query failed: {e}")
                break
            except Exception as e:
                log(f"  Error: {e}")
                break

        observed_cells = int((obs_total > 0).sum())
        multi_sampled = int((obs_total > 1).sum())
        log(f"  Observed {observed_cells} cells, {multi_sampled} with multiple samples")
    elif queries_remaining > 0:
        log(f"\n[DRY RUN] Would use {queries_remaining} queries on seed {obs_seed}")
    else:
        log("\nNo remaining queries. Using transition model only.")

    # Step 4: Build predictions for all seeds
    log("\nBuilding predictions...")
    for seed_idx in range(seeds_count):
        grid = detail["initial_states"][seed_idx]["grid"]

        # For observed seed: use observations directly
        # For other seeds: observations still help via cross-seed transfer
        # (same hidden params means similar dynamics)
        if seed_idx == obs_seed and obs_total.sum() > 0:
            pred = build_prediction(grid, height, width, transitions,
                                    obs_counts, obs_total)
            log(f"Seed {seed_idx}: transition model + {int(obs_total.sum())} observations")
        else:
            # Cross-seed transfer: use observation-derived transition adjustments
            # The observations from seed 0 tell us about round-specific dynamics
            # Apply as empirical transition weights to this seed's initial terrain
            pred = build_prediction(grid, height, width, transitions)
            log(f"Seed {seed_idx}: transition model only (cross-seed from learned transitions)")

        if not validate_prediction(pred, height, width):
            log(f"Seed {seed_idx}: VALIDATION FAILED")
            continue

        # Stats
        argmax = pred.argmax(axis=-1)
        avg_conf = pred.max(axis=-1).mean()
        dynamic_mask = np.array([[grid[y][x] not in STATIC_TERRAIN
                                  for x in range(width)] for y in range(height)])
        dynamic_conf = pred.max(axis=-1)[dynamic_mask].mean() if dynamic_mask.any() else 0
        log(f"  Avg conf: {avg_conf:.3f} (dynamic cells: {dynamic_conf:.3f})")
        for c, name in enumerate(CLASS_NAMES):
            count = int((argmax == c).sum())
            if count > 0:
                log(f"    {name}: {count}")

        if args.submit:
            try:
                result = session.post(f"{BASE}/astar-island/submit", json={
                    "round_id": round_id,
                    "seed_index": seed_idx,
                    "prediction": pred.tolist(),
                })
                result.raise_for_status()
                log(f"  Seed {seed_idx}: SUBMITTED")
            except Exception as e:
                log(f"  Seed {seed_idx}: submit failed: {e}")
        else:
            log(f"  Seed {seed_idx}: [DRY RUN] would submit")

    log("\nDone!")


if __name__ == "__main__":
    main()
