#!/usr/bin/env python3
"""
Tile Value Scorer for Astar Island.

Computes per-cell "value" scores across all cached rounds to identify which
cells (positions and terrain types) matter most for prediction accuracy.

Think of it like chess piece values: each cell on the 40x40 grid has a
different "value" in terms of how much it affects our prediction score.

For each cell, we compute:
  - Entropy contribution: How uncertain is the ground truth? (high entropy = high weight in scoring)
  - Error contribution: How wrong is our model? (high KL = high room for improvement)
  - Combined value = entropy * KL divergence (the actual scoring weight)

This tells us: "if you could only observe N cells, which N would improve
your score the most?"

Usage:
  python tile_value.py --cached-only
"""

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    load_cached_rounds, score_prediction, entropy, kl_divergence,
    TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, CLASS_NAMES, PROB_FLOOR,
)
from churn import NeighborhoodModelV2


DATA_DIR = Path(__file__).parent / "data"


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def compute_tile_values(rounds_data):
    """
    For each round (leave-one-out), for each seed:
      - Train NeighborhoodModelV2 on all other rounds
      - Predict the held-out round
      - Compute per-cell entropy, KL divergence, and combined value
      - Accumulate into 40x40 value maps

    Returns aggregated per-cell and per-terrain-type statistics.
    """
    n_rounds = len(rounds_data)
    h, w = 40, 40

    # Accumulators across all rounds and seeds
    all_entropy = np.zeros((h, w))
    all_kl = np.zeros((h, w))
    all_value = np.zeros((h, w))  # entropy * KL (the scoring contribution)
    all_count = np.zeros((h, w))  # how many (round, seed) pairs contributed

    # Per-terrain-type accumulators
    terrain_entropy = {}   # initial terrain class -> list of per-cell entropies
    terrain_kl = {}        # initial terrain class -> list of per-cell KLs
    terrain_value = {}     # initial terrain class -> list of per-cell values

    # Per-round results for reporting
    round_results = []

    for rd in rounds_data:
        rn = rd["round_number"]
        if not rd.get("seeds"):
            continue

        # Train model on all OTHER rounds (leave-one-out)
        model = NeighborhoodModelV2()
        for other_rd in rounds_data:
            if other_rd["round_number"] != rn:
                model.add_training_data(other_rd)
        model.finalize()

        round_entropy = np.zeros((h, w))
        round_kl = np.zeros((h, w))
        round_value = np.zeros((h, w))
        round_seed_count = 0

        for si_str, seed_data in rd["seeds"].items():
            si = int(si_str)
            ig = rd["initial_states"][si]["grid"]
            gt = np.array(seed_data["ground_truth"])

            # Model prediction (no observations, pure model)
            pred = model.predict_grid(rd, si)

            for y in range(h):
                for x in range(w):
                    ent = entropy(gt[y, x])
                    if ent < 1e-8:
                        # Deterministic cell: no scoring weight, skip
                        continue
                    kl = kl_divergence(gt[y, x], pred[y, x])

                    cell_value = ent * kl  # This is the actual scoring penalty

                    round_entropy[y, x] += ent
                    round_kl[y, x] += kl
                    round_value[y, x] += cell_value

                    # Per-terrain tracking
                    terrain_cls = TERRAIN_TO_CLASS.get(int(ig[y][x]), 0)
                    terrain_name = CLASS_NAMES[terrain_cls]
                    if terrain_name not in terrain_entropy:
                        terrain_entropy[terrain_name] = []
                        terrain_kl[terrain_name] = []
                        terrain_value[terrain_name] = []
                    terrain_entropy[terrain_name].append(ent)
                    terrain_kl[terrain_name].append(kl)
                    terrain_value[terrain_name].append(cell_value)

            round_seed_count += 1

        # Average across seeds for this round
        if round_seed_count > 0:
            round_entropy /= round_seed_count
            round_kl /= round_seed_count
            round_value /= round_seed_count

        all_entropy += round_entropy
        all_kl += round_kl
        all_value += round_value
        all_count += (round_entropy > 0).astype(float)

        # Per-round summary
        total_value = round_value.sum()
        nonzero = (round_value > 0).sum()
        round_results.append({
            "round": rn,
            "total_value": total_value,
            "nonzero_cells": int(nonzero),
            "avg_value": float(total_value / max(nonzero, 1)),
            "max_value": float(round_value.max()),
        })

    # Average across rounds
    mask = all_count > 0
    avg_entropy = np.where(mask, all_entropy / all_count, 0)
    avg_kl = np.where(mask, all_kl / all_count, 0)
    avg_value = np.where(mask, all_value / all_count, 0)

    return {
        "avg_entropy": avg_entropy,
        "avg_kl": avg_kl,
        "avg_value": avg_value,
        "terrain_entropy": terrain_entropy,
        "terrain_kl": terrain_kl,
        "terrain_value": terrain_value,
        "round_results": round_results,
        "n_rounds": n_rounds,
    }


