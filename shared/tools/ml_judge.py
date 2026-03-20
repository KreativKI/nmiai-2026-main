#!/usr/bin/env python3
"""
NM i AI 2026 — ML QC Judge (shared/tools/ml_judge.py)

Validates and scores Astar Island ML predictions before submission.
Catches validation errors that would waste limited submission slots.

Competition scoring: score = max(0, min(100, 100 * exp(-3 * weighted_KL)))

Usage:
    # Validate predictions only (no ground truth)
    python3 shared/tools/ml_judge.py predictions.json

    # Validate + score against ground truth
    python3 shared/tools/ml_judge.py predictions.json --ground-truth ground_truth.json

    # JSON output for dashboard
    python3 shared/tools/ml_judge.py predictions.json --json

    # Auto-fix floors and normalization
    python3 shared/tools/ml_judge.py predictions.json --fix --output fixed.json

Dependencies: numpy, json (stdlib)
"""

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

GRID_W = 40
GRID_H = 40
NUM_CLASSES = 6
PROB_FLOOR = 0.01
NORM_TOLERANCE = 1e-3
EXPECTED_SEEDS = 5

# Competition scoring constants
KL_MULTIPLIER = 3.0

# Terrain types for readable output
TERRAIN_NAMES = {0: "Mountain", 1: "Forest", 2: "Settlement", 3: "Port", 4: "Ruin", 5: "Empty"}

RESULTS_FILE = "shared/tools/ml_results.json"


def validate_tensor(tensor: list, seed_idx: int) -> dict:
    """Validate a single 40x40x6 prediction tensor."""
    result = {
        "seed": seed_idx,
        "valid": True,
        "errors": [],
        "warnings": [],
        "stats": {
            "min_prob": 1.0,
            "max_prob": 0.0,
            "zero_count": 0,
            "below_floor_count": 0,
            "nan_count": 0,
            "norm_errors": 0,
            "cells_checked": 0,
        },
    }

    if not isinstance(tensor, list) or len(tensor) != GRID_H:
        result["valid"] = False
        height = len(tensor) if isinstance(tensor, list) else "non-list"
        result["errors"].append(f"Height={height}, expected {GRID_H}")
        return result

    for y, row in enumerate(tensor):
        if not isinstance(row, list) or len(row) != GRID_W:
            result["valid"] = False
            width = len(row) if isinstance(row, list) else "non-list"
            result["errors"].append(f"Row {y}: width={width}, expected {GRID_W}")
            continue

        for x, probs in enumerate(row):
            if not isinstance(probs, list) or len(probs) != NUM_CLASSES:
                result["valid"] = False
                nc = len(probs) if isinstance(probs, list) else "non-list"
                result["errors"].append(f"Cell ({x},{y}): {nc} classes, expected {NUM_CLASSES}")
                continue

            result["stats"]["cells_checked"] += 1
            total = 0.0

            for p in probs:
                if not isinstance(p, (int, float)):
                    result["valid"] = False
                    result["stats"]["nan_count"] += 1
                    continue
                if math.isnan(p) or math.isinf(p):
                    result["valid"] = False
                    result["stats"]["nan_count"] += 1
                    continue

                total += p

                if p <= 0.0:
                    result["stats"]["zero_count"] += 1
                elif p < PROB_FLOOR:
                    result["stats"]["below_floor_count"] += 1

                if p > 0:
                    result["stats"]["min_prob"] = min(result["stats"]["min_prob"], p)
                result["stats"]["max_prob"] = max(result["stats"]["max_prob"], p)

            if abs(total - 1.0) > NORM_TOLERANCE:
                result["stats"]["norm_errors"] += 1

    # Summarize issues
    stats = result["stats"]

    if stats["nan_count"] > 0:
        result["valid"] = False
        result["errors"].append(f"{stats['nan_count']} NaN/inf values")

    if stats["zero_count"] > 0:
        result["valid"] = False
        result["errors"].append(
            f"{stats['zero_count']} probabilities <= 0. "
            f"KL divergence will be infinite. Must floor at {PROB_FLOOR} and renormalize."
        )

    if stats["below_floor_count"] > 0:
        result["warnings"].append(
            f"{stats['below_floor_count']} probabilities below {PROB_FLOOR} floor. "
            f"Consider flooring and renormalizing for safety."
        )

    if stats["norm_errors"] > 0:
        result["valid"] = False
        result["errors"].append(
            f"{stats['norm_errors']} cells don't sum to 1.0 (tolerance {NORM_TOLERANCE})"
        )

    return result


