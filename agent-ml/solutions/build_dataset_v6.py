#!/usr/bin/env python3
"""
Master Dataset Builder V6 for Astar Island.

Extends V5 dataset with 5 new spatial density features:
- settle_r5: settlement count within Manhattan distance 5
- mountain_r3: mountain count within distance 3
- port_r3: port count within distance 3
- ruin_r3: ruin count within distance 3
- forest_r5: forest count within distance 5

Total: 56 features (51 original + 5 new spatial).
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    load_cached_rounds, log, TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES,
)
from regime_model import classify_round

DATA_DIR = Path(__file__).parent / "data"
REPLAY_DIR = DATA_DIR / "replays"

OCEAN_RAW = {10, 11}


def get_settlement_at(settlements, x, y):
    for s in settlements:
        if s.get("x") == x and s.get("y") == y:
            return s
    return None


def extract_cell_features(grid, y, x, h, w, replay_data=None):
    """Extract full feature vector for one cell (56 features)."""
    my_cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)

    # 8-neighbor scan
    n_counts = [0] * NUM_CLASSES
    ocean_adj = 0
    has_land = False
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w:
                raw = int(grid[ny][nx])
                n_counts[TERRAIN_TO_CLASS.get(raw, 0)] += 1
                if raw in OCEAN_RAW:
                    ocean_adj += 1
                else:
                    has_land = True

    # Extended neighborhood (radius 5) with NEW density counts
    min_dist = 99
    settle_r3 = 0
    settle_r5 = 0
    forest_r2 = 0
    forest_r5 = 0
    mountain_r3 = 0
    port_r3 = 0
    ruin_r3 = 0
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
                    if d <= 5:
                        settle_r5 += 1
                if ncls == 2 and d <= 3:
                    port_r3 += 1
                if ncls == 3 and d <= 3:
                    ruin_r3 += 1
                if ncls == 4:
                    if d <= 2:
                        forest_r2 += 1
                    if d <= 5:
                        forest_r5 += 1
                if ncls == 5 and d <= 3:
                    mountain_r3 += 1

    edge_dist = min(y, x, h - 1 - y, w - 1 - x)
    is_coastal = 1 if ocean_adj > 0 and has_land else 0

    features = {
        # Original 13 spatial
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
        # NEW: 5 spatial density features
        "settle_r5": settle_r5,
        "mountain_r3": mountain_r3,
        "port_r3": port_r3,
        "ruin_r3": ruin_r3,
        "forest_r5": forest_r5,
    }

    # Settlement stats and temporal features from replay
    food, pop, wealth, defense, has_port = 0.0, 0.0, 0.0, 0.0, 0
    owner_id = -1
    is_settle_y0 = 1 if my_cls in (1, 2) else 0
    frames = replay_data.get("frames") if replay_data else None

    if frames:
        sett = get_settlement_at(frames[0].get("settlements", []), x, y)
        if sett:
            food = sett.get("food", 0.0)
            pop = sett.get("population", 0.0)
            wealth = sett.get("wealth", 0.0)
            defense = sett.get("defense", 0.0)
            has_port = 1 if sett.get("has_port", False) else 0
            owner_id = sett.get("owner_id", -1)

        for yr in (10, 25):
            if len(frames) > yr:
                frame = frames[yr]
                cls_yr = TERRAIN_TO_CLASS.get(int(frame["grid"][y][x]), 0)
                features[f"terrain_y{yr}"] = cls_yr
                features[f"is_settle_y{yr}"] = 1 if cls_yr in (1, 2) else 0
                features[f"n_settle_y{yr}"] = sum(
                    1 for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                    if (dy, dx) != (0, 0) and 0 <= y+dy < h and 0 <= x+dx < w
                    and TERRAIN_TO_CLASS.get(int(frame["grid"][y+dy][x+dx]), 0) in (1, 2)
                )
                sett_yr = get_settlement_at(frame.get("settlements", []), x, y)
                features[f"food_y{yr}"] = sett_yr.get("food", 0.0) if sett_yr else 0.0
                features[f"pop_y{yr}"] = sett_yr.get("population", 0.0) if sett_yr else 0.0
                features[f"wealth_y{yr}"] = sett_yr.get("wealth", 0.0) if sett_yr else 0.0
                features[f"defense_y{yr}"] = sett_yr.get("defense", 0.0) if sett_yr else 0.0
                if is_settle_y0:
                    features[f"survived_y{yr}"] = 1 if cls_yr in (1, 2) else 0

    features["food_y0"] = food
    features["pop_y0"] = pop
    features["wealth_y0"] = wealth
    features["defense_y0"] = defense
    features["has_port"] = has_port
    features["owner_id"] = owner_id

    temporal_defaults = {
        "terrain_y10": my_cls,
        "is_settle_y10": is_settle_y0,
        "food_y10": food,
        "pop_y10": pop,
        "wealth_y10": wealth,
        "defense_y10": defense,
        "terrain_y25": my_cls,
        "is_settle_y25": is_settle_y0,
        "n_settle_y10": n_counts[1] + n_counts[2],
        "n_settle_y25": n_counts[1] + n_counts[2],
        "food_y25": food,
        "pop_y25": pop,
        "wealth_y25": wealth,
        "defense_y25": defense,
        "survived_y10": is_settle_y0,
        "survived_y25": is_settle_y0,
    }
    for fname, default in temporal_defaults.items():
        if fname not in features:
            features[fname] = default

    return features


# Canonical feature order: 56 features
FEATURE_NAMES = [
    # Spatial (13 original)
    "terrain", "n_empty", "n_settle", "n_port", "n_ruin", "n_forest", "n_mountain",
    "dist_settle", "settle_r3", "forest_r2", "ocean_adj", "edge_dist", "is_coastal",
    # NEW spatial density (5)
    "settle_r5", "mountain_r3", "port_r3", "ruin_r3", "forest_r5",
    # Year 0 settlement stats (6)
    "food_y0", "pop_y0", "wealth_y0", "defense_y0", "has_port", "owner_id",
    # Year 10 temporal (8)
    "terrain_y10", "is_settle_y10", "food_y10", "pop_y10", "wealth_y10", "defense_y10",
    "n_settle_y10", "survived_y10",
    # Year 25 temporal (8)
    "terrain_y25", "is_settle_y25", "n_settle_y25",
    "food_y25", "pop_y25", "wealth_y25", "defense_y25", "survived_y25",
    # Regime (3)
    "regime_death", "regime_growth", "regime_stable",
    # Round-level counts (2)
    "total_settlements", "total_ports",
    # Round-level trajectory features (7)
    "settle_growth_y10", "settle_growth_y25",
    "wealth_decay_y10", "wealth_decay_y25",
    "faction_consol_y10",
    "pop_trend_y10", "food_trend_y10",
    # Round-level aggregates (4)
    "total_wealth_y0", "total_food_y0", "avg_defense_y0", "total_factions_y0",
]


def _compute_trajectory_features(replay_data, total_settle_y0):
    """Compute round-level trajectory features from replay aggregate stats."""
    defaults = {
        "settle_growth_y10": 1.0,
        "settle_growth_y25": 1.0,
        "wealth_decay_y10": 1.0,
        "wealth_decay_y25": 1.0,
        "faction_consol_y10": 1.0,
        "pop_trend_y10": 1.0,
        "food_trend_y10": 1.0,
        "total_wealth_y0": 0.0,
        "total_food_y0": 0.0,
        "avg_defense_y0": 0.0,
        "total_factions_y0": 0.0,
    }

    if not replay_data:
        return defaults

    frames = replay_data.get("frames")
    if not frames or len(frames) < 26:
        return defaults

    def alive_stats(frame):
        alive = [s for s in frame.get("settlements", []) if s.get("alive", False)]
        n = len(alive)
        if n == 0:
            return {"n": 0, "avg_w": 0.0, "avg_p": 0.0, "avg_f": 0.0,
                    "avg_d": 0.0, "factions": 0, "total_w": 0.0, "total_f": 0.0}
        total_w = sum(s.get("wealth", 0.0) for s in alive)
        total_f = sum(s.get("food", 0.0) for s in alive)
        return {
            "n": n,
            "avg_w": total_w / n,
            "avg_p": sum(s.get("population", 0.0) for s in alive) / n,
            "avg_f": total_f / n,
            "avg_d": sum(s.get("defense", 0.0) for s in alive) / n,
            "factions": len(set(s.get("owner_id", -1) for s in alive)),
            "total_w": total_w,
            "total_f": total_f,
        }

    y0 = alive_stats(frames[0])
    y10 = alive_stats(frames[10])
    y25 = alive_stats(frames[25])

    safe_n0 = max(y0["n"], 1)
    safe_w0 = max(y0["avg_w"], 0.001)
    safe_p0 = max(y0["avg_p"], 0.001)
    safe_f0 = max(y0["avg_f"], 0.001)
    safe_fac0 = max(y0["factions"], 1)

    return {
        "settle_growth_y10": y10["n"] / safe_n0,
        "settle_growth_y25": y25["n"] / safe_n0,
        "wealth_decay_y10": y10["avg_w"] / safe_w0,
        "wealth_decay_y25": y25["avg_w"] / safe_w0,
        "faction_consol_y10": y10["factions"] / safe_fac0,
        "pop_trend_y10": y10["avg_p"] / safe_p0,
        "food_trend_y10": y10["avg_f"] / safe_f0,
        "total_wealth_y0": y0["total_w"],
        "total_food_y0": y0["total_f"],
        "avg_defense_y0": y0["avg_d"],
        "total_factions_y0": float(y0["factions"]),
    }


def build_master_dataset(rounds_data=None, replay_dir=REPLAY_DIR, exclude_round=None):
    """Build 56-feature dataset from all sources."""
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

        for si_str, sd in rd["seeds"].items():
            si = int(si_str)
            ig = rd["initial_states"][si]["grid"]

            total_settle, total_ports = 0, 0
            for row in ig:
                for cell in row:
                    cls = TERRAIN_TO_CLASS.get(int(cell), 0)
                    if cls == 1:
                        total_settle += 1
                    elif cls == 2:
                        total_ports += 1
            gt = np.array(sd["ground_truth"])

            replay_path = replay_dir / f"r{rn}_seed{si}.json"
            replay_data = None
            if replay_path.exists():
                try:
                    with open(replay_path) as f:
                        replay_data = json.load(f)
                except Exception:
                    pass

            traj = _compute_trajectory_features(replay_data, total_settle)

            for y in range(h):
                for x in range(w):
                    if int(ig[y][x]) in STATIC_TERRAIN:
                        continue

                    feats = extract_cell_features(ig, y, x, h, w, replay_data)
                    for regime_name in ("death", "growth", "stable"):
                        feats[f"regime_{regime_name}"] = 1 if regime == regime_name else 0
                    feats["total_settlements"] = total_settle
                    feats["total_ports"] = total_ports
                    feats.update(traj)

                    row = [feats.get(name, 0) for name in FEATURE_NAMES]
                    X_rows.append(row)
                    Y_rows.append(gt[y, x])
                    meta.append({"round": rn, "seed": si, "y": y, "x": x})

    X = np.array(X_rows, dtype=np.float32)
    Y = np.array(Y_rows, dtype=np.float32)
    log(f"Dataset V6: {len(X)} rows, {len(FEATURE_NAMES)} features, "
        f"from {len(set(m['round'] for m in meta))} rounds")
    return X, Y, meta


def main():
    parser = argparse.ArgumentParser(description="Build V6 master dataset (56 features)")
    parser.add_argument("--output", default=str(DATA_DIR / "master_dataset_v6.npz"))
    args = parser.parse_args()

    X, Y, meta = build_master_dataset()

    out = Path(args.output)
    stem = str(out).replace(".npz", "")
    np.savez_compressed(out, X=X, Y=Y)
    with open(f"{stem}_features.json", "w") as f:
        json.dump(FEATURE_NAMES, f, indent=2)

    log(f"Saved to {args.output}")
    log(f"Features: {len(FEATURE_NAMES)}")
    log(f"Rows: {len(X)}")


if __name__ == "__main__":
    main()