def print_results(results):
    """Print tile value analysis results."""
    avg_value = results["avg_value"]
    avg_entropy = results["avg_entropy"]
    avg_kl = results["avg_kl"]
    n_rounds = results["n_rounds"]

    print(f"\n{'='*70}")
    print(f"  TILE VALUE ANALYSIS ({n_rounds} rounds, leave-one-out)")
    print(f"{'='*70}")

    # ── Per-round summary ──
    print(f"\n--- Per-Round Summary ---")
    print(f"  {'Round':>5}  {'Total Value':>12}  {'Nonzero Cells':>14}  {'Avg Value':>10}  {'Max Value':>10}")
    print(f"  {'-'*5}  {'-'*12}  {'-'*14}  {'-'*10}  {'-'*10}")
    for rr in results["round_results"]:
        print(f"  {rr['round']:>5}  {rr['total_value']:>12.3f}  {rr['nonzero_cells']:>14}  "
              f"{rr['avg_value']:>10.5f}  {rr['max_value']:>10.5f}")

    # ── Per-terrain-type breakdown ──
    print(f"\n--- Per Terrain Type (Initial State) ---")
    print(f"  Which terrain types are most worth observing?\n")
    print(f"  {'Terrain':<12}  {'Count':>7}  {'Avg Entropy':>12}  {'Avg KL':>8}  "
          f"{'Avg Value':>10}  {'Total Value':>12}  {'Value %':>8}")
    print(f"  {'-'*12}  {'-'*7}  {'-'*12}  {'-'*8}  {'-'*10}  {'-'*12}  {'-'*8}")

    terrain_stats = {}
    grand_total_value = 0
    for name in CLASS_NAMES:
        if name in results["terrain_value"] and len(results["terrain_value"][name]) > 0:
            vals = results["terrain_value"][name]
            ents = results["terrain_entropy"][name]
            kls = results["terrain_kl"][name]
            total_v = sum(vals)
            grand_total_value += total_v
            terrain_stats[name] = {
                "count": len(vals),
                "avg_entropy": np.mean(ents),
                "avg_kl": np.mean(kls),
                "avg_value": np.mean(vals),
                "total_value": total_v,
            }

    # Sort by total value descending
    sorted_terrain = sorted(terrain_stats.items(), key=lambda x: -x[1]["total_value"])
    for name, s in sorted_terrain:
        pct = 100.0 * s["total_value"] / grand_total_value if grand_total_value > 0 else 0
        print(f"  {name:<12}  {s['count']:>7}  {s['avg_entropy']:>12.4f}  "
              f"{s['avg_kl']:>8.4f}  {s['avg_value']:>10.5f}  "
              f"{s['total_value']:>12.3f}  {pct:>7.1f}%")

    # ── Top-N most valuable cell positions ──
    print(f"\n--- Top 30 Most Valuable Cell Positions ---")
    print(f"  (averaged across all rounds and seeds)\n")
    print(f"  {'Rank':>4}  {'(y, x)':>8}  {'Avg Value':>10}  {'Avg Entropy':>12}  {'Avg KL':>8}")
    print(f"  {'-'*4}  {'-'*8}  {'-'*10}  {'-'*12}  {'-'*8}")

    # Flatten and sort
    h, w = avg_value.shape
    cell_list = []
    for y in range(h):
        for x in range(w):
            if avg_value[y, x] > 0:
                cell_list.append((y, x, avg_value[y, x], avg_entropy[y, x], avg_kl[y, x]))

    cell_list.sort(key=lambda c: -c[2])
    for rank, (y, x, val, ent, kl) in enumerate(cell_list[:30], 1):
        print(f"  {rank:>4}  ({y:>2},{x:>2})  {val:>10.5f}  {ent:>12.4f}  {kl:>8.4f}")

    # ── Value heatmap: row-by-row summary ──
    print(f"\n--- Value Heatmap (row averages) ---")
    print(f"  Row  {'Avg Value':>10}  {'Max Value':>10}  {'Nonzero':>8}  Bar")
    print(f"  {'-'*3}  {'-'*10}  {'-'*10}  {'-'*8}  {'-'*40}")
    max_row_avg = 0
    row_avgs = []
    for y in range(h):
        row_vals = avg_value[y, :]
        nonzero = (row_vals > 0).sum()
        row_avg = row_vals.mean()
        row_max = row_vals.max()
        row_avgs.append(row_avg)
        max_row_avg = max(max_row_avg, row_avg)

    for y in range(h):
        row_vals = avg_value[y, :]
        nonzero = (row_vals > 0).sum()
        row_avg = row_avgs[y]
        row_max = row_vals.max()
        bar_len = int(40 * row_avg / max_row_avg) if max_row_avg > 0 else 0
        bar = "#" * bar_len
        print(f"  {y:>3}  {row_avg:>10.5f}  {row_max:>10.5f}  {nonzero:>8}  {bar}")

    # ── Summary statistics ──
    nonzero_values = avg_value[avg_value > 0]
    print(f"\n--- Summary ---")
    print(f"  Total cells:             {h * w}")
    print(f"  Cells with value > 0:    {len(nonzero_values)}")
    print(f"  Cells with value = 0:    {h * w - len(nonzero_values)} (deterministic/static)")
    if len(nonzero_values) > 0:
        print(f"  Mean value (nonzero):    {nonzero_values.mean():.5f}")
        print(f"  Median value (nonzero):  {np.median(nonzero_values):.5f}")
        print(f"  Std value (nonzero):     {nonzero_values.std():.5f}")
        print(f"  Max value:               {nonzero_values.max():.5f}")
        p90 = np.percentile(nonzero_values, 90)
        p95 = np.percentile(nonzero_values, 95)
        p99 = np.percentile(nonzero_values, 99)
        print(f"  P90 value:               {p90:.5f}")
        print(f"  P95 value:               {p95:.5f}")
        print(f"  P99 value:               {p99:.5f}")

        # How much score is concentrated in top N cells?
        sorted_vals = np.sort(nonzero_values)[::-1]
        total = sorted_vals.sum()
        for topn in [10, 25, 50, 100, 200]:
            if topn <= len(sorted_vals):
                topn_sum = sorted_vals[:topn].sum()
                pct = 100.0 * topn_sum / total
                print(f"  Top {topn:>3} cells contain:    {pct:.1f}% of total value")

    # ── Observation strategy recommendations ──
    print(f"\n--- Observation Strategy Recommendations ---")
    print(f"  Based on value analysis:\n")

    if terrain_stats:
        best_terrain = sorted_terrain[0][0]
        print(f"  A. Most valuable terrain to observe: {best_terrain}")
        print(f"     (accounts for {sorted_terrain[0][1]['total_value']/grand_total_value*100:.1f}% "
              f"of total scoring weight)")

        if len(sorted_terrain) > 1:
            second = sorted_terrain[1]
            print(f"  B. Second most valuable: {second[0]} "
                  f"({second[1]['total_value']/grand_total_value*100:.1f}%)")

    if len(cell_list) >= 50:
        top50_ys = [c[0] for c in cell_list[:50]]
        top50_xs = [c[1] for c in cell_list[:50]]
        print(f"\n  C. Top-50 valuable cells cluster around:")
        print(f"     Y range: {min(top50_ys)}-{max(top50_ys)} "
              f"(center ~{np.mean(top50_ys):.0f})")
        print(f"     X range: {min(top50_xs)}-{max(top50_xs)} "
              f"(center ~{np.mean(top50_xs):.0f})")

    # ── Save value map data ──
    output_path = DATA_DIR / "tile_value_map.json"
    export = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "n_rounds": n_rounds,
        "avg_value": avg_value.tolist(),
        "avg_entropy": avg_entropy.tolist(),
        "avg_kl": avg_kl.tolist(),
        "terrain_stats": {
            name: {
                "count": s["count"],
                "avg_entropy": float(s["avg_entropy"]),
                "avg_kl": float(s["avg_kl"]),
                "avg_value": float(s["avg_value"]),
                "total_value": float(s["total_value"]),
            }
            for name, s in terrain_stats.items()
        },
        "top_50_cells": [
            {"y": int(c[0]), "x": int(c[1]), "value": float(c[2]),
             "entropy": float(c[3]), "kl": float(c[4])}
            for c in cell_list[:50]
        ],
    }
    output_path.write_text(json.dumps(export, indent=2))
    print(f"\n  Value map data saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Tile Value Scorer")
    parser.add_argument("--cached-only", action="store_true",
                        help="Use cached ground truth only (no API calls)")
    args = parser.parse_args()

    if not args.cached_only:
        log("This script only works with cached data. Use --cached-only.")
        return

    rounds_data = load_cached_rounds()
    if not rounds_data:
        log("No cached data found. Run backtest.py --cache first.")
        return

    log(f"Loaded {len(rounds_data)} cached rounds: "
        f"{[rd['round_number'] for rd in rounds_data]}")

    results = compute_tile_values(rounds_data)
    print_results(results)


if __name__ == "__main__":
    main()
