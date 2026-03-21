#!/usr/bin/env python3
"""
Observation Intelligence: Correlation Analysis (Phase 1 Gate).

Tests whether observation-derived features (year-50 terrain counts)
are valid proxies for replay-derived features (year-10/25 stats).

Uses replay year-50 frames as simulated observations (pessimistic:
real observations are Monte Carlo stacked and closer to ground truth).

Decision gate:
  R2 >= 0.5: APPROVED (use as proxy in production)
  R2 0.3-0.5: EXPERIMENTAL (backtest only)
  R2 < 0.3: REJECTED (keep 1.0 default)

Usage:
  python observation_analysis.py
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from backtest import load_cached_rounds, TERRAIN_TO_CLASS, STATIC_TERRAIN
from regime_model import classify_round

DATA_DIR = Path(__file__).parent / "data"
REPLAY_DIR = DATA_DIR / "replays"
OCEAN_RAW = {10, 11}


def compute_obs_features_from_replay(replay_data, initial_grid, h, w):
    """Compute observation-like features from replay year-50 frame.

    Simulates what we'd compute from viewport observations at prediction time.
    """
    frames = replay_data["frames"]
    if len(frames) != 51:
        return None
    grid_50 = frames[50]["grid"]

    # Count terrain classes at year 0 and year 50
    init_settle, init_forest, init_ports = 0, 0, 0
    obs_settle, obs_forest, obs_ports, obs_ruin = 0, 0, 0, 0

    for y in range(h):
        for x in range(w):
            raw_0 = int(initial_grid[y][x])
            if raw_0 in OCEAN_RAW or raw_0 in STATIC_TERRAIN:
                continue
            cls_0 = TERRAIN_TO_CLASS.get(raw_0, 0)
            cls_50 = TERRAIN_TO_CLASS.get(int(grid_50[y][x]), 0)

            if cls_0 in (1, 2):
                init_settle += 1
            if cls_0 == 2:
                init_ports += 1
            if cls_0 == 4:
                init_forest += 1

            if cls_50 in (1, 2):
                obs_settle += 1
            if cls_50 == 2:
                obs_ports += 1
            if cls_50 == 4:
                obs_forest += 1
            if cls_50 == 3:
                obs_ruin += 1

    return {
        "obs_settle_growth": obs_settle / max(init_settle, 1),
        "obs_forest_ratio": obs_forest / max(init_forest, 1),
        "obs_port_growth": obs_ports / max(init_ports, 1),
        "obs_ruin_count": obs_ruin,
        "init_settle": init_settle,
        "obs_settle": obs_settle,
    }


def compute_replay_features(replay_data):
    """Compute the actual replay-derived features (what the model trains on)."""
    frames = replay_data["frames"]

    def alive_stats(frame):
        alive = [s for s in frame.get("settlements", []) if s.get("alive", False)]
        n = len(alive)
        if n == 0:
            return {"n": 0, "avg_w": 0.0, "avg_p": 0.0, "avg_f": 0.0, "factions": 0}
        return {
            "n": n,
            "avg_w": sum(s.get("wealth", 0.0) for s in alive) / n,
            "avg_p": sum(s.get("population", 0.0) for s in alive) / n,
            "avg_f": sum(s.get("food", 0.0) for s in alive) / n,
            "factions": len(set(s.get("owner_id", -1) for s in alive)),
        }

    if not frames or len(frames) < 26:
        return None
    y0 = alive_stats(frames[0])
    y10 = alive_stats(frames[10])
    y25 = alive_stats(frames[25])

    return {
        "settle_growth_y10": y10["n"] / max(y0["n"], 1),
        "settle_growth_y25": y25["n"] / max(y0["n"], 1),
        "wealth_decay_y10": y10["avg_w"] / max(y0["avg_w"], 0.001),
        "wealth_decay_y25": y25["avg_w"] / max(y0["avg_w"], 0.001),
        "faction_consol_y10": y10["factions"] / max(y0["factions"], 1),
        "pop_trend_y10": y10["avg_p"] / max(y0["avg_p"], 0.001),
        "food_trend_y10": y10["avg_f"] / max(y0["avg_f"], 0.001),
    }


def pearson_r2(x, y):
    """Compute Pearson R-squared."""
    x, y = np.array(x), np.array(y)
    if len(x) < 3 or x.std() == 0 or y.std() == 0:
        return 0.0
    r = np.corrcoef(x, y)[0, 1]
    return r ** 2


def main():
    print("Loading data...")
    rounds_data = load_cached_rounds()
    print(f"  {len(rounds_data)} rounds")

    # Collect paired data: obs-derived vs replay-derived features
    rows = []
    for rd in rounds_data:
        rn = rd["round_number"]
        if not rd.get("seeds"):
            continue
        regime, _ = classify_round(rd)
        h, w = rd["map_height"], rd["map_width"]

        for si in range(5):
            replay_path = REPLAY_DIR / f"r{rn}_seed{si}.json"
            if not replay_path.exists():
                continue
            with open(replay_path) as f:
                replay_data = json.load(f)

            ig = rd["initial_states"][si]["grid"]
            obs_feats = compute_obs_features_from_replay(replay_data, ig, h, w)
            replay_feats = compute_replay_features(replay_data)
            if obs_feats is None or replay_feats is None:
                continue

            rows.append({
                "round": rn, "seed": si, "regime": regime,
                **obs_feats,
                **{f"rep_{k}": v for k, v in replay_feats.items()},
            })

    print(f"  {len(rows)} data points (round/seed pairs)")

    # Compute correlations
    pairs = [
        ("obs_settle_growth", "rep_settle_growth_y25"),
        ("obs_settle_growth", "rep_settle_growth_y10"),
        ("obs_settle_growth", "rep_wealth_decay_y10"),
        ("obs_settle_growth", "rep_wealth_decay_y25"),
        ("obs_settle_growth", "rep_faction_consol_y10"),
        ("obs_settle_growth", "rep_pop_trend_y10"),
        ("obs_settle_growth", "rep_food_trend_y10"),
        ("obs_forest_ratio", "rep_settle_growth_y25"),
    ]

    print("\n=== CORRELATION ANALYSIS ===")
    print(f"{'Pair':<50} {'R2':>6} {'Decision':>12}")
    print("-" * 72)

    results = {}
    for obs_key, rep_key in pairs:
        x = [r[obs_key] for r in rows]
        y = [r[rep_key] for r in rows]
        r2 = pearson_r2(x, y)

        if r2 >= 0.5:
            decision = "APPROVED"
        elif r2 >= 0.3:
            decision = "EXPERIMENTAL"
        else:
            decision = "REJECTED"

        label = f"{obs_key} vs {rep_key.removeprefix('rep_')}"
        print(f"  {label:<48} {r2:>5.3f} {decision:>12}")
        results[label] = {"r2": round(float(r2), 4), "decision": decision}

    # Regime classification analysis
    print("\n=== REGIME CLASSIFICATION FROM OBS_SETTLE_GROWTH ===")

    # Find optimal thresholds
    obs_growths = [(r["obs_settle_growth"], r["regime"]) for r in rows]
    print(f"\n  obs_settle_growth by regime:")
    for regime in ("death", "stable", "growth"):
        vals = [g for g, r in obs_growths if r == regime]
        if vals:
            arr = np.array(vals)
            print(f"    {regime}: min={arr.min():.2f} mean={arr.mean():.2f} "
                  f"max={arr.max():.2f} std={arr.std():.2f}")

    # Grid search for optimal thresholds
    best_acc, best_thresholds = 0, (0.3, 2.0)
    for death_t in np.arange(0.1, 1.5, 0.1):
        for growth_t in np.arange(1.0, 5.0, 0.2):
            correct = 0
            for g, r in obs_growths:
                if g < death_t:
                    pred = "death"
                elif g > growth_t:
                    pred = "growth"
                else:
                    pred = "stable"
                if pred == r:
                    correct += 1
            acc = correct / len(obs_growths)
            if acc > best_acc:
                best_acc = acc
                best_thresholds = (death_t, growth_t)

    print(f"\n  Best thresholds: death < {best_thresholds[0]:.1f}, growth > {best_thresholds[1]:.1f}")
    print(f"  Accuracy: {best_acc:.1%} ({int(best_acc * len(obs_growths))}/{len(obs_growths)})")

    # Training distribution bounds for OOD guard
    print("\n=== TRAINING DISTRIBUTION BOUNDS (for OOD fallback) ===")
    for key in ["rep_settle_growth_y25", "rep_settle_growth_y10", "rep_wealth_decay_y10"]:
        vals = [r[key] for r in rows]
        arr = np.array(vals)
        print(f"  {key.replace('rep_', '')}: min={arr.min():.3f} max={arr.max():.3f} "
              f"mean={arr.mean():.3f}")

    # Save results
    out_path = DATA_DIR / "observation_analysis.json"
    save_data = {
        "correlations": results,
        "regime_thresholds": {
            "feature": "obs_settle_growth",
            "death_below": round(float(best_thresholds[0]), 1),
            "growth_above": round(float(best_thresholds[1]), 1),
            "accuracy": round(float(best_acc), 3),
        },
        "n_data_points": len(rows),
    }
    with open(out_path, "w") as f:
        json.dump(save_data, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
