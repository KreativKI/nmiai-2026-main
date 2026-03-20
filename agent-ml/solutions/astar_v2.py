#!/usr/bin/env python3
"""
Astar Island v2 — Cross-Seed Learning + Smart Query Allocation

Improvements over baseline:
  - Cross-seed transition matrix (observations from any seed inform all seeds)
  - Settlement-targeted viewport placement (skip ocean/mountain waste)
  - Tiered query budget: seeds 0-1 get most queries, 3-4 get fewest
  - Round polling: waits for active round instead of exiting
  - Post-round analysis fetching for learning between rounds
  - Persistent transition data saved to disk for round-over-round improvement

Usage:
  python astar_v2.py --token TOKEN                    # PREVIEW: no queries spent, shows predictions from saved data
  python astar_v2.py --token TOKEN --observe           # Spends queries, does NOT submit. Review output first.
  python astar_v2.py --token TOKEN --submit            # Full run: observe + submit. REQUIRES JC's approval.
  python astar_v2.py --token TOKEN --poll              # Wait for next active round (default: preview mode)
  python astar_v2.py --token TOKEN --learn             # Fetch analysis from completed rounds
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

# Terrain code to prediction class mapping
# Grid values 10 (Ocean) and 11 (Plains) both map to class 0 (Empty) in predictions
TERRAIN_TO_CLASS = {
    0: 0,    # Empty -> Empty
    1: 1,    # Settlement -> Settlement
    2: 2,    # Port -> Port
    3: 3,    # Ruin -> Ruin
    4: 4,    # Forest -> Forest
    5: 5,    # Mountain -> Mountain
    10: 0,   # Ocean -> Empty
    11: 0,   # Plains -> Empty
}

# Terrain codes that are static (never change after year 0)
STATIC_TERRAIN = {5, 10}  # Mountain, Ocean

NUM_CLASSES = 6
PROB_FLOOR = 0.01

# Query budget allocation per seed (total: 50)
QUERY_BUDGET = {0: 15, 1: 15, 2: 10, 3: 5, 4: 5}


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def get_session(token: str) -> requests.Session:
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {token}"
    s.headers["User-Agent"] = "astar-v2/nmiai-2026"
    return s


def get_rounds(session: requests.Session) -> list[dict]:
    resp = session.get(f"{BASE}/astar-island/rounds")
    resp.raise_for_status()
    return resp.json()


def get_active_round(session: requests.Session) -> dict | None:
    for r in get_rounds(session):
        if r["status"] == "active":
            return r
    return None


def poll_for_active_round(session: requests.Session, max_wait_min: int = 30) -> dict | None:
    """Poll every 30 seconds until an active round appears or timeout."""
    log(f"No active round. Polling for up to {max_wait_min} minutes...")
    deadline = time.time() + max_wait_min * 60
    while time.time() < deadline:
        active = get_active_round(session)
        if active:
            return active
        remaining = int((deadline - time.time()) / 60)
        log(f"  Still no active round. {remaining} min remaining. Checking again in 30s...")
        time.sleep(30)
    return None


def get_round_detail(session: requests.Session, round_id: str) -> dict:
    resp = session.get(f"{BASE}/astar-island/rounds/{round_id}")
    resp.raise_for_status()
    return resp.json()


def get_budget(session: requests.Session) -> dict:
    resp = session.get(f"{BASE}/astar-island/budget")
    resp.raise_for_status()
    return resp.json()


def find_dynamic_regions(grid: list[list[int]], height: int, width: int) -> list[tuple[int, int, int, int]]:
    """Find viewport rectangles that cover dynamic (non-static) terrain.

    Returns list of (x, y, w, h) viewports targeting settlement clusters
    and other dynamic regions, avoiding pure ocean/mountain areas.
    """
    # Mark cells as dynamic or static
    dynamic = np.zeros((height, width), dtype=bool)
    for y in range(height):
        for x in range(width):
            terrain = grid[y][x]
            if terrain not in STATIC_TERRAIN:
                dynamic[y, x] = True

    # Find bounding box of all dynamic cells
    dynamic_ys, dynamic_xs = np.where(dynamic)
    if len(dynamic_ys) == 0:
        return [(0, 0, 15, 15)]  # Fallback: center

    # Generate overlapping 15x15 viewports covering all dynamic regions
    viewports = []
    min_y, max_y = dynamic_ys.min(), dynamic_ys.max()
    min_x, max_x = dynamic_xs.min(), dynamic_xs.max()

    # Tile dynamic bounding box with 15x15 viewports (12-cell stride for overlap)
    stride = 12
    for vy in range(max(0, min_y - 2), min(max_y + 2, height - 5 + 1), stride):
        for vx in range(max(0, min_x - 2), min(max_x + 2, width - 5 + 1), stride):
            # Clamp to ensure minimum 5-cell viewport
            vx_clamped = min(vx, width - 5)
            vy_clamped = min(vy, height - 5)
            vw = min(15, width - vx_clamped)
            vh = min(15, height - vy_clamped)
            if vw >= 5 and vh >= 5:
                # Count dynamic cells in this viewport
                region = dynamic[vy_clamped:vy_clamped+vh, vx_clamped:vx_clamped+vw]
                dyn_count = region.sum()
                viewports.append((vx_clamped, vy_clamped, vw, vh, dyn_count))

    # Sort by dynamic cell count (most dynamic first)
    viewports.sort(key=lambda v: v[4], reverse=True)

    # Return without the count
    return [(vx, vy, vw, vh) for vx, vy, vw, vh, _ in viewports]


def build_prior(grid: list[list[int]], height: int, width: int,
                settlements: list[dict]) -> np.ndarray:
    """Build prior probability tensor from initial terrain + settlement positions."""
    prior = np.full((height, width, NUM_CLASSES), PROB_FLOOR)

    # Settlement position lookup for adjacency reasoning
    settlement_positions = set()
    port_positions = set()
    for s in settlements:
        pos = (s["x"], s["y"])
        if s.get("has_port"):
            port_positions.add(pos)
        if s.get("alive", True):
            settlement_positions.add(pos)

    for y in range(height):
        for x in range(width):
            terrain = grid[y][x]

            if terrain == 5:  # Mountain: static
                prior[y, x, 5] = 0.96
            elif terrain == 10:  # Ocean: static
                prior[y, x, 0] = 0.96
            elif terrain == 4:  # Forest: mostly static
                # Forests near settlements have higher chance of being cleared
                near_settlement = any(
                    (x + dx, y + dy) in settlement_positions
                    for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                    if (dx, dy) != (0, 0)
                )
                if near_settlement:
                    prior[y, x, 4] = 0.50
                    prior[y, x, 1] = 0.15
                    prior[y, x, 0] = 0.15
                    prior[y, x, 3] = 0.05
                else:
                    prior[y, x, 4] = 0.75
                    prior[y, x, 0] = 0.08
                    prior[y, x, 1] = 0.03
                    prior[y, x, 3] = 0.02
            elif terrain == 1:  # Settlement: dynamic
                prior[y, x, 1] = 0.35
                prior[y, x, 2] = 0.10
                prior[y, x, 3] = 0.25
                prior[y, x, 0] = 0.15
                prior[y, x, 4] = 0.05
            elif terrain == 2:  # Port: dynamic
                prior[y, x, 2] = 0.35
                prior[y, x, 1] = 0.15
                prior[y, x, 3] = 0.20
                prior[y, x, 0] = 0.15
                prior[y, x, 4] = 0.03
            elif terrain == 3:  # Ruin: can stay ruin, decay to empty, or regrow forest
                prior[y, x, 3] = 0.30
                prior[y, x, 0] = 0.35
                prior[y, x, 4] = 0.15
                prior[y, x, 1] = 0.08
            elif terrain in (0, 11):  # Empty/Plains
                # Near settlements: higher chance of becoming settled
                near_settlement = any(
                    (x + dx, y + dy) in settlement_positions
                    for dx in (-2, -1, 0, 1, 2) for dy in (-2, -1, 0, 1, 2)
                    if abs(dx) + abs(dy) <= 2 and (dx, dy) != (0, 0)
                )
                if near_settlement:
                    prior[y, x, 0] = 0.30
                    prior[y, x, 1] = 0.25
                    prior[y, x, 4] = 0.15
                    prior[y, x, 3] = 0.10
                    prior[y, x, 2] = 0.05
                else:
                    prior[y, x, 0] = 0.55
                    prior[y, x, 4] = 0.20
                    prior[y, x, 1] = 0.08
                    prior[y, x, 3] = 0.03

    # Floor and renormalize
    prior = np.maximum(prior, PROB_FLOOR)
    prior = prior / prior.sum(axis=-1, keepdims=True)
    return prior


def query_viewport(session: requests.Session, round_id: str, seed_index: int,
                   x: int, y: int, w: int = 15, h: int = 15) -> dict:
    resp = session.post(f"{BASE}/astar-island/simulate", json={
        "round_id": round_id,
        "seed_index": seed_index,
        "viewport_x": x,
        "viewport_y": y,
        "viewport_w": w,
        "viewport_h": h,
    })
    resp.raise_for_status()
    return resp.json()


def build_transition_matrix(initial_grids: list[list[list[int]]],
                            observations: dict,
                            height: int, width: int) -> np.ndarray:
    """Build a 6x6 transition matrix from (initial terrain -> observed final terrain).

    observations: dict of {seed_idx: {(y,x): list_of_observed_classes}}
    This is the core cross-seed learning mechanism.
    """
    # Count transitions: transition_counts[initial_class][final_class]
    counts = np.ones((NUM_CLASSES, NUM_CLASSES))  # Laplace smoothing

    for seed_idx, seed_obs in observations.items():
        grid = initial_grids[seed_idx]
        for (y, x), final_classes in seed_obs.items():
            initial_terrain = grid[y][x]
            initial_cls = TERRAIN_TO_CLASS.get(initial_terrain, 0)
            for final_cls in final_classes:
                counts[initial_cls][final_cls] += 1

    # Normalize rows to get probabilities
    row_sums = counts.sum(axis=1, keepdims=True)
    transition = counts / row_sums
    return transition


def apply_transition_matrix(grid: list[list[int]], transition: np.ndarray,
                            height: int, width: int) -> np.ndarray:
    """Apply transition matrix to initial grid to get predicted probabilities."""
    prediction = np.full((height, width, NUM_CLASSES), PROB_FLOOR)
    for y in range(height):
        for x in range(width):
            terrain = grid[y][x]
            cls = TERRAIN_TO_CLASS.get(terrain, 0)
            prediction[y, x] = transition[cls]

    prediction = np.maximum(prediction, PROB_FLOOR)
    prediction = prediction / prediction.sum(axis=-1, keepdims=True)
    return prediction


def blend_predictions(prior: np.ndarray, transition_pred: np.ndarray,
                      observation_counts: np.ndarray,
                      prior_weight: float = 0.3,
                      transition_weight: float = 0.3,
                      obs_weight: float = 0.4) -> np.ndarray:
    """Blend prior, transition model, and direct observations."""
    total_obs = observation_counts.sum(axis=-1, keepdims=True)
    has_obs = total_obs > 0

    # Empirical distribution from observations
    empirical = np.where(total_obs > 0,
                         observation_counts / np.maximum(total_obs, 1),
                         0)

    # Dynamic weights: more observations = trust empirical more
    # Scale obs confidence by observation count
    obs_confidence = np.clip(total_obs / 3.0, 0, 0.85)

    # Where we have observations: blend all three, weighted by obs count
    result = np.where(
        has_obs,
        obs_confidence * empirical + (1 - obs_confidence) * (0.5 * prior + 0.5 * transition_pred),
        # Where we have no observations: blend prior and transition model
        prior_weight / (prior_weight + transition_weight) * prior +
        transition_weight / (prior_weight + transition_weight) * transition_pred
    )

    # Floor and renormalize
    result = np.maximum(result, PROB_FLOOR)
    result = result / result.sum(axis=-1, keepdims=True)
    return result


def submit_prediction(session: requests.Session, round_id: str,
                      seed_index: int, prediction: np.ndarray) -> dict:
    resp = session.post(f"{BASE}/astar-island/submit", json={
        "round_id": round_id,
        "seed_index": seed_index,
        "prediction": prediction.tolist(),
    })
    resp.raise_for_status()
    return resp.json()


def validate_prediction(prediction: np.ndarray, height: int, width: int) -> bool:
    """Validate prediction tensor before submission."""
    if prediction.shape != (height, width, NUM_CLASSES):
        log(f"  ERROR: Wrong shape {prediction.shape}, expected ({height},{width},{NUM_CLASSES})")
        return False

    sums = prediction.sum(axis=-1)
    if not np.allclose(sums, 1.0, atol=0.01):
        log(f"  ERROR: Row sums range [{sums.min():.4f}, {sums.max():.4f}], expected ~1.0")
        return False

    if (prediction < 0).any():
        log(f"  ERROR: Negative probabilities found")
        return False

    if (prediction < PROB_FLOOR - 0.001).any():
        log(f"  ERROR: Probabilities below floor {PROB_FLOOR} found")
        return False

    return True


def save_transition_data(transition: np.ndarray, round_number: int) -> None:
    """Save transition matrix to disk for persistence between runs."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"transition_round_{round_number}.npy"
    np.save(path, transition)
    log(f"Transition matrix saved to {path}")


