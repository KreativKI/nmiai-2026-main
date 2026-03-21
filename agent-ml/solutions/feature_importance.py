#!/usr/bin/env python3
"""
Feature Importance Analysis for Astar Island 51-feature model.

Trains LightGBM on all data, extracts feature importance (gain-based),
and cross-references with feature availability at prediction time.

Usage:
  python feature_importance.py
"""

import json
from pathlib import Path

import numpy as np
import lightgbm as lgb

import sys
sys.path.insert(0, str(Path(__file__).parent))
from backtest import load_cached_rounds, NUM_CLASSES, CLASS_NAMES
from build_dataset import build_master_dataset, FEATURE_NAMES

DATA_DIR = Path(__file__).parent / "data"

# Features that require replay data (not available for new active rounds)
REPLAY_ONLY_FEATURES = {
    "food_y10", "pop_y10", "wealth_y10", "defense_y10",
    "terrain_y10", "is_settle_y10", "n_settle_y10", "survived_y10",
    "food_y25", "pop_y25", "wealth_y25", "defense_y25",
    "terrain_y25", "is_settle_y25", "n_settle_y25", "survived_y25",
    "settle_growth_y10", "settle_growth_y25",
    "wealth_decay_y10", "wealth_decay_y25",
    "faction_consol_y10", "pop_trend_y10", "food_trend_y10",
    "total_wealth_y0", "total_food_y0", "avg_defense_y0", "total_factions_y0",
}

# Features always available (from initial grid or computable)
ALWAYS_AVAILABLE = set(FEATURE_NAMES) - REPLAY_ONLY_FEATURES


def main():
    print("Loading data...")
    rounds_data = load_cached_rounds()
    X, Y, _ = build_master_dataset(rounds_data)
    print(f"  {X.shape[0]} rows, {X.shape[1]} features")

    # Train 6 regressors (matching production pipeline)
    print("\nTraining models...")
    importance_per_class = np.zeros((NUM_CLASSES, len(FEATURE_NAMES)))

    for cls in range(NUM_CLASSES):
        m = lgb.LGBMRegressor(
            n_estimators=50, num_leaves=31, learning_rate=0.05,
            min_child_samples=20, subsample=0.8, colsample_bytree=0.8,
            verbose=-1,
        )
        m.fit(X, Y[:, cls])
        importance_per_class[cls] = m.feature_importances_

    # Average importance across all 6 classes
    avg_importance = importance_per_class.mean(axis=0)
    total = avg_importance.sum()
    pct = avg_importance / total * 100

    # Sort by importance
    order = np.argsort(-avg_importance)

    print("\n=== FEATURE IMPORTANCE (averaged across 6 terrain classes) ===")
    print(f"{'Rank':>4} {'Feature':<25} {'Importance':>10} {'%':>6} {'Available':>10}")
    print("-" * 60)

    results = []
    for rank, idx in enumerate(order):
        name = FEATURE_NAMES[idx]
        avail = "always" if name in ALWAYS_AVAILABLE else "replay"
        print(f"{rank+1:>4} {name:<25} {avg_importance[idx]:>10.1f} {pct[idx]:>5.1f}% {avail:>10}")
        results.append({
            "rank": rank + 1,
            "feature": name,
            "importance": round(float(avg_importance[idx]), 1),
            "pct": round(float(pct[idx]), 2),
            "available": avail,
        })

    # Summary stats
    replay_imp = sum(pct[i] for i, n in enumerate(FEATURE_NAMES) if n in REPLAY_ONLY_FEATURES)
    always_imp = sum(pct[i] for i, n in enumerate(FEATURE_NAMES) if n in ALWAYS_AVAILABLE)

    print(f"\n=== SUMMARY ===")
    print(f"  Always-available features: {always_imp:.1f}% of total importance")
    print(f"  Replay-only features: {replay_imp:.1f}% of total importance")
    print(f"  Total features: {len(FEATURE_NAMES)}")
    print(f"  Always-available: {len(ALWAYS_AVAILABLE)}")
    print(f"  Replay-only: {len(REPLAY_ONLY_FEATURES)}")

    # Per-class breakdown for top features
    print(f"\n=== TOP 10 PER CLASS ===")
    for cls in range(NUM_CLASSES):
        cls_order = np.argsort(-importance_per_class[cls])[:5]
        top = [FEATURE_NAMES[i] for i in cls_order]
        print(f"  {CLASS_NAMES[cls]:>10}: {', '.join(top)}")

    # Zero-importance features
    zero_feats = [FEATURE_NAMES[i] for i in range(len(FEATURE_NAMES)) if avg_importance[i] == 0]
    if zero_feats:
        print(f"\n=== ZERO IMPORTANCE (candidates for removal) ===")
        for f in zero_feats:
            print(f"  - {f}")

    # New features analysis
    new_features = [
        "wealth_y10", "defense_y10",
        "food_y25", "pop_y25", "wealth_y25", "defense_y25",
        "survived_y10", "survived_y25",
        "settle_growth_y10", "settle_growth_y25",
        "wealth_decay_y10", "wealth_decay_y25",
        "faction_consol_y10", "pop_trend_y10", "food_trend_y10",
        "total_wealth_y0", "total_food_y0", "avg_defense_y0", "total_factions_y0",
    ]
    print(f"\n=== NEW FEATURES (added this session) ===")
    for name in new_features:
        idx = FEATURE_NAMES.index(name)
        rank_pos = list(order).index(idx) + 1
        avail = "always" if name in ALWAYS_AVAILABLE else "replay"
        print(f"  {name:<25} rank={rank_pos:>2} imp={avg_importance[idx]:>6.1f} ({pct[idx]:.1f}%) [{avail}]")

    # Save
    out_path = DATA_DIR / "feature_importance.json"
    with open(out_path, "w") as f:
        json.dump({
            "features": results,
            "replay_importance_pct": round(float(replay_imp), 1),
            "always_importance_pct": round(float(always_imp), 1),
        }, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
