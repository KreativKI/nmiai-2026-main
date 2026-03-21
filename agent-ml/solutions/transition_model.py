#!/usr/bin/env python3
"""
Neighborhood-Conditioned Transition Model for Astar Island.

Builds transition probability matrices from replay data, conditioned on
regime, terrain type, and neighborhood composition. Used by CA-Markov model.

Hierarchical fallback (matching regime_model.py pattern):
1. Full key: (regime, terrain, n_settle, n_forest) -- use if 10+ observations
2. Reduced key: (regime, terrain, n_dynamic, has_forest) -- use if 20+ observations
3. Minimal key: (regime, terrain) -- always available
4. Global: (terrain) -- absolute fallback

Usage:
  python transition_model.py              # Build and print stats
  python transition_model.py --save       # Build and save to JSON
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    load_cached_rounds, TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, CLASS_NAMES,
    PROB_FLOOR,
)
from regime_model import classify_round

DATA_DIR = Path(__file__).parent / "data"
REPLAY_DIR = DATA_DIR / "replays"
OCEAN_RAW = {10, 11}
SKIP_CELLS = STATIC_TERRAIN | OCEAN_RAW

MIN_OBS_FULL = 10
MIN_OBS_REDUCED = 20


def count_neighbors(grid, y, x, h, w):
    """Count settlement and forest neighbors for a cell."""
    n_settle, n_forest = 0, 0
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w:
                cls = TERRAIN_TO_CLASS.get(int(grid[ny][nx]), 0)
                if cls in (1, 2):
                    n_settle += 1
                elif cls == 4:
                    n_forest += 1
    return n_settle, n_forest


def build_transition_tables(replay_dir=REPLAY_DIR, rounds_data=None):
    """Build hierarchical transition tables from all replay data.

    Returns dict with 4 levels of lookup tables, each mapping
    a key tuple to (sum_dist[6], count).
    """
    if rounds_data is None:
        rounds_data = load_cached_rounds()

    regimes = {}
    for rd in rounds_data:
        regime, _ = classify_round(rd)
        regimes[rd["round_number"]] = regime

    # 4-level tables: key -> [sum_of_distributions, count]
    full = defaultdict(lambda: [np.zeros(NUM_CLASSES), 0])
    reduced = defaultdict(lambda: [np.zeros(NUM_CLASSES), 0])
    minimal = defaultdict(lambda: [np.zeros(NUM_CLASSES), 0])
    global_t = defaultdict(lambda: [np.zeros(NUM_CLASSES), 0])

    total_transitions = 0

    for path in sorted(replay_dir.glob("r*_seed*.json")):
        parts = path.stem.split("_")
        rn = int(parts[0][1:])
        regime = regimes.get(rn)
        if regime is None:
            continue

        with open(path) as f:
            data = json.load(f)

        frames = data.get("frames", [])
        if len(frames) < 2:
            continue

        h = len(frames[0]["grid"])
        w = len(frames[0]["grid"][0])

        for t in range(len(frames) - 1):
            grid_now = frames[t]["grid"]
            grid_next = frames[t + 1]["grid"]

            for y in range(h):
                for x in range(w):
                    raw = int(grid_now[y][x])
                    if raw in SKIP_CELLS:
                        continue
                    cls_now = TERRAIN_TO_CLASS.get(raw, 0)
                    if cls_now == 0:
                        continue

                    cls_next = TERRAIN_TO_CLASS.get(int(grid_next[y][x]), 0)
                    n_settle, n_forest = count_neighbors(grid_now, y, x, h, w)

                    one_hot = np.zeros(NUM_CLASSES)
                    one_hot[cls_next] = 1.0

                    # Level 1: full
                    key_f = (regime, cls_now, n_settle, n_forest)
                    full[key_f][0] += one_hot
                    full[key_f][1] += 1

                    # Level 2: reduced
                    n_dynamic = n_settle  # settle+port neighbors
                    has_forest = 1 if n_forest > 0 else 0
                    key_r = (regime, cls_now, n_dynamic, has_forest)
                    reduced[key_r][0] += one_hot
                    reduced[key_r][1] += 1

                    # Level 3: minimal
                    key_m = (regime, cls_now)
                    minimal[key_m][0] += one_hot
                    minimal[key_m][1] += 1

                    # Level 4: global
                    key_g = (cls_now,)
                    global_t[key_g][0] += one_hot
                    global_t[key_g][1] += 1

                    total_transitions += 1

    return {
        "full": dict(full),
        "reduced": dict(reduced),
        "minimal": dict(minimal),
        "global": dict(global_t),
        "total_transitions": total_transitions,
    }


def normalize_tables(tables):
    """Normalize transition counts into probability distributions."""
    normalized = {}
    for level_name in ("full", "reduced", "minimal", "global"):
        level = tables[level_name]
        normalized[level_name] = {}
        for key, (sum_dist, count) in level.items():
            dist = sum_dist / count
            dist = np.maximum(dist, PROB_FLOOR)
            dist /= dist.sum()
            normalized[level_name][key] = (dist, count)
    return normalized


class TransitionModel:
    """Hierarchical transition model with fallback lookup."""

    def __init__(self, tables=None, replay_dir=REPLAY_DIR, rounds_data=None):
        if tables is None:
            raw = build_transition_tables(replay_dir, rounds_data)
            self.tables = normalize_tables(raw)
            self.total = raw["total_transitions"]
        else:
            self.tables = tables
            self.total = 0

    def lookup(self, regime, terrain, n_settle, n_forest):
        """Look up transition distribution with hierarchical fallback.

        Returns (prob_vector[6], level_used).
        """
        # Level 1: full
        key = (regime, terrain, n_settle, n_forest)
        if key in self.tables["full"]:
            dist, count = self.tables["full"][key]
            if count >= MIN_OBS_FULL:
                return dist.copy(), "full"

        # Level 2: reduced
        n_dynamic = n_settle
        has_forest = 1 if n_forest > 0 else 0
        key = (regime, terrain, n_dynamic, has_forest)
        if key in self.tables["reduced"]:
            dist, count = self.tables["reduced"][key]
            if count >= MIN_OBS_REDUCED:
                return dist.copy(), "reduced"

        # Level 3: minimal
        key = (regime, terrain)
        if key in self.tables["minimal"]:
            dist, _ = self.tables["minimal"][key]
            return dist.copy(), "minimal"

        # Level 4: global
        key = (terrain,)
        if key in self.tables["global"]:
            dist, _ = self.tables["global"][key]
            return dist.copy(), "global"

        # Ultimate fallback: uniform
        return np.full(NUM_CLASSES, 1.0 / NUM_CLASSES), "uniform"

    def stats(self):
        """Print table statistics."""
        print(f"Total transitions: {self.total:,}")
        for level in ("full", "reduced", "minimal", "global"):
            entries = len(self.tables[level])
            counts = [v[1] for v in self.tables[level].values()]
            if counts:
                print(f"  {level}: {entries} entries, "
                      f"obs range [{min(counts)}-{max(counts)}], "
                      f"median {int(np.median(counts))}")


def main():
    parser = argparse.ArgumentParser(description="Build transition model")
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()

    print("Building transition model from replays...")
    model = TransitionModel()
    model.stats()

    # Show sample lookups
    print("\nSample lookups:")
    for regime in ("death", "stable", "growth"):
        for terrain in (1, 4):  # Settlement, Forest
            dist, level = model.lookup(regime, terrain, n_settle=2, n_forest=1)
            names = [f"{CLASS_NAMES[i]}={dist[i]:.3f}" for i in range(NUM_CLASSES) if dist[i] > 0.02]
            print(f"  {regime}/{CLASS_NAMES[terrain]} (2s,1f): [{level}] {', '.join(names)}")

    if args.save:
        out_path = DATA_DIR / "transition_model.json"
        save_data = {}
        for level in ("full", "reduced", "minimal", "global"):
            save_data[level] = {}
            for key, (dist, count) in model.tables[level].items():
                str_key = str(key)
                save_data[level][str_key] = {
                    "dist": dist.tolist(),
                    "count": int(count),
                }
        with open(out_path, "w") as f:
            json.dump(save_data, f, indent=2)
        print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
