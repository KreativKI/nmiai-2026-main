#!/usr/bin/env python3
"""
Astar Island v5 — Full-Pipeline with Cross-Seed Transfer

Key improvements over v4:
  - Fixed broadcasting bug
  - True cross-seed transfer: observations from observed seeds build
    a ROUND-SPECIFIC transition model that applies to all seeds
  - Stacked observations: multiple queries on same area give multi-sample
    probability estimates (much more informative than single samples)
  - Better blending: round-specific transitions weighted higher than
    historical transitions when we have enough observations
  - Post-round analysis: fetches ground truth from completed rounds
    and computes error metrics for next round improvement

Usage:
  python astar_v5.py --token TOKEN --dry-run          # Preview predictions
  python astar_v5.py --token TOKEN --submit            # Observe + submit
  python astar_v5.py --token TOKEN --analyze           # Post-round analysis
  python astar_v5.py --token TOKEN --submit --skip-obs # Submit without queries
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
    s.headers["User-Agent"] = "astar-v5/nmiai-2026"
    return s


def learn_historical_transitions(session):
    """Learn transition distributions from ALL completed rounds' ground truth.
    Returns dict with global/near/far 6x6 matrices."""
    rounds = session.get(f"{BASE}/astar-island/rounds").json()
    completed = [r for r in rounds if r["status"] == "completed"]

    if not completed:
        log("No completed rounds for learning.")
        return None

    sums = {k: np.zeros((NUM_CLASSES, NUM_CLASSES)) for k in ["global", "near", "far"]}
    counts = {k: np.zeros(NUM_CLASSES) for k in ["global", "near", "far"]}

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

                    sums["global"][cls] += gt_dist
                    counts["global"][cls] += 1

                    has_adj = any(
                        0 <= y+dy < h and 0 <= x+dx < w
                        and TERRAIN_TO_CLASS.get(ig[y+dy][x+dx], 0) in (1, 2)
                        for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                        if (dy, dx) != (0, 0)
                    )
                    key = "near" if has_adj else "far"
                    sums[key][cls] += gt_dist
                    counts[key][cls] += 1

        log(f"  Learned from round {r['round_number']} ({seeds_count} seeds)")

    def normalize(s, c):
        mat = np.full((NUM_CLASSES, NUM_CLASSES), PROB_FLOOR)
        for i in range(NUM_CLASSES):
            if c[i] > 0:
                mat[i] = s[i] / c[i]
        mat = np.maximum(mat, PROB_FLOOR)
        mat = mat / mat.sum(axis=1, keepdims=True)
        return mat

    result = {k: normalize(sums[k], counts[k]) for k in ["global", "near", "far"]}

    # Save to disk
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for k in result:
        np.save(DATA_DIR / f"v5_hist_{k}.npy", result[k])

    return result


def plan_observation_strategy(grids, height, width, budget, seeds_count):
    """Plan which seeds to observe and where.
    Strategy: concentrate on seeds 0-1 for deep coverage, light coverage on 2.
    Returns {seed_idx: [(x, y, w, h), ...]}"""
    if budget <= 0:
        return {}

    # Allocate budget across seeds
    if budget >= 30:
        alloc = {0: 15, 1: 10, 2: 5}
        remaining = budget - 30
        # Distribute remainder to seed 0
        alloc[0] += remaining
    elif budget >= 15:
        alloc = {0: min(15, budget), 1: budget - min(15, budget)}
    else:
        alloc = {0: budget}

    plan = {}
    for seed_idx, n_queries in alloc.items():
        if n_queries <= 0 or seed_idx >= seeds_count:
            continue
        grid = grids[seed_idx]
        viewports = _select_viewports(grid, height, width, n_queries)
        plan[seed_idx] = viewports

    return plan


def _select_viewports(grid, height, width, n_queries):
    """Select viewport positions maximizing dynamic cell coverage.
    Uses greedy: pick viewport with most uncovered dynamic cells."""
    # Build priority map
    priority = np.zeros((height, width))
    for y in range(height):
        for x in range(width):
            terrain = grid[y][x]
            cls = TERRAIN_TO_CLASS.get(terrain, 0)
            if terrain in STATIC_TERRAIN:
                priority[y, x] = 0
            elif cls in (1, 2):  # Settlement/Port: highest priority
                priority[y, x] = 10
            elif cls == 3:  # Ruin
                priority[y, x] = 5
            elif cls == 4:  # Forest
                priority[y, x] = 1
            else:  # Empty
                # Check if near settlement
                has_adj = any(
                    0 <= y+dy < height and 0 <= x+dx < width
                    and TERRAIN_TO_CLASS.get(grid[y+dy][x+dx], 0) in (1, 2)
                    for dy in range(-2, 3) for dx in range(-2, 3)
                    if abs(dy) + abs(dx) <= 2 and (dy, dx) != (0, 0)
                )
                priority[y, x] = 4 if has_adj else 2

    viewports = []
    coverage_count = np.zeros((height, width))

    for _ in range(n_queries):
        best_score = -1
        best_vp = None

        for vy in range(0, max(1, height - 14), 4):
            for vx in range(0, max(1, width - 14), 4):
                vh = min(15, height - vy)
                vw = min(15, width - vx)
                region_p = priority[vy:vy+vh, vx:vx+vw].copy()
                region_c = coverage_count[vy:vy+vh, vx:vx+vw]
                # Diminishing returns for re-covering cells (but still some value
                # for multi-sample estimates)
                region_p = region_p / (1 + region_c * 0.5)
                score = region_p.sum()
                if score > best_score:
                    best_score = score
                    best_vp = (vx, vy, vw, vh)

        if best_vp is None:
            break
        viewports.append(best_vp)
        vx, vy, vw, vh = best_vp
        coverage_count[vy:vy+vh, vx:vx+vw] += 1

    return viewports


def execute_observations(session, round_id, obs_plan, grids, height, width):
    """Execute observation queries and collect results.
    Returns {seed_idx: (obs_counts[H,W,6], obs_total[H,W])}"""
    results = {}

    for seed_idx, viewports in obs_plan.items():
        obs_counts = np.zeros((height, width, NUM_CLASSES))
        obs_total = np.zeros((height, width))

        for i, (vx, vy, vw, vh) in enumerate(viewports):
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
                        obs_total[y_abs, x_abs] += 1

                budget_used = obs["queries_used"]
                budget_max = obs.get("queries_max", 50)
                log(f"  Seed {seed_idx} [{i+1}/{len(viewports)}]: "
                    f"({vx},{vy}) {vw}x{vh} — {budget_used}/{budget_max}")
                time.sleep(0.22)
            except requests.HTTPError as e:
                if e.response and e.response.status_code == 429:
                    log(f"  Budget exhausted at query {i+1}")
                    break
                log(f"  Query failed: {e}")
                continue
            except Exception as e:
                log(f"  Error: {e}")
                continue

        observed = int((obs_total > 0).sum())
        multi = int((obs_total > 1).sum())
        log(f"  Seed {seed_idx}: {observed} cells observed, {multi} multi-sampled")
        results[seed_idx] = (obs_counts, obs_total)

    return results


def build_round_transitions(grids, observations, height, width):
    """Build round-specific transition model from this round's observations.
    This captures the current round's hidden parameters."""
    sums = {k: np.zeros((NUM_CLASSES, NUM_CLASSES)) for k in ["global", "near", "far"]}
    counts = {k: np.zeros(NUM_CLASSES) for k in ["global", "near", "far"]}

    for seed_idx, (obs_counts, obs_total) in observations.items():
        grid = grids[seed_idx]
        for y in range(height):
            for x in range(width):
                if obs_total[y, x] == 0:
                    continue
                terrain = grid[y][x]
                cls = TERRAIN_TO_CLASS.get(terrain, 0)
                # Empirical distribution from observations
                empirical = obs_counts[y, x] / obs_total[y, x]

                sums["global"][cls] += empirical
                counts["global"][cls] += 1

                has_adj = any(
                    0 <= y+dy < height and 0 <= x+dx < width
                    and TERRAIN_TO_CLASS.get(grid[y+dy][x+dx], 0) in (1, 2)
                    for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                    if (dy, dx) != (0, 0)
                )
                key = "near" if has_adj else "far"
                sums[key][cls] += empirical
                counts[key][cls] += 1

    def normalize(s, c):
        mat = np.full((NUM_CLASSES, NUM_CLASSES), PROB_FLOOR)
        for i in range(NUM_CLASSES):
            if c[i] > 0:
                mat[i] = s[i] / c[i]
        mat = np.maximum(mat, PROB_FLOOR)
        mat = mat / mat.sum(axis=1, keepdims=True)
        return mat

    result = {k: normalize(sums[k], counts[k]) for k in ["global", "near", "far"]}

    # Log useful transition info
    for label in ["global"]:
        mat = result[label]
        log(f"  Round-specific [{label}] transitions:")
        for i, name in enumerate(CLASS_NAMES):
            if counts[label][i] > 5:
                top = sorted(range(NUM_CLASSES), key=lambda j: mat[i][j], reverse=True)[:2]
                s = ", ".join(f"{CLASS_NAMES[j]}:{mat[i][j]:.3f}" for j in top)
                log(f"    {name} ({int(counts[label][i])} samples) -> {s}")

    return result


