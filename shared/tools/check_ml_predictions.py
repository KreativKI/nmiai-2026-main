#!/usr/bin/env python3
"""
NM i AI 2026 — ML Prediction Tensor Validator (shared/tools/check_ml_predictions.py)

Validates Astar Island prediction tensor before submission.
Checks: shape (40x40x6), probability floors (>0), normalization (sum to 1), no NaN/inf.

Usage:
    python3 shared/tools/check_ml_predictions.py predictions.json
    python3 shared/tools/check_ml_predictions.py predictions.json --json
"""

import argparse
import json
import math
import sys
from pathlib import Path

GRID_W = 40
GRID_H = 40
NUM_CLASSES = 6
PROB_FLOOR = 0.01  # Competition recommendation: floor at 0.01
NORM_TOLERANCE = 1e-4  # Probabilities must sum to 1.0 within this tolerance


def validate_predictions(data: list) -> dict:
    """Validate a list of seed predictions. Each is a 40x40x6 tensor."""
    result = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "seed_count": len(data),
        "seeds": [],
    }

    for seed_idx, tensor in enumerate(data):
        seed_result = {
            "seed": seed_idx,
            "valid": True,
            "shape": None,
            "min_prob": 1.0,
            "max_prob": 0.0,
            "zero_count": 0,
            "nan_count": 0,
            "norm_errors": 0,
        }

        if not isinstance(tensor, list):
            seed_result["valid"] = False
            result["errors"].append(f"Seed {seed_idx}: not a list")
            result["seeds"].append(seed_result)
            continue

        h = len(tensor)
        if h != GRID_H:
            seed_result["valid"] = False
            result["errors"].append(f"Seed {seed_idx}: height={h}, expected {GRID_H}")

        for y, row in enumerate(tensor):
            if not isinstance(row, list):
                seed_result["valid"] = False
                result["errors"].append(f"Seed {seed_idx}: row {y} not a list")
                continue

            w = len(row)
            if w != GRID_W:
                seed_result["valid"] = False
                result["errors"].append(f"Seed {seed_idx}: row {y} width={w}, expected {GRID_W}")
                continue

            for x, probs in enumerate(row):
                if not isinstance(probs, list) or len(probs) != NUM_CLASSES:
                    seed_result["valid"] = False
                    result["errors"].append(f"Seed {seed_idx}: cell ({x},{y}) has {len(probs) if isinstance(probs, list) else 'non-list'} classes, expected {NUM_CLASSES}")
                    continue

                total = 0.0
                for p in probs:
                    if not isinstance(p, (int, float)):
                        continue
                    if math.isnan(p) or math.isinf(p):
                        seed_result["nan_count"] += 1
                        continue
                    total += p
                    if p <= 0.0:
                        seed_result["zero_count"] += 1
                    else:
                        seed_result["min_prob"] = min(seed_result["min_prob"], p)
                        seed_result["max_prob"] = max(seed_result["max_prob"], p)

                if abs(total - 1.0) > NORM_TOLERANCE:
                    seed_result["norm_errors"] += 1

        seed_result["shape"] = f"{h}x{GRID_W}x{NUM_CLASSES}"

        # Aggregate seed issues
        if seed_result["nan_count"] > 0:
            seed_result["valid"] = False
            result["errors"].append(f"Seed {seed_idx}: {seed_result['nan_count']} NaN/inf values")

        if seed_result["zero_count"] > 0:
            seed_result["valid"] = False
            result["errors"].append(
                f"Seed {seed_idx}: {seed_result['zero_count']} probabilities <= 0. "
                f"KL divergence will be infinite. Floor at 0.01 and renormalize."
            )

        if 0 < seed_result["min_prob"] < PROB_FLOOR:
            result["warnings"].append(f"Seed {seed_idx}: min probability {seed_result['min_prob']:.6f} (recommend floor 0.01)")

        if seed_result["norm_errors"] > 0:
            seed_result["valid"] = False
            result["errors"].append(f"Seed {seed_idx}: {seed_result['norm_errors']} cells don't sum to 1.0 (tolerance {NORM_TOLERANCE})")

        if not seed_result["valid"]:
            result["valid"] = False

        result["seeds"].append(seed_result)

    if len(data) != 5:
        result["valid"] = False
        result["errors"].append(f"Expected 5 seeds, got {len(data)}. Must submit ALL 5 seeds.")

    return result


def main():
    parser = argparse.ArgumentParser(description="Validate ML prediction tensor")
    parser.add_argument("predictions", help="Path to predictions JSON file")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    path = Path(args.predictions)
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    data = json.loads(path.read_text())

    # Handle various formats: list of tensors, or dict with seeds key
    if isinstance(data, dict):
        if "predictions" in data:
            data = data["predictions"]
        elif "seeds" in data:
            data = data["seeds"]
        else:
            data = list(data.values())

    result = validate_predictions(data)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        status = "PASS" if result["valid"] else "FAIL"
        print(f"\nML Prediction Validation: {status}")
        print(f"Seeds: {result['seed_count']}")
        for s in result["seeds"]:
            icon = "PASS" if s["valid"] else "FAIL"
            print(f"  [{icon}] Seed {s['seed']}: shape={s['shape']}, min_p={s['min_prob']:.4f}, zeros={s['zero_count']}")
        if result["errors"]:
            print(f"\nErrors:")
            for e in result["errors"]:
                print(f"  {e}")
        if result["warnings"]:
            print(f"\nWarnings:")
            for w in result["warnings"]:
                print(f"  {w}")
        print()

    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
