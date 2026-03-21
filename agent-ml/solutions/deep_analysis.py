#!/usr/bin/env python3
"""
Deep Analysis of Astar Island Replay Data.

Processes ALL replay files to validate 8 hypotheses about world mechanics.
Outputs structured findings and JSON summary.

Usage:
  python deep_analysis.py                          # Run all hypotheses
  python deep_analysis.py --output results.json    # Custom output path
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
)
from regime_model import classify_round

DATA_DIR = Path(__file__).parent / "data"
REPLAY_DIR = DATA_DIR / "replays"

OCEAN_RAW = {10, 11}


def neighbors(grid, y, x, h, w):
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w:
                yield ny, nx, grid[ny][nx]


def load_all_replays():
    """Load all replay files, grouped by round number."""
    replays = {}
    for path in sorted(REPLAY_DIR.glob("r*_seed*.json")):
        parts = path.stem.split("_")
        rn = int(parts[0][1:])
        si = int(parts[1][4:])
        with open(path) as f:
            data = json.load(f)
        replays.setdefault(rn, {})[si] = data
    return replays


def get_regime_map(rounds_data):
    """Classify regime for each round using ground truth."""
    regimes = {}
    for rd in rounds_data:
        rn = rd["round_number"]
        regime, info = classify_round(rd)
        regimes[rn] = regime
    return regimes


def cell_to_class(raw_val):
    return TERRAIN_TO_CLASS.get(int(raw_val), 0)


def has_ocean_neighbor(grid, y, x, h, w):
    return any(int(val) in OCEAN_RAW for _, _, val in neighbors(grid, y, x, h, w))


def count_mountain_neighbors(grid, y, x, h, w):
    return sum(1 for _, _, val in neighbors(grid, y, x, h, w) if cell_to_class(val) == 5)


def manhattan_distance(y1, x1, y2, x2):
    return abs(y1 - y2) + abs(x1 - x2)


# ── Hypothesis Tests ──


def h1_empty_to_forest(replays, regimes):
    """H1: Do empty cells ever become forest?"""
    print("\n=== H1: EMPTY -> FOREST TRANSITIONS ===")

    transitions_by_regime = defaultdict(lambda: {"empty_to_forest": 0, "total_empty_years": 0})

    for rn, seeds in replays.items():
        regime = regimes.get(rn, "unknown")
        for si, data in seeds.items():
            frames = data["frames"]
            h, w = len(frames[0]["grid"]), len(frames[0]["grid"][0])

            for yr in range(len(frames) - 1):
                grid_now = frames[yr]["grid"]
                grid_next = frames[yr + 1]["grid"]

                for y in range(h):
                    for x in range(w):
                        raw_now = int(grid_now[y][x])
                        if raw_now in OCEAN_RAW:
                            continue
                        cls_now = cell_to_class(raw_now)
                        cls_next = cell_to_class(grid_next[y][x])

                        if cls_now == 0:
                            transitions_by_regime[regime]["total_empty_years"] += 1
                            if cls_next == 4:
                                transitions_by_regime[regime]["empty_to_forest"] += 1

    total_e2f = sum(v["empty_to_forest"] for v in transitions_by_regime.values())
    total_empty = sum(v["total_empty_years"] for v in transitions_by_regime.values())

    print(f"  Total empty->forest: {total_e2f} / {total_empty} empty-cell-years")
    if total_empty > 0:
        print(f"  Rate: {total_e2f / total_empty:.6f}")

    for regime in ("death", "stable", "growth"):
        d = transitions_by_regime[regime]
        if d["total_empty_years"] > 0:
            rate = d["empty_to_forest"] / d["total_empty_years"]
            print(f"  {regime}: {d['empty_to_forest']} / {d['total_empty_years']} = {rate:.6f}")

    return {
        "total_empty_to_forest": total_e2f,
        "total_empty_cell_years": total_empty,
        "rate": total_e2f / max(1, total_empty),
        "by_regime": {r: dict(v) for r, v in transitions_by_regime.items()},
        "conclusion": "CONFIRMED_ZERO" if total_e2f == 0 else "FOUND_TRANSITIONS",
    }


def h2_expansion_radius(replays, regimes):
    """H2: How far do new settlements form from initial settlements?"""
    print("\n=== H2: SETTLEMENT EXPANSION RADIUS ===")

    distances_by_regime = defaultdict(list)

    for rn, seeds in replays.items():
        regime = regimes.get(rn, "unknown")
        for si, data in seeds.items():
            frames = data["frames"]
            h = len(frames[0]["grid"])
            w = len(frames[0]["grid"][0])

            # Initial settlement positions (year 0)
            initial_settle = set()
            for y in range(h):
                for x in range(w):
                    if cell_to_class(frames[0]["grid"][y][x]) in (1, 2):
                        initial_settle.add((y, x))

            # Final settlement positions (year 50)
            final_grid = frames[-1]["grid"]
            for y in range(h):
                for x in range(w):
                    if cell_to_class(final_grid[y][x]) in (1, 2):
                        if (y, x) not in initial_settle and initial_settle:
                            min_d = min(manhattan_distance(y, x, iy, ix)
                                        for iy, ix in initial_settle)
                            distances_by_regime[regime].append(min_d)

    for regime in ("death", "stable", "growth"):
        dists = distances_by_regime.get(regime, [])
        if dists:
            arr = np.array(dists)
            print(f"  {regime}: n={len(dists)}, min={arr.min()}, "
                f"median={np.median(arr):.1f}, p90={np.percentile(arr, 90):.1f}, "
                f"max={arr.max()}")
        else:
            print(f"  {regime}: no new settlements")

    return {
        regime: {
            "count": len(dists),
            "min": int(np.min(dists)) if dists else None,
            "median": float(np.median(dists)) if dists else None,
            "p90": float(np.percentile(dists, 90)) if dists else None,
            "max": int(np.max(dists)) if dists else None,
        }
        for regime, dists in distances_by_regime.items()
    }


def h3_mountain_adjacency(replays, regimes):
    """H3: Do mountains kill adjacent settlements?"""
    print("\n=== H3: MOUNTAIN ADJACENCY EFFECT ON SETTLEMENT SURVIVAL ===")

    survival_by_mtns = defaultdict(lambda: {"survived": 0, "died": 0})
    survival_by_regime_mtns = defaultdict(lambda: defaultdict(lambda: {"survived": 0, "died": 0}))

    for rn, seeds in replays.items():
        regime = regimes.get(rn, "unknown")
        for si, data in seeds.items():
            frames = data["frames"]
            grid_0 = frames[0]["grid"]
            grid_50 = frames[-1]["grid"]
            h, w = len(grid_0), len(grid_0[0])

            for y in range(h):
                for x in range(w):
                    if cell_to_class(grid_0[y][x]) not in (1, 2):
                        continue
                    mtns = count_mountain_neighbors(grid_0, y, x, h, w)
                    final_cls = cell_to_class(grid_50[y][x])
                    survived = final_cls in (1, 2)

                    key = min(mtns, 3)  # bucket 3+
                    if survived:
                        survival_by_mtns[key]["survived"] += 1
                        survival_by_regime_mtns[regime][key]["survived"] += 1
                    else:
                        survival_by_mtns[key]["died"] += 1
                        survival_by_regime_mtns[regime][key]["died"] += 1

    print("  Overall survival by mountain adjacency:")
    result = {}
    for mtns in sorted(survival_by_mtns.keys()):
        d = survival_by_mtns[mtns]
        total = d["survived"] + d["died"]
        rate = d["survived"] / max(1, total)
        label = f"{mtns}+" if mtns == 3 else str(mtns)
        print(f"    {label} mountains: {d['survived']}/{total} survived ({rate:.1%})")
        result[f"mtns_{label}"] = {"survived": d["survived"], "total": total, "rate": round(rate, 3)}

    print("  By regime:")
    regime_result = {}
    for regime in ("death", "stable", "growth"):
        regime_result[regime] = {}
        for mtns in sorted(survival_by_regime_mtns.get(regime, {}).keys()):
            d = survival_by_regime_mtns[regime][mtns]
            total = d["survived"] + d["died"]
            rate = d["survived"] / max(1, total)
            label = f"{mtns}+" if mtns == 3 else str(mtns)
            print(f"    {regime} / {label} mtns: {d['survived']}/{total} ({rate:.1%})")
            regime_result[regime][f"mtns_{label}"] = round(rate, 3)

    result["by_regime"] = regime_result
    return result


def h4_port_formation(replays, regimes):
    """H4: Port formation rules — always coastal? What triggers it?"""
    print("\n=== H4: PORT FORMATION RULES ===")

    coastal_ports = 0
    inland_ports = 0
    coastal_settle_became_port = 0
    coastal_settle_stayed = 0

    for rn, seeds in replays.items():
        for si, data in seeds.items():
            frames = data["frames"]
            h, w = len(frames[0]["grid"]), len(frames[0]["grid"][0])

            for yr in range(len(frames) - 1):
                grid_now = frames[yr]["grid"]
                grid_next = frames[yr + 1]["grid"]

                for y in range(h):
                    for x in range(w):
                        cls_now = cell_to_class(grid_now[y][x])
                        cls_next = cell_to_class(grid_next[y][x])

                        # New port formation
                        if cls_next == 2 and cls_now != 2:
                            if has_ocean_neighbor(grid_now, y, x, h, w):
                                coastal_ports += 1
                            else:
                                inland_ports += 1

                        # Coastal settlement tracking (year 0 only for clean signal)
                        if yr == 0 and cls_now == 1:
                            is_coastal = has_ocean_neighbor(grid_now, y, x, h, w)
                            if is_coastal:
                                if cell_to_class(frames[-1]["grid"][y][x]) == 2:
                                    coastal_settle_became_port += 1
                                else:
                                    coastal_settle_stayed += 1

    total_ports = coastal_ports + inland_ports
    print(f"  New port formations: {total_ports}")
    print(f"    Coastal (ocean-adjacent): {coastal_ports}")
    print(f"    Inland (no ocean): {inland_ports}")
    if total_ports > 0:
        print(f"    Coastal %: {coastal_ports / total_ports:.1%}")

    total_coastal = coastal_settle_became_port + coastal_settle_stayed
    if total_coastal > 0:
        print(f"  Coastal settlements at year 0: {total_coastal}")
        print(f"    Became port by year 50: {coastal_settle_became_port} ({coastal_settle_became_port / total_coastal:.1%})")

    return {
        "coastal_port_formations": coastal_ports,
        "inland_port_formations": inland_ports,
        "coastal_pct": coastal_ports / max(1, total_ports),
        "coastal_settle_to_port_rate": coastal_settle_became_port / max(1, total_coastal),
    }


def h5_ruin_lifecycle(replays, regimes):
    """H5: How long do ruins persist before changing?"""
    print("\n=== H5: RUIN LIFECYCLE ===")

    ruin_lifespans = []
    ruin_transitions = defaultdict(int)
    ruin_appearances = 0

    for rn, seeds in replays.items():
        for si, data in seeds.items():
            frames = data["frames"]
            h, w = len(frames[0]["grid"]), len(frames[0]["grid"][0])

            # Track each cell that becomes a ruin
            for y in range(h):
                for x in range(w):
                    in_ruin = False
                    ruin_start = 0

                    for yr in range(len(frames)):
                        cls = cell_to_class(frames[yr]["grid"][y][x])

                        if cls == 3 and not in_ruin:
                            in_ruin = True
                            ruin_start = yr
                            ruin_appearances += 1
                        elif cls != 3 and in_ruin:
                            lifespan = yr - ruin_start
                            ruin_lifespans.append(lifespan)
                            ruin_transitions[CLASS_NAMES[cls]] += 1
                            in_ruin = False

                    # Still a ruin at last frame
                    if in_ruin:
                        ruin_lifespans.append(len(frames) - 1 - ruin_start)
                        ruin_transitions["still_ruin_at_50"] += 1

    print(f"  Total ruin appearances: {ruin_appearances}")
    if ruin_lifespans:
        arr = np.array(ruin_lifespans)
        print(f"  Lifespan: mean={arr.mean():.1f} years, median={np.median(arr):.0f}, "
            f"min={arr.min()}, max={arr.max()}")
        print(f"  Transitions from ruin:")
        for dest, count in sorted(ruin_transitions.items(), key=lambda x: -x[1]):
            print(f"    -> {dest}: {count} ({count / len(ruin_lifespans):.1%})")
    else:
        print("  No ruins found in any replay!")

    return {
        "total_appearances": ruin_appearances,
        "lifespans": {
            "mean": float(np.mean(ruin_lifespans)) if ruin_lifespans else None,
            "median": float(np.median(ruin_lifespans)) if ruin_lifespans else None,
            "min": int(np.min(ruin_lifespans)) if ruin_lifespans else None,
            "max": int(np.max(ruin_lifespans)) if ruin_lifespans else None,
        },
        "transitions": dict(ruin_transitions),
    }


def h6_winter_detection(replays, regimes):
    """H6: Can year-10 settlement stats predict final regime?"""
    print("\n=== H6: WINTER DETECTION FROM YEAR-10 STATS ===")

    rows = []

    for rn, seeds in replays.items():
        regime = regimes.get(rn, "unknown")
        for si, data in seeds.items():
            frames = data["frames"]
            h, w = len(frames[0]["grid"]), len(frames[0]["grid"][0])

            # Count settlements at year 0, 10, 50
            yr_10 = min(10, len(frames) - 1)
            yr_50 = len(frames) - 1
            counts = {}
            for yr in (0, yr_10, yr_50):
                settle = 0
                for y in range(h):
                    for x in range(w):
                        if cell_to_class(frames[yr]["grid"][y][x]) in (1, 2):
                            settle += 1
                counts[yr] = settle

            # Settlement stats at year 10 (or last available frame)
            alive_settlements = [s for s in frames[yr_10].get("settlements", [])
                                 if s.get("alive", False)]
            avg_pop = np.mean([s["population"] for s in alive_settlements]) if alive_settlements else 0
            avg_food = np.mean([s["food"] for s in alive_settlements]) if alive_settlements else 0

            survival_y10 = counts[yr_10] / max(1, counts[0])

            rows.append({
                "round": rn, "seed": si, "regime": regime,
                "settle_y0": counts[0],
                "settle_y10": counts[yr_10],
                "settle_y50": counts[yr_50],
                "survival_y10": round(survival_y10, 3),
                "avg_pop_y10": round(avg_pop, 3),
                "avg_food_y10": round(avg_food, 3),
            })

    # Group by regime
    print("  Year-10 survival rate by regime:")
    regime_stats = defaultdict(list)
    for row in rows:
        regime_stats[row["regime"]].append(row["survival_y10"])

    thresholds = {}
    for regime in ("death", "stable", "growth"):
        vals = regime_stats.get(regime, [])
        if vals:
            arr = np.array(vals)
            print(f"    {regime}: mean={arr.mean():.3f}, min={arr.min():.3f}, max={arr.max():.3f}")
            thresholds[regime] = {"mean": round(float(arr.mean()), 3),
                                  "min": round(float(arr.min()), 3),
                                  "max": round(float(arr.max()), 3)}

    # Simple classifier: if year-10 survival < threshold => death
    print("\n  Year-10 population by regime:")
    pop_stats = defaultdict(list)
    food_stats = defaultdict(list)
    for row in rows:
        pop_stats[row["regime"]].append(row["avg_pop_y10"])
        food_stats[row["regime"]].append(row["avg_food_y10"])

    for regime in ("death", "stable", "growth"):
        pops = pop_stats.get(regime, [])
        foods = food_stats.get(regime, [])
        if pops:
            print(f"    {regime}: avg_pop={np.mean(pops):.3f}, avg_food={np.mean(foods):.3f}")

    return {
        "survival_y10_by_regime": thresholds,
        "pop_by_regime": {r: round(float(np.mean(v)), 3)
                          for r, v in pop_stats.items() if v},
        "food_by_regime": {r: round(float(np.mean(v)), 3)
                           for r, v in food_stats.items() if v},
        "detail": rows,
    }


def h7_faction_dynamics(replays, regimes):
    """H7: Do faction (owner_id) patterns predict outcomes?"""
    print("\n=== H7: FACTION DYNAMICS ===")

    rows = {}

    for rn, seeds in replays.items():
        regime = regimes.get(rn, "unknown")
        for si, data in seeds.items():
            frames = data["frames"]

            for yr in (0, 10, 25, 50):
                if yr >= len(frames):
                    continue
                settlements = frames[yr].get("settlements", [])
                alive = [s for s in settlements if s.get("alive", False)]
                owner_ids = set(s.get("owner_id", -1) for s in alive)

                rows[(rn, si, yr)] = {
                    "regime": regime,
                    "alive_settlements": len(alive),
                    "unique_factions": len(owner_ids),
                    "largest_faction": max(
                        (sum(1 for s in alive if s.get("owner_id") == oid) for oid in owner_ids),
                        default=0
                    ),
                }

    # Consolidation rate: factions at year 50 / factions at year 0
    print("  Faction consolidation by regime:")
    regime_consol = defaultdict(list)
    for rn, seeds in replays.items():
        regime = regimes.get(rn, "unknown")
        for si in seeds:
            y0 = rows.get((rn, si, 0))
            y50 = rows.get((rn, si, 50))
            if y0 and y50 and y0["unique_factions"] > 0:
                regime_consol[regime].append(y50["unique_factions"] / y0["unique_factions"])

    result = {}
    for regime in ("death", "stable", "growth"):
        vals = regime_consol.get(regime, [])
        if vals:
            arr = np.array(vals)
            print(f"    {regime}: faction ratio y50/y0 = {arr.mean():.3f} "
                f"(min={arr.min():.3f}, max={arr.max():.3f})")
            result[regime] = {"mean_ratio": round(float(arr.mean()), 3),
                              "min": round(float(arr.min()), 3),
                              "max": round(float(arr.max()), 3)}

    return result


def h8_predictability(replays, regimes):
    """H8: What makes rounds predictable vs chaotic?"""
    print("\n=== H8: PREDICTABLE vs CHAOTIC ROUNDS ===")

    round_stats = {}

    for rn, seeds in replays.items():
        regime = regimes.get(rn, "unknown")
        settle_counts_y50 = []

        for si, data in seeds.items():
            grid_50 = data["frames"][-1]["grid"]
            h, w = len(grid_50), len(grid_50[0])
            settle = sum(1 for y in range(h) for x in range(w)
                         if cell_to_class(grid_50[y][x]) in (1, 2))
            settle_counts_y50.append(settle)

        arr = np.array(settle_counts_y50)
        cv = arr.std() / max(arr.mean(), 1)  # coefficient of variation

        round_stats[rn] = {
            "regime": regime,
            "n_seeds": len(settle_counts_y50),
            "settle_y50_mean": round(float(arr.mean()), 1),
            "settle_y50_std": round(float(arr.std()), 1),
            "cv": round(float(cv), 3),
            "settle_y50_per_seed": [int(x) for x in settle_counts_y50],
        }

    print("  Settlement count variance across seeds (lower CV = more predictable):")
    for rn in sorted(round_stats.keys()):
        s = round_stats[rn]
        print(f"    R{rn} [{s['regime']:>6}]: mean={s['settle_y50_mean']:>6.1f}, "
            f"std={s['settle_y50_std']:>5.1f}, CV={s['cv']:.3f}  "
            f"seeds={s['settle_y50_per_seed']}")

    return round_stats


def build_transition_matrix(replays, regimes):
    """Bonus: full transition matrix per regime (year-over-year)."""
    print("\n=== BONUS: FULL TRANSITION MATRIX (year-over-year) ===")

    matrices = defaultdict(lambda: np.zeros((NUM_CLASSES, NUM_CLASSES), dtype=np.int64))
    totals = defaultdict(lambda: np.zeros(NUM_CLASSES, dtype=np.int64))

    for rn, seeds in replays.items():
        regime = regimes.get(rn, "unknown")
        for si, data in seeds.items():
            frames = data["frames"]
            h, w = len(frames[0]["grid"]), len(frames[0]["grid"][0])

            for yr in range(len(frames) - 1):
                grid_now = frames[yr]["grid"]
                grid_next = frames[yr + 1]["grid"]

                for y in range(h):
                    for x in range(w):
                        raw_now = int(grid_now[y][x])
                        if raw_now in OCEAN_RAW:
                            continue
                        cls_now = cell_to_class(raw_now)
                        cls_next = cell_to_class(grid_next[y][x])
                        matrices[regime][cls_now, cls_next] += 1
                        totals[regime][cls_now] += 1

    result = {}
    for regime in ("death", "stable", "growth"):
        mat = matrices.get(regime)
        tot = totals.get(regime)
        if mat is None:
            continue

        print(f"\n  {regime.upper()} regime transition rates:")
        print(f"  {'From/To':>12} " + " ".join(f"{c:>8}" for c in CLASS_NAMES))
        regime_rates = {}
        for from_cls in range(NUM_CLASSES):
            if tot[from_cls] == 0:
                continue
            rates = mat[from_cls] / tot[from_cls]
            print(f"  {CLASS_NAMES[from_cls]:>12} " +
                " ".join(f"{r:>8.4f}" for r in rates))
            regime_rates[CLASS_NAMES[from_cls]] = {
                CLASS_NAMES[to_cls]: round(float(rates[to_cls]), 6)
                for to_cls in range(NUM_CLASSES)
            }
        result[regime] = regime_rates

    return result


def main():
    parser = argparse.ArgumentParser(description="Deep analysis of Astar Island replays")
    parser.add_argument("--output", default=str(DATA_DIR / "deep_analysis_results.json"))
    args = parser.parse_args()

    print("Loading replays...")
    replays = load_all_replays()
    total_files = sum(len(seeds) for seeds in replays.values())
    print(f"  {total_files} replay files across {len(replays)} rounds")

    print("Loading ground truth for regime classification...")
    rounds_data = load_cached_rounds()
    regimes = get_regime_map(rounds_data)
    print(f"  Regimes: " + ", ".join(f"R{rn}={r}" for rn, r in sorted(regimes.items())))

    results = {}

    results["h1_empty_to_forest"] = h1_empty_to_forest(replays, regimes)
    results["h2_expansion_radius"] = h2_expansion_radius(replays, regimes)
    results["h3_mountain_adjacency"] = h3_mountain_adjacency(replays, regimes)
    results["h4_port_formation"] = h4_port_formation(replays, regimes)
    results["h5_ruin_lifecycle"] = h5_ruin_lifecycle(replays, regimes)
    results["h6_winter_detection"] = h6_winter_detection(replays, regimes)
    results["h7_faction_dynamics"] = h7_faction_dynamics(replays, regimes)
    results["h8_predictability"] = h8_predictability(replays, regimes)
    results["transition_matrix"] = build_transition_matrix(replays, regimes)

    # Save results (exclude large detail arrays for JSON)
    save_results = {}
    for key, val in results.items():
        if key == "h6_winter_detection":
            save_results[key] = {k: v for k, v in val.items() if k != "detail"}
        else:
            save_results[key] = val

    out_path = Path(args.output)
    with open(out_path, "w") as f:
        json.dump(save_results, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")

    # Print actionable summary
    print("\n" + "=" * 60)
    print("ACTIONABLE FINDINGS SUMMARY")
    print("=" * 60)

    h1 = results["h1_empty_to_forest"]
    if h1["conclusion"] == "CONFIRMED_ZERO":
        print("H1: HARD CONSTRAINT: Empty NEVER becomes Forest. Force P(forest|empty) = 0.01")
    else:
        print(f"H1: Empty->Forest rate = {h1['rate']:.6f}. "
            f"{'Negligible' if h1['rate'] < 0.001 else 'Significant'}")

    h5 = results["h5_ruin_lifecycle"]
    if h5["total_appearances"] > 0:
        print(f"H5: Ruins exist ({h5['total_appearances']} appearances, "
            f"avg {h5['lifespans']['mean']:.1f} yr lifespan) but are transitional.")
    else:
        print("H5: Ruins NEVER appear in replays. Force P(ruin) = 0.01 always.")

    h4 = results["h4_port_formation"]
    if h4["inland_port_formations"] == 0:
        print("H4: HARD CONSTRAINT: Ports ONLY form on coastal cells. Force P(port) = 0.01 for inland.")
    else:
        print(f"H4: {h4['inland_port_formations']} inland ports found (unexpected).")


if __name__ == "__main__":
    main()
