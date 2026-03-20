#!/usr/bin/env python3
"""
Astar Island Baseline — Uniform Prior + Observation Pass-through

This is the Approach C baseline. Gets a non-zero score with minimal effort.
Strategy:
  1. Fetch active round + initial states
  2. Use initial terrain as prior (mountains stay mountains, forests likely stay)
  3. Make a few strategic queries to observe actual outcomes
  4. For observed cells: use empirical distribution
  5. For unobserved cells: use terrain-based prior
  6. Floor all probabilities at 0.01, renormalize
  7. Submit predictions for all 5 seeds

Usage:
  python astar_baseline.py --token YOUR_JWT_TOKEN
  
Get your JWT token from app.ainm.no cookies (access_token).
"""

import argparse
import json
import time
import numpy as np
import requests

BASE = "https://api.ainm.no"

# Terrain code to prediction class mapping
TERRAIN_TO_CLASS = {
    0: 0,   # Empty → Empty
    1: 1,   # Settlement → Settlement
    2: 2,   # Port → Port
    3: 3,   # Ruin → Ruin
    4: 4,   # Forest → Forest
    5: 5,   # Mountain → Mountain
    10: 0,  # Ocean → Empty
    11: 0,  # Plains → Empty
}

NUM_CLASSES = 6
PROB_FLOOR = 0.01


def get_session(token: str) -> requests.Session:
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {token}"
    return s


def get_active_round(session: requests.Session) -> dict | None:
    resp = session.get(f"{BASE}/astar-island/rounds")
    resp.raise_for_status()
    rounds = resp.json()
    for r in rounds:
        if r["status"] == "active":
            return r
    return None


def get_round_detail(session: requests.Session, round_id: str) -> dict:
    resp = session.get(f"{BASE}/astar-island/rounds/{round_id}")
    resp.raise_for_status()
    return resp.json()


def build_prior_from_initial(grid: list[list[int]], height: int, width: int) -> np.ndarray:
    """Build prior probability tensor from initial terrain map."""
    prior = np.full((height, width, NUM_CLASSES), PROB_FLOOR)
    
    for y in range(height):
        for x in range(width):
            terrain = grid[y][x]
            cls = TERRAIN_TO_CLASS.get(terrain, 0)
            
            if terrain == 5:  # Mountain — static, never changes
                prior[y, x, 5] = 0.95
            elif terrain == 10:  # Ocean — static
                prior[y, x, 0] = 0.95
            elif terrain == 4:  # Forest — mostly static, small chance of settlement
                prior[y, x, 4] = 0.70
                prior[y, x, 0] = 0.10
                prior[y, x, 1] = 0.05
                prior[y, x, 3] = 0.05
            elif terrain == 1:  # Settlement — could survive, become port, or ruin
                prior[y, x, 1] = 0.40
                prior[y, x, 2] = 0.10
                prior[y, x, 3] = 0.25
                prior[y, x, 0] = 0.10
                prior[y, x, 4] = 0.05
            elif terrain == 2:  # Port — similar to settlement
                prior[y, x, 2] = 0.35
                prior[y, x, 1] = 0.15
                prior[y, x, 3] = 0.25
                prior[y, x, 0] = 0.10
            elif terrain in (0, 11):  # Empty/Plains — could get settled or forested
                prior[y, x, 0] = 0.50
                prior[y, x, 1] = 0.15
                prior[y, x, 4] = 0.15
                prior[y, x, 3] = 0.05
            
    # Renormalize
    prior = np.maximum(prior, PROB_FLOOR)
    prior = prior / prior.sum(axis=-1, keepdims=True)
    return prior


def query_viewport(session: requests.Session, round_id: str, seed_index: int,
                   x: int, y: int, w: int = 15, h: int = 15) -> dict:
    """Query the simulator for a viewport observation."""
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


def update_prediction_from_observation(prediction: np.ndarray, obs: dict,
                                        observation_counts: np.ndarray) -> None:
    """Update prediction tensor with observed data."""
    vp = obs["viewport"]
    vx, vy = vp["x"], vp["y"]
    grid = obs["grid"]
    
    for dy, row in enumerate(grid):
        for dx, terrain in enumerate(row):
            y, x = vy + dy, vx + dx
            cls = TERRAIN_TO_CLASS.get(terrain, 0)
            observation_counts[y, x, cls] += 1


def submit_prediction(session: requests.Session, round_id: str,
                       seed_index: int, prediction: np.ndarray) -> dict:
    """Submit prediction tensor for one seed."""
    resp = session.post(f"{BASE}/astar-island/submit", json={
        "round_id": round_id,
        "seed_index": seed_index,
        "prediction": prediction.tolist(),
    })
    resp.raise_for_status()
    return resp.json()