def load_latest_transition() -> np.ndarray | None:
    """Load most recent transition matrix from disk."""
    if not DATA_DIR.exists():
        return None
    files = sorted(DATA_DIR.glob("transition_round_*.npy"))
    if not files:
        return None
    path = files[-1]
    log(f"Loaded transition matrix from {path}")
    return np.load(path)


def fetch_analysis(session: requests.Session, round_id: str, seeds_count: int) -> dict:
    """Fetch post-round analysis for all seeds. Returns {seed_idx: analysis_data}."""
    analyses = {}
    for seed_idx in range(seeds_count):
        try:
            resp = session.get(f"{BASE}/astar-island/analysis/{round_id}/{seed_idx}")
            if resp.status_code == 200:
                analyses[seed_idx] = resp.json()
                log(f"  Analysis seed {seed_idx}: score = {analyses[seed_idx].get('score', 'N/A')}")
        except Exception as e:
            log(f"  Analysis seed {seed_idx} failed: {e}")
    return analyses


def learn_from_completed_rounds(session: requests.Session) -> np.ndarray | None:
    """Fetch analysis from all completed rounds, build aggregate transition matrix."""
    rounds = get_rounds(session)
    completed = [r for r in rounds if r["status"] == "completed"]

    if not completed:
        log("No completed rounds to learn from.")
        return None

    log(f"Learning from {len(completed)} completed round(s)...")

    # Aggregate transition counts across all completed rounds
    counts = np.ones((NUM_CLASSES, NUM_CLASSES))  # Laplace smoothing

    for r in completed:
        round_id = r["id"]
        round_num = r["round_number"]
        log(f"  Round {round_num}:")

        try:
            detail = get_round_detail(session, round_id)
        except Exception as e:
            log(f"    Failed to get detail: {e}")
            continue

        for seed_idx in range(detail.get("seeds_count", 5)):
            try:
                resp = session.get(f"{BASE}/astar-island/analysis/{round_id}/{seed_idx}")
                if resp.status_code != 200:
                    continue
                analysis = resp.json()
                initial_grid = analysis.get("initial_grid")
                ground_truth = analysis.get("ground_truth")
                if not initial_grid or not ground_truth:
                    continue

                # Ground truth is H x W x 6 probability tensor
                # Use argmax as the "most likely" final terrain
                gt_array = np.array(ground_truth)
                height, width = len(initial_grid), len(initial_grid[0])

                for y in range(height):
                    for x in range(width):
                        initial_terrain = initial_grid[y][x]
                        initial_cls = TERRAIN_TO_CLASS.get(initial_terrain, 0)
                        # Add probability mass to transition counts
                        for final_cls in range(NUM_CLASSES):
                            counts[initial_cls][final_cls] += gt_array[y][x][final_cls]

                log(f"    Seed {seed_idx}: incorporated ground truth")
            except Exception as e:
                log(f"    Seed {seed_idx} analysis failed: {e}")

    # Normalize
    row_sums = counts.sum(axis=1, keepdims=True)
    transition = counts / row_sums

    log("Learned transition matrix:")
    class_names = ["Empty", "Settlement", "Port", "Ruin", "Forest", "Mountain"]
    for i, name in enumerate(class_names):
        top3 = sorted(range(NUM_CLASSES), key=lambda j: transition[i][j], reverse=True)[:3]
        top3_str = ", ".join(f"{class_names[j]}:{transition[i][j]:.2f}" for j in top3)
        log(f"  {name} -> {top3_str}")

    return transition