def validate_predictions(data: list) -> dict:
    """Validate all seed predictions."""
    result = {
        "valid": True,
        "seed_count": len(data),
        "errors": [],
        "warnings": [],
        "seeds": [],
    }

    if len(data) != EXPECTED_SEEDS:
        result["valid"] = False
        result["errors"].append(f"Expected {EXPECTED_SEEDS} seeds, got {len(data)}. Must submit ALL seeds.")

    for i, tensor in enumerate(data):
        seed_result = validate_tensor(tensor, i)
        result["seeds"].append(seed_result)
        if not seed_result["valid"]:
            result["valid"] = False
        result["errors"].extend(
            f"Seed {i}: {e}" for e in seed_result["errors"]
        )
        result["warnings"].extend(
            f"Seed {i}: {w}" for w in seed_result["warnings"]
        )

    return result


def cell_entropy(probs: list) -> float:
    """Shannon entropy of a probability distribution."""
    h = 0.0
    for p in probs:
        if p > 0:
            h -= p * math.log(p)
    return h


def compute_kl_divergence(pred_tensor: list, gt_tensor: list) -> float:
    """Compute entropy-weighted KL divergence for one seed.

    Competition formula: each cell's KL is weighted by that cell's GT entropy.
    Cells with low entropy (deterministic terrain) contribute less.
    Final value = sum(entropy_i * KL_i) / sum(entropy_i).

    KL(gt || pred) per cell = sum over classes of: gt[c] * log(gt[c] / pred[c])
    """
    weighted_kl_sum = 0.0
    entropy_sum = 0.0

    for y in range(GRID_H):
        for x in range(GRID_W):
            gt_probs = gt_tensor[y][x]
            pred_probs = pred_tensor[y][x]

            # Cell entropy (weight)
            ent = cell_entropy(gt_probs)

            # Cell KL divergence
            cell_kl = 0.0
            for c in range(NUM_CLASSES):
                gt_p = gt_probs[c]
                pred_p = max(pred_probs[c], 1e-10)  # Prevent log(0)
                if gt_p > 0:
                    cell_kl += gt_p * math.log(gt_p / pred_p)

            weighted_kl_sum += ent * cell_kl
            entropy_sum += ent

    if entropy_sum == 0:
        return 0.0  # All cells are deterministic, no divergence possible

    return weighted_kl_sum / entropy_sum


def compute_score(weighted_kl: float) -> float:
    """Competition score formula: max(0, min(100, 100 * exp(-3 * weighted_KL)))"""
    return max(0.0, min(100.0, 100.0 * math.exp(-KL_MULTIPLIER * weighted_kl)))


def score_predictions(pred_data: list, gt_data: list) -> dict:
    """Score predictions against ground truth for all seeds."""
    results = {
        "per_seed": [],
        "weighted_kl": 0.0,
        "score": 0.0,
    }

    seed_count = min(len(pred_data), len(gt_data))
    total_score = 0.0

    for i in range(seed_count):
        kl = compute_kl_divergence(pred_data[i], gt_data[i])
        seed_score = compute_score(kl)
        results["per_seed"].append({
            "seed": i,
            "kl_divergence": round(kl, 6),
            "score": round(seed_score, 2),
        })
        total_score += seed_score

    # Competition: round_score = mean(score_per_seed), NOT score(mean(KL))
    avg_kl = sum(s["kl_divergence"] for s in results["per_seed"]) / seed_count if seed_count > 0 else float("inf")
    results["weighted_kl"] = round(avg_kl, 6)
    results["score"] = round(total_score / seed_count, 2) if seed_count > 0 else 0.0

    return results