def main():
    parser = argparse.ArgumentParser(description="Astar Island Baseline")
    parser.add_argument("--token", required=True, help="JWT access_token from app.ainm.no")
    parser.add_argument("--queries-per-seed", type=int, default=8,
                        help="Queries to spend per seed (total budget: 50)")
    parser.add_argument("--dry-run", action="store_true", help="Don't submit, just preview")
    args = parser.parse_args()
    
    session = get_session(args.token)
    
    # 1. Get active round
    active = get_active_round(session)
    if not active:
        print("No active round found!")
        return
    
    round_id = active["id"]
    print(f"Active round: #{active['round_number']} (weight: {active['round_weight']})")
    print(f"Closes at: {active['closes_at']}")
    
    # 2. Get round details with initial states
    detail = get_round_detail(session, round_id)
    width = detail["map_width"]
    height = detail["map_height"]
    seeds_count = detail["seeds_count"]
    print(f"Map: {width}x{height}, {seeds_count} seeds")
    
    # 3. Check budget
    budget = session.get(f"{BASE}/astar-island/budget").json()
    queries_remaining = budget["queries_max"] - budget["queries_used"]
    print(f"Query budget: {budget['queries_used']}/{budget['queries_max']} used, {queries_remaining} remaining")
    
    queries_per_seed = min(args.queries_per_seed, queries_remaining // seeds_count)
    if queries_per_seed < 1:
        print("Not enough queries remaining for observations. Submitting prior-only predictions.")
        queries_per_seed = 0
    
    # 4. Process each seed
    for seed_idx in range(seeds_count):
        print(f"\n--- Seed {seed_idx} ---")
        
        initial_state = detail["initial_states"][seed_idx]
        initial_grid = initial_state["grid"]
        
        # Build prior from initial terrain
        prediction = build_prior_from_initial(initial_grid, height, width)
        
        if queries_per_seed > 0:
            # Make strategic viewport queries
            observation_counts = np.zeros((height, width, NUM_CLASSES))
            
            # Query strategy: tile the map with large viewports
            viewports = []
            if queries_per_seed >= 6:
                # Cover most of the map with 6 queries (3×2 grid of 15×15)
                for vy in [0, 13, 26]:
                    for vx in [0, 25]:
                        viewports.append((vx, vy, 15, min(15, height - vy)))
            elif queries_per_seed >= 4:
                # 4 queries: quadrants
                viewports = [(0, 0, 15, 15), (25, 0, 15, 15),
                             (0, 25, 15, 15), (25, 25, 15, 15)]
            else:
                # Minimal: center of map
                viewports = [(12, 12, 15, 15)]
            
            for i, (vx, vy, vw, vh) in enumerate(viewports[:queries_per_seed]):
                try:
                    obs = query_viewport(session, round_id, seed_idx, vx, vy, vw, vh)
                    update_prediction_from_observation(prediction, obs, observation_counts)
                    print(f"  Query {i+1}: viewport ({vx},{vy}) {vw}x{vh} — "
                          f"{obs['queries_used']}/{obs['queries_max']} budget used")
                    time.sleep(0.25)  # Respect rate limit (5 req/s)
                except Exception as e:
                    print(f"  Query {i+1} failed: {e}")
                    break
            
            # Blend observations into prediction
            total_obs = observation_counts.sum(axis=-1, keepdims=True)
            observed_mask = total_obs > 0
            if observed_mask.any():
                # Where we have observations, blend empirical with prior
                empirical = np.where(total_obs > 0,
                                     observation_counts / np.maximum(total_obs, 1),
                                     0)
                # Weight: more observations = more trust in empirical
                obs_weight = np.clip(total_obs / 5.0, 0, 0.8)  # Max 80% empirical
                prediction = np.where(observed_mask,
                                      obs_weight * empirical + (1 - obs_weight) * prediction,
                                      prediction)
        
        # Floor and renormalize
        prediction = np.maximum(prediction, PROB_FLOOR)
        prediction = prediction / prediction.sum(axis=-1, keepdims=True)
        
        # Validate
        sums = prediction.sum(axis=-1)
        assert np.allclose(sums, 1.0, atol=0.01), f"Prediction sums not 1.0: {sums.min()}-{sums.max()}"
        assert (prediction >= 0).all(), "Negative probabilities!"
        
        if args.dry_run:
            print(f"  [DRY RUN] Would submit {height}x{width}x{NUM_CLASSES} tensor")
            # Show some stats
            argmax = prediction.argmax(axis=-1)
            for c in range(NUM_CLASSES):
                count = (argmax == c).sum()
                print(f"    Class {c}: {count} cells predicted as dominant")
        else:
            result = submit_prediction(session, round_id, seed_idx, prediction)
            print(f"  Submitted: {result}")
    
    print("\nDone!")


if __name__ == "__main__":
    main()