def blend_transition_models(historical, round_specific, obs_weight=0.6):
    """Blend historical and round-specific transition models.
    Round-specific gets higher weight when available."""
    blended = {}
    for key in ["global", "near", "far"]:
        h = historical[key]
        r = round_specific[key]
        blended[key] = obs_weight * r + (1 - obs_weight) * h
        blended[key] = np.maximum(blended[key], PROB_FLOOR)
        blended[key] = blended[key] / blended[key].sum(axis=1, keepdims=True)
    return blended


def build_prediction(grid, height, width, transitions,
                     obs_counts=None, obs_total=None):
    """Build prediction tensor."""
    pred = np.full((height, width, NUM_CLASSES), PROB_FLOOR)
    trans_g = transitions["global"]
    trans_n = transitions["near"]
    trans_f = transitions["far"]

    for y in range(height):
        for x in range(width):
            terrain = grid[y][x]
            cls = TERRAIN_TO_CLASS.get(terrain, 0)

            if terrain in STATIC_TERRAIN:
                pred[y, x] = trans_g[cls]
                continue

            adj = sum(
                1 for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                if (dy, dx) != (0, 0)
                and 0 <= y+dy < height and 0 <= x+dx < width
                and TERRAIN_TO_CLASS.get(grid[y+dy][x+dx], 0) in (1, 2)
            )

            if adj > 0:
                w_near = min(adj / 3.0, 0.8)
                pred[y, x] = w_near * trans_n[cls] + (1 - w_near) * trans_g[cls]
            else:
                pred[y, x] = trans_f[cls]

    # Blend with direct observations (highest trust)
    if obs_counts is not None and obs_total is not None:
        has_obs = obs_total > 0
        if has_obs.any():
            # Expand obs_total for broadcasting: (H,W) -> (H,W,1)
            obs_total_3d = obs_total[..., np.newaxis]
            empirical = obs_counts / np.maximum(obs_total_3d, 1)
            # Weight based on sample count: 1 sample -> 30%, 3+ -> 70%
            w = np.clip(obs_total_3d / 5.0, 0.3, 0.7)
            has_obs_3d = has_obs[..., np.newaxis]
            pred = np.where(
                has_obs_3d,
                w * empirical + (1 - w) * pred,
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
        log(f"  ERROR: Row sums [{sums.min():.4f}, {sums.max():.4f}]")
        return False
    if (prediction < PROB_FLOOR - 0.001).any():
        log(f"  ERROR: Below floor")
        return False
    return True


def submit_seed(session, round_id, seed_idx, prediction):
    """Submit prediction for one seed with retry on rate limit."""
    for attempt in range(3):
        try:
            resp = session.post(f"{BASE}/astar-island/submit", json={
                "round_id": round_id,
                "seed_index": seed_idx,
                "prediction": prediction.tolist(),
            })
            resp.raise_for_status()
            log(f"  Seed {seed_idx}: SUBMITTED")
            return True
        except requests.HTTPError as e:
            if e.response and e.response.status_code == 429:
                log(f"  Seed {seed_idx}: rate limited, retrying in 2s...")
                time.sleep(2)
                continue
            log(f"  Seed {seed_idx}: failed: {e}")
            return False
    log(f"  Seed {seed_idx}: failed after 3 attempts")
    return False


def analyze_round(session, round_id, seeds_count):
    """Post-round analysis: fetch ground truth, compute error metrics."""
    log(f"\nAnalyzing round {round_id}...")

    for seed_idx in range(seeds_count):
        resp = session.get(f"{BASE}/astar-island/analysis/{round_id}/{seed_idx}")
        if resp.status_code != 200:
            log(f"  Seed {seed_idx}: analysis not available")
            continue

        data = resp.json()
        score = data.get("score")
        gt = np.array(data["ground_truth"])
        ig = data["initial_grid"]
        pred = data.get("prediction")

        log(f"  Seed {seed_idx}: score = {score}")

        if pred is not None:
            pred = np.array(pred)
            # Per-class error analysis
            for cls, name in enumerate(CLASS_NAMES):
                # Cells where ground truth has significant probability for this class
                gt_prob = gt[:, :, cls]
                pred_prob = pred[:, :, cls]
                mask = gt_prob > 0.1
                if mask.sum() > 0:
                    mae = np.abs(gt_prob[mask] - pred_prob[mask]).mean()
                    log(f"    {name}: MAE={mae:.3f} ({int(mask.sum())} cells with gt>0.1)")

        # Count terrain transitions
        h, w = len(ig), len(ig[0])
        changes = 0
        for y in range(h):
            for x in range(w):
                initial = TERRAIN_TO_CLASS.get(ig[y][x], 0)
                dominant = gt[y, x].argmax()
                if initial != dominant:
                    changes += 1
        log(f"    Terrain changes: {changes}/{h*w}")


def main():
    parser = argparse.ArgumentParser(description="Astar Island v5")
    parser.add_argument("--token", required=True)
    parser.add_argument("--dry-run", action="store_true",
                        help="Don't query or submit")
    parser.add_argument("--submit", action="store_true",
                        help="Observe + submit")
    parser.add_argument("--analyze", action="store_true",
                        help="Post-round analysis of completed rounds")
    parser.add_argument("--skip-obs", action="store_true",
                        help="Skip observations, submit from model only")
    parser.add_argument("--round-id", type=str, default=None,
                        help="Specific round to analyze")
    args = parser.parse_args()

    session = get_session(args.token)

    # Step 1: Learn from historical rounds
    log("Learning from completed rounds...")
    hist_trans = learn_historical_transitions(session)
    if hist_trans is None:
        log("No historical data. Using uniform priors.")
        hist_trans = {k: np.full((NUM_CLASSES, NUM_CLASSES), 1/NUM_CLASSES)
                      for k in ["global", "near", "far"]}

    # Step 2: Post-round analysis if requested
    if args.analyze:
        rounds = session.get(f"{BASE}/astar-island/rounds").json()
        completed = [r for r in rounds if r["status"] == "completed"]
        for r in completed:
            detail = session.get(f"{BASE}/astar-island/rounds/{r['id']}").json()
            log(f"\n=== Round {r['round_number']} (weight {r['round_weight']:.4f}) ===")
            analyze_round(session, r["id"], detail.get("seeds_count", 5))
        return

    # Step 3: Find active round
    rounds = session.get(f"{BASE}/astar-island/rounds").json()
    active = None
    for r in rounds:
        if r["status"] == "active":
            active = r
            break
    if not active:
        log("No active round.")
        for r in rounds:
            log(f"  Round {r['round_number']}: {r['status']}")
        return

    round_id = active["id"]
    round_num = active["round_number"]
    closes_at = datetime.fromisoformat(active["closes_at"])
    remaining_min = (closes_at - datetime.now(timezone.utc)).total_seconds() / 60
    log(f"\nRound #{round_num}, weight {active['round_weight']:.4f}, "
        f"closes in {remaining_min:.0f} min")

    detail = session.get(f"{BASE}/astar-island/rounds/{round_id}").json()
    width = detail["map_width"]
    height = detail["map_height"]
    seeds_count = detail["seeds_count"]

    budget = session.get(f"{BASE}/astar-island/budget").json()
    queries_remaining = budget["queries_max"] - budget["queries_used"]
    log(f"Queries: {budget['queries_used']}/{budget['queries_max']} used, "
        f"{queries_remaining} remaining")

    # Get initial grids
    grids = [detail["initial_states"][i]["grid"] for i in range(seeds_count)]

    # Step 4: Observe
    observations = {}
    round_trans = None

    if args.submit and not args.skip_obs and queries_remaining > 0:
        obs_plan = plan_observation_strategy(grids, height, width,
                                              queries_remaining, seeds_count)
        total_planned = sum(len(v) for v in obs_plan.values())
        log(f"\nObservation plan: {total_planned} queries across "
            f"{len(obs_plan)} seeds")
        for s, vps in obs_plan.items():
            log(f"  Seed {s}: {len(vps)} viewports")

        observations = execute_observations(session, round_id, obs_plan,
                                             grids, height, width)

        # Build round-specific transitions from observations
        if observations:
            log("\nBuilding round-specific transition model...")
            round_trans = build_round_transitions(grids, observations,
                                                   height, width)
    elif queries_remaining == 0:
        log("\nNo queries remaining.")
    else:
        log(f"\n[{'DRY RUN' if args.dry_run else 'SKIP-OBS'}] "
            f"Not using queries.")

    # Step 5: Determine transition model to use
    if round_trans is not None:
        log("\nBlending round-specific + historical transitions (60/40)...")
        final_trans = blend_transition_models(hist_trans, round_trans, obs_weight=0.6)
    else:
        log("\nUsing historical transitions only.")
        final_trans = hist_trans

    # Step 6: Build and submit predictions
    log(f"\nBuilding predictions for {seeds_count} seeds...")
    for seed_idx in range(seeds_count):
        grid = grids[seed_idx]

        # Use direct observations for this seed if available
        obs_c, obs_t = None, None
        if seed_idx in observations:
            obs_c, obs_t = observations[seed_idx]

        pred = build_prediction(grid, height, width, final_trans, obs_c, obs_t)

        if not validate_prediction(pred, height, width):
            log(f"Seed {seed_idx}: VALIDATION FAILED")
            continue

        # Stats
        argmax = pred.argmax(axis=-1)
        avg_conf = pred.max(axis=-1).mean()
        dynamic_mask = np.array([[grid[y][x] not in STATIC_TERRAIN
                                  for x in range(width)] for y in range(height)])
        dyn_conf = pred.max(axis=-1)[dynamic_mask].mean() if dynamic_mask.any() else 0
        obs_str = ""
        if obs_c is not None:
            obs_str = f", {int(obs_t.sum())} obs"
        log(f"Seed {seed_idx}: conf {avg_conf:.3f} (dyn {dyn_conf:.3f}){obs_str}")

        if args.submit:
            submit_seed(session, round_id, seed_idx, pred)
        else:
            log(f"  Seed {seed_idx}: [{'DRY RUN' if args.dry_run else 'PREVIEW'}]")

    log("\nDone!")


if __name__ == "__main__":
    main()