def fix_predictions(data: list) -> list:
    """Floor probabilities at PROB_FLOOR and renormalize."""
    fixed = []
    for tensor in data:
        fixed_tensor = []
        for row in tensor:
            fixed_row = []
            for probs in row:
                # Floor
                floored = [max(p, PROB_FLOOR) for p in probs]
                # Renormalize
                total = sum(floored)
                normalized = [p / total for p in floored]
                fixed_row.append(normalized)
            fixed_tensor.append(fixed_row)
        fixed.append(fixed_tensor)
    return fixed


def parse_prediction_data(raw_data) -> list:
    """Handle various prediction formats and extract tensor list."""
    if isinstance(raw_data, list):
        return raw_data

    if isinstance(raw_data, dict):
        # Try common keys
        for key in ("predictions", "seeds", "tensors", "data"):
            if key in raw_data:
                return parse_prediction_data(raw_data[key])
        # Try seed-numbered keys
        if "0" in raw_data or 0 in raw_data:
            return [raw_data[k] for k in sorted(raw_data.keys(), key=str)]
        return list(raw_data.values())

    return raw_data


def load_previous_results(results_path: Path) -> list:
    """Load previous scoring results for comparison."""
    if results_path.exists():
        return json.loads(results_path.read_text())
    return []


def save_result(results_path: Path, result: dict):
    """Append result to history file."""
    results_path.parent.mkdir(parents=True, exist_ok=True)
    history = load_previous_results(results_path)
    history.append(result)
    results_path.write_text(json.dumps(history, indent=2))


def determine_verdict(validation: dict, scoring: dict | None, history: list) -> str:
    """Determine submission verdict."""
    if not validation["valid"]:
        return "VALIDATION_ERROR"

    if scoring is None:
        # No ground truth, can only validate
        return "VALID"

    current_score = scoring["score"]

    if not history:
        return "SUBMIT"

    scored_history = [h for h in history if "score" in h and h["score"] is not None]
    if not scored_history:
        return "SUBMIT"

    best_previous = max(h["score"] for h in scored_history)

    if current_score > best_previous + 0.5:
        return "SUBMIT"
    elif current_score < best_previous - 0.5:
        return "SKIP"
    else:
        return "RISKY"


def find_repo_root() -> Path:
    """Walk up from cwd to find the repo root."""
    cwd = Path.cwd()
    for p in [cwd] + list(cwd.parents):
        if (p / "CLAUDE.md").exists() or (p / "shared").exists():
            return p
    return cwd


