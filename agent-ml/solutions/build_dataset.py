#!/usr/bin/env python3
"""
Master Dataset Builder for Astar Island.

Extracts EVERY feature from EVERY data source:
- Initial terrain (spatial features)
- Replay data (settlement stats, temporal dynamics)
- Ground truth (targets)

Produces a single flat dataset: one row per dynamic cell per seed per round.
Model-agnostic: any brain version can train on this.

Usage:
  python build_dataset.py                    # Build from all cached data
  python build_dataset.py --output my.npz    # Custom output path
"""

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    load_cached_rounds, TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, PROB_FLOOR,
)
from regime_model import classify_round

DATA_DIR = Path(__file__).parent / "data"
REPLAY_DIR = DATA_DIR / "replays"


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def get_settlement_at(settlements, x, y):
    """Find settlement stats for a specific cell."""
    for s in settlements:
        if s.get("x") == x and s.get("y") == y:
            return s
    return None


def count_terrain_in_radius(grid, y, x, h, w, target_cls, radius):
    """Count cells of target class within Manhattan radius."""
    count = 0
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w:
                if TERRAIN_TO_CLASS.get(int(grid[ny][nx]), 0) == target_cls:
                    count += 1
    return count


def extract_cell_features(grid, y, x, h, w, replay_data=None, year=0):
    """Extract full feature vector for one cell.

    Returns dict of named features (makes it easy to add/remove features).
    """
    my_cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)

    # 8-neighbor counts
    n_counts = [0] * NUM_CLASSES
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w:
                n_counts[TERRAIN_TO_CLASS.get(int(grid[ny][nx]), 0)] += 1

    # Distance to nearest settlement
    min_dist = 99
    settle_r3 = 0
    forest_r2 = 0
    for dy in range(-5, 6):
        for dx in range(-5, 6):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w:
                ncls = TERRAIN_TO_CLASS.get(int(grid[ny][nx]), 0)
                d = abs(dy) + abs(dx)
                if ncls in (1, 2):
                    min_dist = min(min_dist, d)
                    if d <= 3:
                        settle_r3 += 1
                if ncls == 4 and d <= 2:
                    forest_r2 += 1

    # Ocean adjacency
    ocean_adj = sum(
        1 for dy in (-1, 0, 1) for dx in (-1, 0, 1)
        if (dy, dx) != (0, 0) and 0 <= y+dy < h and 0 <= x+dx < w
        and int(grid[y+dy][x+dx]) == 10
    )

    # Edge distance
    edge_dist = min(y, x, h - 1 - y, w - 1 - x)

    # Is on coastline (has both ocean and non-ocean neighbors)
    has_land = any(
        0 <= y+dy < h and 0 <= x+dx < w and int(grid[y+dy][x+dx]) != 10
        for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy, dx) != (0, 0)
    )
    is_coastal = 1 if ocean_adj > 0 and has_land else 0

    features = {
        "terrain": my_cls,
        "n_empty": n_counts[0],
        "n_settle": n_counts[1],
        "n_port": n_counts[2],
        "n_ruin": n_counts[3],
        "n_forest": n_counts[4],
        "n_mountain": n_counts[5],
        "dist_settle": min(min_dist, 6),
        "settle_r3": settle_r3,
        "forest_r2": forest_r2,
        "ocean_adj": ocean_adj,
        "edge_dist": edge_dist,
        "is_coastal": is_coastal,
    }

    # Settlement stats from replay (year 0 frame)
    food, pop, wealth, defense, has_port, alive = 0.0, 0.0, 0.0, 0.0, 0, 1
    owner_id = -1

    if replay_data and "frames" in replay_data:
        frame0 = replay_data["frames"][0]
        sett = get_settlement_at(frame0.get("settlements", []), x, y)
        if sett:
            food = sett.get("food", 0.0)
            pop = sett.get("population", 0.0)
            wealth = sett.get("wealth", 0.0)
            defense = sett.get("defense", 0.0)
            has_port = 1 if sett.get("has_port", False) else 0
            alive = 1 if sett.get("alive", True) else 0
            owner_id = sett.get("owner_id", -1)

    features["food_y0"] = food
    features["pop_y0"] = pop
    features["wealth_y0"] = wealth
    features["defense_y0"] = defense
    features["has_port"] = has_port
    features["owner_id"] = owner_id

    # Temporal features from replay intermediate frames
    if replay_data and "frames" in replay_data:
        frames = replay_data["frames"]

        # What's this cell at year 10?
        if len(frames) > 10:
            cls_y10 = TERRAIN_TO_CLASS.get(int(frames[10]["grid"][y][x]), 0)
            features["terrain_y10"] = cls_y10
            # Is it still a settlement at year 10?
            features["is_settle_y10"] = 1 if cls_y10 in (1, 2) else 0

            # Settlement stats at year 10
            sett10 = get_settlement_at(frames[10].get("settlements", []), x, y)
            features["food_y10"] = sett10.get("food", 0.0) if sett10 else 0.0
            features["pop_y10"] = sett10.get("population", 0.0) if sett10 else 0.0

        # What's this cell at year 25?
        if len(frames) > 25:
            cls_y25 = TERRAIN_TO_CLASS.get(int(frames[25]["grid"][y][x]), 0)
            features["terrain_y25"] = cls_y25
            features["is_settle_y25"] = 1 if cls_y25 in (1, 2) else 0

        # Neighborhood settlement count at year 10 and 25
        if len(frames) > 10:
            g10 = frames[10]["grid"]
            features["n_settle_y10"] = sum(
                1 for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                if (dy, dx) != (0, 0) and 0 <= y+dy < h and 0 <= x+dx < w
                and TERRAIN_TO_CLASS.get(int(g10[y+dy][x+dx]), 0) in (1, 2)
            )
        if len(frames) > 25:
            g25 = frames[25]["grid"]
            features["n_settle_y25"] = sum(
                1 for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                if (dy, dx) != (0, 0) and 0 <= y+dy < h and 0 <= x+dx < w
                and TERRAIN_TO_CLASS.get(int(g25[y+dy][x+dx]), 0) in (1, 2)
            )
    else:
        # No replay data: fill temporal features with defaults
        features["terrain_y10"] = my_cls
        features["is_settle_y10"] = 1 if my_cls in (1, 2) else 0
        features["food_y10"] = food
        features["pop_y10"] = pop
        features["terrain_y25"] = my_cls
        features["is_settle_y25"] = 1 if my_cls in (1, 2) else 0
        features["n_settle_y10"] = n_counts[1] + n_counts[2]
        features["n_settle_y25"] = n_counts[1] + n_counts[2]

    return features