def run_round(session: requests.Session, active: dict,
              mode: str = "preview",
              learned_transition: np.ndarray | None = None) -> None:
    """Execute one round. Modes: preview (no API queries), observe (queries but no submit), submit (full run)."""
    round_id = active["id"]
    round_num = active["round_number"]
    log(f"Active round: #{round_num} (weight: {active['round_weight']:.4f})")
    log(f"Closes at: {active['closes_at']}")
    log(f"Mode: {mode.upper()}")

    detail = get_round_detail(session, round_id)
    width = detail["map_width"]
    height = detail["map_height"]
    seeds_count = detail["seeds_count"]
    log(f"Map: {width}x{height}, {seeds_count} seeds")

    budget = get_budget(session)
    queries_remaining = budget["queries_max"] - budget["queries_used"]
    log(f"Query budget: {budget['queries_used']}/{budget['queries_max']} used, {queries_remaining} remaining")

    if mode == "preview":
        log("PREVIEW MODE: Using saved transition data + priors only. Zero queries spent.")

    # Phase 1: Build priors for all seeds
    initial_grids = []
    priors = []
    for seed_idx in range(seeds_count):
        state = detail["initial_states"][seed_idx]
        initial_grids.append(state["grid"])
        prior = build_prior(state["grid"], height, width, state.get("settlements", []))
        priors.append(prior)

    # Phase 2: Strategic observation (skipped in preview mode)
    all_observations = {}
    all_obs_counts = {}
    queries_used = budget["queries_used"]

    for seed_idx in range(seeds_count):
        if mode == "preview":
            all_observations[seed_idx] = {}
            all_obs_counts[seed_idx] = np.zeros((height, width, NUM_CLASSES))
            continue

        seed_budget = QUERY_BUDGET.get(seed_idx, 5)
        available = min(seed_budget, budget["queries_max"] - queries_used)

        if available <= 0:
            log(f"Seed {seed_idx}: No queries available, using prior only")
            all_observations[seed_idx] = {}
            all_obs_counts[seed_idx] = np.zeros((height, width, NUM_CLASSES))
            continue

        log(f"Seed {seed_idx}: Allocating {available} queries")

        # Get targeted viewports for this seed
        viewports = find_dynamic_regions(initial_grids[seed_idx], height, width)

        seed_obs = {}
        obs_counts = np.zeros((height, width, NUM_CLASSES))

        for i, (vx, vy, vw, vh) in enumerate(viewports[:available]):
            try:
                obs = query_viewport(session, round_id, seed_idx, vx, vy, vw, vh)
                queries_used = obs["queries_used"]

                vp = obs["viewport"]
                for dy, row in enumerate(obs["grid"]):
                    for dx, terrain in enumerate(row):
                        y_abs, x_abs = vp["y"] + dy, vp["x"] + dx
                        cls = TERRAIN_TO_CLASS.get(terrain, 0)
                        obs_counts[y_abs, x_abs, cls] += 1
                        key = (y_abs, x_abs)
                        if key not in seed_obs:
                            seed_obs[key] = []
                        seed_obs[key].append(cls)

                log(f"  Query {i+1}/{available}: ({vx},{vy}) {vw}x{vh} — "
                    f"budget {queries_used}/{budget['queries_max']}")
                time.sleep(0.22)  # Rate limit: 5 req/s
            except requests.HTTPError as e:
                if e.response and e.response.status_code == 429:
                    log(f"  Query budget exhausted at query {i+1}")
                    break
                log(f"  Query {i+1} failed: {e}")
                break
            except Exception as e:
                log(f"  Query {i+1} failed: {e}")
                break

        all_observations[seed_idx] = seed_obs
        all_obs_counts[seed_idx] = obs_counts

    # Phase 3: Build cross-seed transition matrix
    transition = build_transition_matrix(initial_grids, all_observations, height, width)

    # If we have a learned transition from previous rounds, blend it in
    if learned_transition is not None:
        log("Blending learned transition from previous rounds (60% learned, 40% current)")
        transition = 0.6 * learned_transition + 0.4 * transition
        transition = transition / transition.sum(axis=1, keepdims=True)

    # Log transition matrix summary
    class_names = ["Empty", "Settl", "Port", "Ruin", "Forest", "Mount"]
    log("Transition matrix (top 2 per initial terrain):")
    for i, name in enumerate(class_names):
        top2 = sorted(range(NUM_CLASSES), key=lambda j: transition[i][j], reverse=True)[:2]
        s = ", ".join(f"{class_names[j]}:{transition[i][j]:.2f}" for j in top2)
        log(f"  {name} -> {s}")

    save_transition_data(transition, active["round_number"])

    # Phase 4: Build final predictions per seed
    for seed_idx in range(seeds_count):
        log(f"\n--- Seed {seed_idx}: Building prediction ---")

        # Transition-based prediction
        trans_pred = apply_transition_matrix(
            initial_grids[seed_idx], transition, height, width
        )

        # Blend prior + transition + observations
        prediction = blend_predictions(
            priors[seed_idx], trans_pred, all_obs_counts[seed_idx]
        )

        # Validate
        if not validate_prediction(prediction, height, width):
            log(f"  Seed {seed_idx}: VALIDATION FAILED, skipping submission")
            continue

        # Stats
        argmax = prediction.argmax(axis=-1)
        avg_confidence = prediction.max(axis=-1).mean()
        log(f"  Avg confidence: {avg_confidence:.3f}")
        for c, name in enumerate(class_names):
            count = (argmax == c).sum()
            if count > 0:
                log(f"    {name}: {count} cells")

        if mode in ("preview", "observe"):
            label = "PREVIEW" if mode == "preview" else "OBSERVE"
            log(f"  [{label}] Would submit {height}x{width}x{NUM_CLASSES} tensor")
        elif mode == "submit":
            try:
                result = submit_prediction(session, round_id, seed_idx, prediction)
                log(f"  Submitted seed {seed_idx}: {result.get('status', 'unknown')}")
            except Exception as e:
                log(f"  Submission failed for seed {seed_idx}: {e}")

    log("\nRound complete!")