def main():
    parser = argparse.ArgumentParser(
        description="ML QC Judge: Validate and score predictions before submission"
    )
    parser.add_argument("predictions", help="Path to predictions JSON file")
    parser.add_argument("--ground-truth", help="Path to ground truth JSON for scoring")
    parser.add_argument("--json", action="store_true", help="JSON output for dashboard")
    parser.add_argument("--fix", action="store_true", help="Auto-fix floors and normalization")
    parser.add_argument("--output", help="Write fixed predictions to file (requires --fix)")
    args = parser.parse_args()

    pred_path = Path(args.predictions)
    if not pred_path.exists():
        print(f"ERROR: File not found: {pred_path}")
        raise SystemExit(1)

    raw_data = json.loads(pred_path.read_text())
    data = parse_prediction_data(raw_data)

    # Validate
    print("Validating predictions...")
    validation = validate_predictions(data)

    # Auto-fix if requested (applies regardless of validation status to catch below-floor warnings)
    if args.fix:
        print("Applying fixes (floor + renormalize)...")
        data = fix_predictions(data)
        validation = validate_predictions(data)
        print(f"After fix: {'PASS' if validation['valid'] else 'STILL FAILING'}")

        if args.output:
            Path(args.output).write_text(json.dumps(data))
            print(f"Fixed predictions written to: {args.output}")

    # Score if ground truth provided
    scoring = None
    if args.ground_truth:
        gt_path = Path(args.ground_truth)
        if gt_path.exists():
            gt_raw = json.loads(gt_path.read_text())
            gt_data = parse_prediction_data(gt_raw)
            print("Scoring against ground truth...")
            scoring = score_predictions(data, gt_data)
        else:
            print(f"WARNING: Ground truth file not found: {gt_path}")

    # History and verdict
    repo_root = find_repo_root()
    results_path = repo_root / RESULTS_FILE
    history = load_previous_results(results_path)
    verdict = determine_verdict(validation, scoring, history)

    # Save result
    this_result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": str(pred_path),
        "seed_count": validation["seed_count"],
        "valid": validation["valid"],
        "error_count": len(validation["errors"]),
        "warning_count": len(validation["warnings"]),
        "score": scoring["score"] if scoring else None,
        "weighted_kl": scoring["weighted_kl"] if scoring else None,
        "verdict": verdict,
    }
    save_result(results_path, this_result)

    if args.json:
        output = {
            "validation": validation,
            "scoring": scoring,
            "verdict": verdict,
            "result": this_result,
        }
        print(json.dumps(output, indent=2))
    else:
        v_status = "PASS" if validation["valid"] else "FAIL"
        print(f"\n{'='*55}")
        print(f"  ML QC Judge Results")
        print(f"{'='*55}")
        print(f"  Source:          {pred_path}")
        print(f"  Seeds:           {validation['seed_count']} / {EXPECTED_SEEDS}")
        print(f"  Validation:      {v_status}")

        for s in validation["seeds"]:
            icon = "PASS" if s["valid"] else "FAIL"
            stats = s["stats"]
            print(
                f"    [{icon}] Seed {s['seed']}: "
                f"cells={stats['cells_checked']}, "
                f"min_p={stats['min_prob']:.4f}, "
                f"zeros={stats['zero_count']}, "
                f"norm_err={stats['norm_errors']}"
            )

        if validation["errors"]:
            print(f"\n  Errors ({len(validation['errors'])}):")
            for e in validation["errors"][:10]:
                print(f"    {e}")
            if len(validation["errors"]) > 10:
                print(f"    ... and {len(validation['errors']) - 10} more")

        if validation["warnings"]:
            print(f"\n  Warnings ({len(validation['warnings'])}):")
            for w in validation["warnings"][:5]:
                print(f"    {w}")

        if scoring:
            print(f"\n  Scoring:")
            for s in scoring["per_seed"]:
                print(f"    Seed {s['seed']}: KL={s['kl_divergence']:.4f}  Score={s['score']:.1f}")
            print(f"    Weighted KL: {scoring['weighted_kl']:.4f}")
            print(f"    Predicted score: {scoring['score']:.1f} / 100")

            if history:
                scored = [h for h in history if h.get("score") is not None]
                if scored:
                    best_prev = max(h["score"] for h in scored)
                    delta = scoring["score"] - best_prev
                    sign = "+" if delta >= 0 else ""
                    print(f"    vs previous best: {sign}{delta:.1f} (was {best_prev:.1f})")

        print(f"\n  Verdict: {verdict}")
        if verdict == "VALIDATION_ERROR":
            print("  Fix validation errors before submitting.")
            print("  Tip: use --fix --output fixed.json to auto-fix floors + normalization")
        elif verdict == "SUBMIT":
            print("  Score improved. Safe to submit.")
        elif verdict == "SKIP":
            print("  Score regressed. Do NOT submit.")
        elif verdict == "RISKY":
            print("  Marginal change. Review before submitting.")
        elif verdict == "VALID":
            print("  Validation passed. No ground truth for scoring.")
        print(f"{'='*55}\n")

    exit_codes = {"VALIDATION_ERROR": 2, "SKIP": 1}
    raise SystemExit(exit_codes.get(verdict, 0))


if __name__ == "__main__":
    main()