# Canonical feature order (must be consistent for training/prediction)
FEATURE_NAMES = [
    "terrain", "n_empty", "n_settle", "n_port", "n_ruin", "n_forest", "n_mountain",
    "dist_settle", "settle_r3", "forest_r2", "ocean_adj", "edge_dist", "is_coastal",
    "food_y0", "pop_y0", "wealth_y0", "defense_y0", "has_port", "owner_id",
    "terrain_y10", "is_settle_y10", "food_y10", "pop_y10",
    "terrain_y25", "is_settle_y25",
    "n_settle_y10", "n_settle_y25",
    "regime_death", "regime_growth", "regime_stable",
    "total_settlements", "total_ports",
]


def build_master_dataset(rounds_data=None, replay_dir=REPLAY_DIR, exclude_round=None):
    """Build the complete dataset from all sources.

    Returns (X, Y, metadata) where:
    - X: (N, num_features) feature matrix
    - Y: (N, 6) target probabilities
    - metadata: list of dicts with round_number, seed_index, y, x per row
    """
    if rounds_data is None:
        rounds_data = load_cached_rounds()

    X_rows, Y_rows, meta = [], [], []

    for rd in rounds_data:
        rn = rd["round_number"]
        if exclude_round and rn == exclude_round:
            continue
        if not rd.get("seeds"):
            continue

        regime, _ = classify_round(rd)
        h, w = rd["map_height"], rd["map_width"]

        # Count global features
        ig0 = rd["initial_states"][0]["grid"]
        total_settle = sum(1 for y in range(h) for x in range(w)
                          if TERRAIN_TO_CLASS.get(int(ig0[y][x]), 0) == 1)
        total_ports = sum(1 for y in range(h) for x in range(w)
                         if TERRAIN_TO_CLASS.get(int(ig0[y][x]), 0) == 2)

        for si_str, sd in rd["seeds"].items():
            si = int(si_str)
            ig = rd["initial_states"][si]["grid"]
            gt = np.array(sd["ground_truth"])

            # Load replay if available
            replay_path = replay_dir / f"r{rn}_seed{si}.json"
            replay_data = None
            if replay_path.exists():
                try:
                    with open(replay_path) as f:
                        replay_data = json.load(f)
                except Exception:
                    pass

            for y in range(h):
                for x in range(w):
                    if int(ig[y][x]) in STATIC_TERRAIN:
                        continue

                    feats = extract_cell_features(ig, y, x, h, w, replay_data)

                    # Add round-level features
                    feats["regime_death"] = 1 if regime == "death" else 0
                    feats["regime_growth"] = 1 if regime == "growth" else 0
                    feats["regime_stable"] = 1 if regime == "stable" else 0
                    feats["total_settlements"] = total_settle
                    feats["total_ports"] = total_ports

                    # Build feature vector in canonical order
                    row = [feats.get(name, 0) for name in FEATURE_NAMES]
                    X_rows.append(row)
                    Y_rows.append(gt[y, x])
                    meta.append({"round": rn, "seed": si, "y": y, "x": x})

    X = np.array(X_rows, dtype=np.float32)
    Y = np.array(Y_rows, dtype=np.float32)
    log(f"Dataset: {len(X)} rows, {len(FEATURE_NAMES)} features, "
        f"from {len(set(m['round'] for m in meta))} rounds")
    return X, Y, meta


def main():
    parser = argparse.ArgumentParser(description="Build master dataset")
    parser.add_argument("--output", default=str(DATA_DIR / "master_dataset.npz"))
    args = parser.parse_args()

    X, Y, meta = build_master_dataset()

    np.savez_compressed(args.output, X=X, Y=Y)
    # Save feature names for reference
    with open(str(args.output).replace(".npz", "_features.json"), "w") as f:
        json.dump(FEATURE_NAMES, f, indent=2)
    # Save metadata
    with open(str(args.output).replace(".npz", "_meta.json"), "w") as f:
        json.dump(meta[:10], f, indent=2)  # Just first 10 for reference

    log(f"Saved to {args.output}")
    log(f"Features: {len(FEATURE_NAMES)}")
    log(f"Rows: {len(X)}")


if __name__ == "__main__":
    main()