def main():
    parser = argparse.ArgumentParser(description="Astar Island v2 — Cross-Seed Learning")
    parser.add_argument("--token", required=True, help="JWT access_token from app.ainm.no")

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--preview", action="store_const", dest="mode", const="preview",
                            help="DEFAULT: No queries spent. Shows predictions from saved data + priors only.")
    mode_group.add_argument("--observe", action="store_const", dest="mode", const="observe",
                            help="Spend observation queries but do NOT submit. Review before committing.")
    mode_group.add_argument("--submit", action="store_const", dest="mode", const="submit",
                            help="Full run: observe + submit. Requires JC's approval.")
    parser.set_defaults(mode="preview")

    parser.add_argument("--poll", action="store_true",
                        help="Wait for active round if none found (up to 30 min)")
    parser.add_argument("--learn", action="store_true",
                        help="Fetch analysis from completed rounds before predicting")
    parser.add_argument("--poll-timeout", type=int, default=30,
                        help="Max minutes to poll for active round (default: 30)")
    args = parser.parse_args()

    session = get_session(args.token)

    # Learn from completed rounds if requested
    learned_transition = None
    if args.learn:
        learned_transition = learn_from_completed_rounds(session)
        if learned_transition is not None:
            save_transition_data(learned_transition, 0)  # Save as "round 0" = learned
    else:
        # Try to load from disk
        learned_transition = load_latest_transition()

    # Find active round
    active = get_active_round(session)
    if not active:
        if args.poll:
            active = poll_for_active_round(session, args.poll_timeout)
        if not active:
            log("No active round found.")
            # Show completed rounds for reference
            rounds = get_rounds(session)
            for r in rounds:
                log(f"  Round {r['round_number']}: {r['status']} "
                    f"(started {r['started_at']}, closes {r['closes_at']})")
            return

    run_round(session, active, mode=args.mode,
              learned_transition=learned_transition)


if __name__ == "__main__":
    main()
