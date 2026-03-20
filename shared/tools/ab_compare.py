#!/usr/bin/env python3
"""A/B compare two CV prediction sets with per-image and per-category breakdown.

Usage:
  python3 shared/tools/ab_compare.py --a predictions_v1.json --b predictions_v2.json
  python3 shared/tools/ab_compare.py --a prev_best.json --b new.json --top 20
"""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def load_preds(path: Path) -> list[dict]:
    """Load and validate predictions JSON."""
    preds = json.loads(path.read_text())
    if not isinstance(preds, list):
        print(f"FAIL: {path} is not a JSON array")
        raise SystemExit(1)
    return preds


def summarize(preds: list[dict], label: str) -> dict:
    """Compute summary stats for a prediction set."""
    if not preds:
        return {"label": label, "count": 0}

    scores = [p.get("score", 0) for p in preds]
    cats = [p.get("category_id", -1) for p in preds]
    images = [p.get("image_id", -1) for p in preds]

    return {
        "label": label,
        "count": len(preds),
        "unique_images": len(set(images)),
        "unique_cats": len(set(cats)),
        "preds_per_image": round(len(preds) / max(len(set(images)), 1), 1),
        "score_mean": round(sum(scores) / len(scores), 4),
        "score_median": round(sorted(scores)[len(scores) // 2], 4),
        "high_conf": sum(1 for s in scores if s >= 0.5),
        "cat_distribution": Counter(cats),
        "image_counts": Counter(images),
    }


def main():
    parser = argparse.ArgumentParser(description="A/B compare two prediction sets")
    parser.add_argument("--a", required=True, help="Path to predictions A (baseline)")
    parser.add_argument("--b", required=True, help="Path to predictions B (new)")
    parser.add_argument("--top", type=int, default=10,
                        help="Show top N differences (default: 10)")
    args = parser.parse_args()

    path_a = Path(args.a)
    path_b = Path(args.b)

    for p in [path_a, path_b]:
        if not p.exists():
            print(f"FAIL: File not found: {p}")
            raise SystemExit(1)

    preds_a = load_preds(path_a)
    preds_b = load_preds(path_b)
    stats_a = summarize(preds_a, f"A ({path_a.name})")
    stats_b = summarize(preds_b, f"B ({path_b.name})")

    print(f"=== A/B Comparison ===\n")

    # Side-by-side overview
    header = f"{'Metric':<25} {'A':>15} {'B':>15} {'Delta':>10}"
    print(header)
    print("-" * len(header))

    metrics = [
        ("Total predictions", "count"),
        ("Unique images", "unique_images"),
        ("Unique categories", "unique_cats"),
        ("Preds/image", "preds_per_image"),
        ("Score mean", "score_mean"),
        ("Score median", "score_median"),
        ("High conf (>=0.5)", "high_conf"),
    ]

    for label, key in metrics:
        va = stats_a.get(key, 0)
        vb = stats_b.get(key, 0)
        delta = vb - va
        sign = "+" if delta > 0 else ""
        print(f"{label:<25} {va:>15} {vb:>15} {sign}{delta:>9}")

    # Per-image comparison
    print(f"\n=== Per-Image Breakdown (top {args.top} differences) ===")
    all_images = set(stats_a["image_counts"].keys()) | set(stats_b["image_counts"].keys())

    diffs = []
    for img_id in all_images:
        count_a = stats_a["image_counts"].get(img_id, 0)
        count_b = stats_b["image_counts"].get(img_id, 0)
        diffs.append((img_id, count_a, count_b, count_b - count_a))

    diffs.sort(key=lambda x: abs(x[3]), reverse=True)
    print(f"{'Image ID':>10} {'A':>8} {'B':>8} {'Delta':>8}")
    print("-" * 40)
    for img_id, ca, cb, d in diffs[:args.top]:
        sign = "+" if d > 0 else ""
        print(f"{img_id:>10} {ca:>8} {cb:>8} {sign}{d:>7}")

    # Category coverage comparison
    cats_a = set(stats_a["cat_distribution"].keys())
    cats_b = set(stats_b["cat_distribution"].keys())
    only_a = cats_a - cats_b
    only_b = cats_b - cats_a
    shared = cats_a & cats_b

    print(f"\n=== Category Coverage ===")
    print(f"Shared categories:     {len(shared)}")
    print(f"Only in A:             {len(only_a)}")
    print(f"Only in B:             {len(only_b)}")
    if only_b:
        print(f"New in B:              {sorted(only_b)[:20]}{'...' if len(only_b) > 20 else ''}")
    if only_a:
        print(f"Lost from A:           {sorted(only_a)[:20]}{'...' if len(only_a) > 20 else ''}")

    # Score distribution comparison
    scores_a = sorted([p.get("score", 0) for p in preds_a])
    scores_b = sorted([p.get("score", 0) for p in preds_b])

    print(f"\n=== Score Distribution ===")
    bins = [(0, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.01)]
    print(f"{'Range':<12} {'A':>8} {'B':>8}")
    print("-" * 30)
    for lo, hi in bins:
        ca = sum(1 for s in scores_a if lo <= s < hi)
        cb = sum(1 for s in scores_b if lo <= s < hi)
        print(f"[{lo:.1f}-{hi:.1f}){'' if hi < 1 else ' ':<3} {ca:>8} {cb:>8}")

    # Overall assessment
    print(f"\n{'='*50}")
    improvements = 0
    regressions = 0
    if stats_b["count"] > stats_a["count"]:
        improvements += 1
    elif stats_b["count"] < stats_a["count"]:
        regressions += 1
    if stats_b["unique_cats"] > stats_a["unique_cats"]:
        improvements += 1
    elif stats_b["unique_cats"] < stats_a["unique_cats"]:
        regressions += 1
    if stats_b["score_mean"] > stats_a["score_mean"]:
        improvements += 1
    elif stats_b["score_mean"] < stats_a["score_mean"]:
        regressions += 1

    if improvements > regressions:
        print(f"Assessment: B looks BETTER ({improvements} improvements, {regressions} regressions)")
    elif regressions > improvements:
        print(f"Assessment: B looks WORSE ({regressions} regressions, {improvements} improvements)")
    else:
        print(f"Assessment: MIXED results ({improvements} improvements, {regressions} regressions)")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
