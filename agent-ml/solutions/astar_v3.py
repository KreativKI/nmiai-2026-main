#!/usr/bin/env python3
"""
Astar Island v3 — Ground-Truth-Learned Transition Model + Neighborhood Awareness

Key improvements over v2:
  - Learns transition distributions from rounds 1-2 ground truth (10 complete tensors)
  - Neighborhood-aware: cells near settlements get different priors than isolated cells
  - Uses remaining query budget for targeted observation on dynamic cells
  - Better probability calibration from empirical data

Usage:
  python astar_v3.py --token YOUR_JWT_TOKEN
  python astar_v3.py --token YOUR_JWT_TOKEN --dry-run
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
STATIC_TERRAIN = {5, 10}  # Mountain, Ocean
NUM_CLASSES = 6
PROB_FLOOR = 0.01
CLASS_NAMES = ["Empty", "Settlement", "Port", "Ruin", "Forest", "Mountain"]


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def get_session(token: str) -> requests.Session:
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {token}"
    s.headers["User-Agent"] = "astar-v3/nmiai-2026"
    return s


def learn_transitions_from_ground_truth(session: requests.Session) -> dict:
    """Fetch ground truth from all completed rounds and build transition models.

    Returns dict with:
      - 'global': 6x6 average transition matrix
      - 'near': 6x6 transitions for cells near settlements
      - 'far': 6x6 transitions for cells far from settlements
    """
    rounds = session.get(f"{BASE}/astar-island/rounds").json()
    completed = [r for r in rounds if r["status"] == "completed"]

    if not completed:
        log("No completed rounds for learning.")
        return None

    global_sums = np.zeros((NUM_CLASSES, NUM_CLASSES))
    global_counts = np.zeros(NUM_CLASSES)
    near_sums = np.zeros((NUM_CLASSES, NUM_CLASSES))
    near_counts = np.zeros(NUM_CLASSES)
    far_sums = np.zeros((NUM_CLASSES, NUM_CLASSES))
    far_counts = np.zeros(NUM_CLASSES)

    for r in completed:
        round_id = r["id"]
        round_num = r["round_number"]
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
                    cls = TERRAIN_TO_CLASS.get(ig[y][x], 0)
                    gt_dist = gt[y][x]

                    global_sums[cls] += gt_dist
                    global_counts[cls] += 1

                    # Check for adjacent settlements/ports
                    has_adj_settlement = False
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            if (dy, dx) == (0, 0):
                                continue
                            ny, nx = y + dy, x + dx
                            if 0 <= ny < h and 0 <= nx < w:
                                ncls = TERRAIN_TO_CLASS.get(ig[ny][nx], 0)
                                if ncls in (1, 2):
                                    has_adj_settlement = True
                                    break
                        if has_adj_settlement:
                            break

                    if has_adj_settlement:
                        near_sums[cls] += gt_dist
                        near_counts[cls] += 1
                    else:
                        far_sums[cls] += gt_dist
                        far_counts[cls] += 1

            log(f"  Learned from round {round_num} seed {seed_idx}")

    # Build normalized transition matrices
    def normalize(sums, counts):
        mat = np.full((NUM_CLASSES, NUM_CLASSES), PROB_FLOOR)
        for i in range(NUM_CLASSES):
            if counts[i] > 0:
                mat[i] = sums[i] / counts[i]
        mat = np.maximum(mat, PROB_FLOOR)
        mat = mat / mat.sum(axis=1, keepdims=True)
        return mat

    result = {
        "global": normalize(global_sums, global_counts),
        "near": normalize(near_sums, near_counts),
        "far": normalize(far_sums, far_counts),
    }

    # Save to disk
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    np.save(DATA_DIR / "v3_transition_global.npy", result["global"])
    np.save(DATA_DIR / "v3_transition_near.npy", result["near"])
    np.save(DATA_DIR / "v3_transition_far.npy", result["far"])

    log("Learned transition matrices:")
    for label in ["global", "near", "far"]:
        log(f"  [{label}]")
        mat = result[label]
        for i, name in enumerate(CLASS_NAMES):
            top = sorted(range(NUM_CLASSES), key=lambda j: mat[i][j], reverse=True)[:3]
            s = ", ".join(f"{CLASS_NAMES[j]}:{mat[i][j]:.3f}" for j in top)
            log(f"    {name} -> {s}")

    return result


def load_cached_transitions() -> dict | None:
    """Load cached transition matrices from disk."""
    paths = {
        "global": DATA_DIR / "v3_transition_global.npy",
        "near": DATA_DIR / "v3_transition_near.npy",
        "far": DATA_DIR / "v3_transition_far.npy",
    }
    if all(p.exists() for p in paths.values()):
        result = {k: np.load(p) for k, p in paths.items()}
        log("Loaded cached transition matrices from disk")
        return result
    return None


def build_prediction_from_learned_model(
    grid: list[list[int]], height: int, width: int,
    transitions: dict
) -> np.ndarray:
    """Build prediction using learned transition model with neighborhood awareness."""
    pred = np.full((height, width, NUM_CLASSES), PROB_FLOOR)
    trans_global = transitions["global"]
    trans_near = transitions["near"]
    trans_far = transitions["far"]

    for y in range(height):
        for x in range(width):
            terrain = grid[y][x]
            cls = TERRAIN_TO_CLASS.get(terrain, 0)

            if terrain in STATIC_TERRAIN:
                # Static: use global (it's ~1.0 for the correct class)
                pred[y, x] = trans_global[cls]
                continue

            # Check for adjacent settlements/ports
            has_adj_settlement = False
            adj_settlement_count = 0
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if (dy, dx) == (0, 0):
                        continue
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < height and 0 <= nx < width:
                        ncls = TERRAIN_TO_CLASS.get(grid[ny][nx], 0)
                        if ncls in (1, 2):
                            has_adj_settlement = True
                            adj_settlement_count += 1

            if has_adj_settlement:
                # Blend near and global based on adjacency count
                weight_near = min(adj_settlement_count / 3.0, 0.8)
                pred[y, x] = weight_near * trans_near[cls] + (1 - weight_near) * trans_global[cls]
            else:
                pred[y, x] = trans_far[cls]

    # Floor and renormalize
    pred = np.maximum(pred, PROB_FLOOR)
    pred = pred / pred.sum(axis=-1, keepdims=True)
    return pred


def find_dynamic_cells(grid: list[list[int]], height: int, width: int) -> list[tuple[int, int]]:
    """Find cells that are dynamic (not mountain/ocean)."""
    dynamic = []
    for y in range(height):
        for x in range(width):
            if grid[y][x] not in STATIC_TERRAIN:
                dynamic.append((y, x))
    return dynamic


def plan_queries(grid: list[list[int]], height: int, width: int,
                 budget: int, seeds_count: int) -> dict[int, list[tuple[int, int, int, int]]]:
    """Plan query allocation across seeds. Returns {seed_idx: [(x,y,w,h), ...]}"""
    if budget <= 0:
        return {}

    # Spread queries evenly across seeds, prioritizing lower indices
    per_seed = max(1, budget // seeds_count)
    remainder = budget - per_seed * seeds_count
    allocation = {}
    remaining = budget
    for seed_idx in range(seeds_count):
        n = min(per_seed + (1 if seed_idx < remainder else 0), remaining)
        if n <= 0:
            break
        remaining -= n

        # Find dynamic region center for this seed's grid
        # Use a single large viewport centered on the densest dynamic area
        dynamic = find_dynamic_cells(grid, height, width)
        if not dynamic:
            continue

        # Find center of mass of dynamic cells
        ys = [c[0] for c in dynamic]
        xs = [c[1] for c in dynamic]
        cy, cx = int(np.mean(ys)), int(np.mean(xs))

        viewports = []
        # Spread viewports around dynamic center
        offsets = [(0, 0), (-12, 0), (12, 0), (0, -12), (0, 12),
                   (-12, -12), (12, -12), (-12, 12), (12, 12)]
        for i, (oy, ox) in enumerate(offsets[:n]):
            vy = max(0, min(cy + oy - 7, height - 15))
            vx = max(0, min(cx + ox - 7, width - 15))
            viewports.append((vx, vy, 15, 15))

        allocation[seed_idx] = viewports

    return allocation


def observe_and_update(
    session: requests.Session, round_id: str,
    predictions: dict[int, np.ndarray],
    grids: list[list[list[int]]],
    query_plan: dict[int, list[tuple[int, int, int, int]]],
    height: int, width: int
) -> dict[int, np.ndarray]:
    """Execute queries and update predictions with observations."""
    for seed_idx, viewports in query_plan.items():
        obs_counts = np.zeros((height, width, NUM_CLASSES))

        for vx, vy, vw, vh in viewports:
            try:
                resp = session.post(f"{BASE}/astar-island/simulate", json={
                    "round_id": round_id,
                    "seed_index": seed_idx,
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

                log(f"  Seed {seed_idx}: queried ({vx},{vy}) 15x15, "
                    f"budget {obs['queries_used']}/{obs.get('queries_max', 50)}")
                time.sleep(0.22)
            except requests.HTTPError as e:
                if e.response and e.response.status_code == 429:
                    log(f"  Query budget exhausted")
                    break
                log(f"  Query failed: {e}")
                break
            except Exception as e:
                log(f"  Query error: {e}")
                break

        # Update predictions for cells where we have observations
        pred = predictions[seed_idx]
        total_obs = obs_counts.sum(axis=-1, keepdims=True)
        has_obs = total_obs > 0

        if has_obs.any():
            empirical = obs_counts / np.maximum(total_obs, 1)
            # Blend: 30% observation, 70% learned model (single observation is noisy)
            obs_weight = np.clip(total_obs / 5.0, 0, 0.5)
            pred = np.where(
                has_obs,
                obs_weight * empirical + (1 - obs_weight) * pred,
                pred
            )
            pred = np.maximum(pred, PROB_FLOOR)
            pred = pred / pred.sum(axis=-1, keepdims=True)
            predictions[seed_idx] = pred
            observed_cells = int(has_obs.squeeze().sum())
            log(f"  Seed {seed_idx}: updated {observed_cells} cells with observations")

    return predictions


def validate_prediction(prediction: np.ndarray, height: int, width: int) -> bool:
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


def submit_prediction(session: requests.Session, round_id: str,
                      seed_index: int, prediction: np.ndarray) -> dict:
    resp = session.post(f"{BASE}/astar-island/submit", json={
        "round_id": round_id,
        "seed_index": seed_index,
        "prediction": prediction.tolist(),
    })
    resp.raise_for_status()
    return resp.json()


def main():
    parser = argparse.ArgumentParser(description="Astar Island v3 — Learned Transitions")
    parser.add_argument("--token", required=True, help="JWT token")
    parser.add_argument("--dry-run", action="store_true", help="Don't submit")
    parser.add_argument("--skip-learn", action="store_true",
                        help="Use cached transitions instead of re-fetching")
    parser.add_argument("--skip-queries", action="store_true",
                        help="Don't use observation queries, just submit learned model")
    args = parser.parse_args()

    session = get_session(args.token)

    # Step 1: Learn from completed rounds
    transitions = None
    if args.skip_learn:
        transitions = load_cached_transitions()
    if transitions is None:
        log("Learning from completed rounds' ground truth...")
        transitions = learn_transitions_from_ground_truth(session)
    if transitions is None:
        log("FATAL: No transition data available")
        return

    # Step 2: Find active round
    rounds = session.get(f"{BASE}/astar-island/rounds").json()
    active = None
    for r in rounds:
        if r["status"] == "active":
            active = r
            break
    if not active:
        log("No active round found.")
        for r in rounds:
            log(f"  Round {r['round_number']}: {r['status']}")
        return

    round_id = active["id"]
    round_num = active["round_number"]
    log(f"Active round: #{round_num} (weight: {active['round_weight']:.4f})")
    log(f"Closes at: {active['closes_at']}")

    # Step 3: Get round details
    detail = session.get(f"{BASE}/astar-island/rounds/{round_id}").json()
    width = detail["map_width"]
    height = detail["map_height"]
    seeds_count = detail["seeds_count"]
    log(f"Map: {width}x{height}, {seeds_count} seeds")

    budget = session.get(f"{BASE}/astar-island/budget").json()
    queries_remaining = budget["queries_max"] - budget["queries_used"]
    log(f"Queries: {budget['queries_used']}/{budget['queries_max']} used, {queries_remaining} remaining")

    # Step 4: Build predictions for all seeds using learned model
    predictions = {}
    grids = []
    for seed_idx in range(seeds_count):
        state = detail["initial_states"][seed_idx]
        grid = state["grid"]
        grids.append(grid)

        pred = build_prediction_from_learned_model(grid, height, width, transitions)
        predictions[seed_idx] = pred

        # Log prediction stats
        argmax = pred.argmax(axis=-1)
        avg_conf = pred.max(axis=-1).mean()
        log(f"Seed {seed_idx}: avg confidence {avg_conf:.3f}, "
            f"Empty={int((argmax==0).sum())} Settl={int((argmax==1).sum())} "
            f"Port={int((argmax==2).sum())} Ruin={int((argmax==3).sum())} "
            f"Forest={int((argmax==4).sum())} Mount={int((argmax==5).sum())}")

    # Step 5: Use remaining queries to observe and refine
    if not args.skip_queries and queries_remaining > 0:
        log(f"\nUsing {queries_remaining} remaining queries for observation...")
        query_plan = plan_queries(grids[0], height, width, queries_remaining, seeds_count)
        predictions = observe_and_update(
            session, round_id, predictions, grids, query_plan, height, width
        )
    elif queries_remaining == 0:
        log("No remaining queries. Submitting learned model predictions only.")

    # Step 6: Validate and submit
    log("\nSubmitting predictions...")
    for seed_idx in range(seeds_count):
        pred = predictions[seed_idx]
        if not validate_prediction(pred, height, width):
            log(f"Seed {seed_idx}: VALIDATION FAILED")
            continue

        if args.dry_run:
            log(f"Seed {seed_idx}: [DRY RUN] Would submit {height}x{width}x{NUM_CLASSES}")
        else:
            try:
                result = submit_prediction(session, round_id, seed_idx, pred)
                log(f"Seed {seed_idx}: submitted OK")
            except Exception as e:
                log(f"Seed {seed_idx}: submission failed: {e}")

    log("\nDone!")


if __name__ == "__main__":
    main()
