#!/usr/bin/env python3
"""CV Judge: Score and assess CV predictions quality.

Without ground truth: analyzes prediction quality heuristics (format, coverage,
score distribution, detection density). With ground truth: computes actual
70% det mAP + 30% cls mAP using pycocotools.

Verdict: SUBMIT / RISKY / SKIP

Usage:
  python3 shared/tools/cv_judge.py --predictions-json predictions.json
  python3 shared/tools/cv_judge.py --predictions-json predictions.json --ground-truth annotations.json
"""
import argparse
import json
from collections import Counter
from pathlib import Path

NUM_CATEGORIES = 357  # IDs 0-356


def analyze_predictions(preds: list[dict]) -> dict:
    """Analyze prediction quality without ground truth."""
    if not preds:
        return {"verdict": "SKIP", "reason": "No predictions", "score_estimate": 0}

    # Format checks: sample first 10 for structure, check ALL for category range
    required_fields = {"image_id", "category_id", "bbox", "score"}
    format_errors = []
    for i, p in enumerate(preds[:10]):
        missing = required_fields - set(p.keys())
        if missing:
            format_errors.append(f"Prediction {i}: missing {missing}")
        if "bbox" in p and (not isinstance(p["bbox"], list) or len(p["bbox"]) != 4):
            format_errors.append(f"Prediction {i}: bbox must be [x,y,w,h]")

    # Check category_id range on ALL predictions (out-of-range = silent scoring failure)
    bad_cats = [
        (i, p.get("category_id"))
        for i, p in enumerate(preds)
        if "category_id" in p and not (0 <= p["category_id"] <= 356)
    ]
    if bad_cats:
        for i, cat in bad_cats[:5]:
            format_errors.append(f"Prediction {i}: category_id {cat} out of range 0-356")
        if len(bad_cats) > 5:
            format_errors.append(f"...and {len(bad_cats) - 5} more out-of-range category_ids")

    # Statistics
    scores = [p.get("score", 0) for p in preds]
    cat_ids = [p.get("category_id", -1) for p in preds]
    image_ids = [p.get("image_id", -1) for p in preds]

    unique_images = len(set(image_ids))
    unique_cats = len(set(cat_ids))
    preds_per_image = len(preds) / max(unique_images, 1)

    cat_counter = Counter(cat_ids)
    top_cats = cat_counter.most_common(10)

    # Score distribution
    high_conf = sum(1 for s in scores if s >= 0.5)
    med_conf = sum(1 for s in scores if 0.15 <= s < 0.5)
    low_conf = sum(1 for s in scores if s < 0.15)

    # Bbox sanity
    negative_bbox = 0
    zero_area = 0
    for p in preds:
        if "bbox" in p and len(p["bbox"]) == 4:
            x, y, w, h = p["bbox"]
            if w <= 0 or h <= 0:
                zero_area += 1
            if x < 0 or y < 0:
                negative_bbox += 1

    return {
        "total_predictions": len(preds),
        "unique_images": unique_images,
        "unique_categories": unique_cats,
        "preds_per_image": round(preds_per_image, 1),
        "score_mean": round(sum(scores) / len(scores), 4),
        "score_median": round(sorted(scores)[len(scores) // 2], 4),
        "high_conf_pct": round(100 * high_conf / len(preds), 1),
        "med_conf_pct": round(100 * med_conf / len(preds), 1),
        "low_conf_pct": round(100 * low_conf / len(preds), 1),
        "top_categories": top_cats,
        "zero_area_boxes": zero_area,
        "negative_bbox": negative_bbox,
        "format_errors": format_errors,
    }


def compute_verdict(stats: dict) -> tuple[str, str, float]:
    """Return (verdict, reason, estimated_score)."""
    issues = []

    if stats.get("format_errors"):
        return "SKIP", f"Format errors: {stats['format_errors'][:3]}", 0

    if stats["total_predictions"] == 0:
        return "SKIP", "No predictions", 0

    if stats["zero_area_boxes"] > 0:
        issues.append(f"{stats['zero_area_boxes']} zero-area boxes")

    if stats["unique_categories"] < 10:
        issues.append(f"Only {stats['unique_categories']} categories predicted (357 available)")

    if stats["preds_per_image"] < 5:
        issues.append(f"Low density: {stats['preds_per_image']} preds/image (shelves usually have 50-100+ products)")

    if stats["high_conf_pct"] < 10:
        issues.append(f"Very few high-confidence detections ({stats['high_conf_pct']}%)")

    # Estimate score based on heuristics
    base = 30  # Reasonable baseline for any working model
    if stats["unique_categories"] > 50:
        base += 10
    if stats["unique_categories"] > 150:
        base += 10
    if stats["preds_per_image"] > 30:
        base += 5
    if stats["high_conf_pct"] > 30:
        base += 5
    if stats["score_mean"] > 0.5:
        base += 5

    estimated = min(base, 80)  # Cap heuristic estimate

    if issues:
        verdict = "RISKY"
        reason = "; ".join(issues)
    else:
        verdict = "SUBMIT"
        reason = "Predictions look healthy"

    return verdict, reason, estimated


def main():
    parser = argparse.ArgumentParser(description="CV Judge: Score predictions")
    parser.add_argument("--predictions-json", required=True,
                        help="Path to predictions JSON file")
    parser.add_argument("--ground-truth", default=None,
                        help="Path to COCO annotations JSON (optional, for actual mAP)")
    args = parser.parse_args()

    pred_path = Path(args.predictions_json)
    if not pred_path.exists():
        print(f"FAIL: Predictions file not found: {pred_path}")
        raise SystemExit(1)

    preds = json.loads(pred_path.read_text())
    if not isinstance(preds, list):
        print("FAIL: predictions.json must be a JSON array")
        raise SystemExit(1)

    print(f"=== CV Judge: {pred_path.name} ===\n")

    # Heuristic analysis (always)
    stats = analyze_predictions(preds)

    print(f"Predictions:       {stats['total_predictions']}")
    print(f"Images:            {stats['unique_images']}")
    print(f"Categories used:   {stats['unique_categories']} / {NUM_CATEGORIES}")
    print(f"Preds/image:       {stats['preds_per_image']}")
    print(f"Score mean:        {stats['score_mean']}")
    print(f"Score median:      {stats['score_median']}")
    print(f"High conf (>=0.5): {stats['high_conf_pct']}%")
    print(f"Med conf:          {stats['med_conf_pct']}%")
    print(f"Low conf (<0.15):  {stats['low_conf_pct']}%")
    print(f"Zero-area boxes:   {stats['zero_area_boxes']}")

    if stats["top_categories"]:
        print(f"\nTop 10 categories (id: count):")
        for cat_id, count in stats["top_categories"]:
            print(f"  {cat_id:4d}: {count}")

    if stats["format_errors"]:
        print(f"\nFormat errors:")
        for e in stats["format_errors"]:
            print(f"  {e}")

    # Ground truth scoring (if available)
    if args.ground_truth:
        gt_path = Path(args.ground_truth)
        if not gt_path.exists():
            print(f"\nWARNING: Ground truth not found: {gt_path}")
        else:
            try:
                from pycocotools.coco import COCO
                from pycocotools.cocoeval import COCOeval

                coco_gt = COCO(str(gt_path))
                coco_dt = coco_gt.loadRes(preds)

                # mAP calculation (category-specific by default in COCOeval)
                coco_eval = COCOeval(coco_gt, coco_dt, "bbox")
                coco_eval.evaluate()
                coco_eval.accumulate()
                coco_eval.summarize()
                det_map = coco_eval.stats[0]

                # COCOeval bbox mAP is category-aware (considers category_id matching)
                # For a proper 70/30 split we'd need separate category-agnostic eval,
                # but COCOeval doesn't support that natively. Report as combined mAP.
                print(f"\n--- Ground Truth Scoring ---")
                print(f"mAP (bbox, category-aware): {det_map:.4f}")
                print(f"NOTE: This is the combined COCO mAP. The competition's 70/30")
                print(f"      det/cls split requires platform evaluation.")
            except ImportError:
                print("\nWARNING: pycocotools not available, skipping mAP calculation")

    # Verdict
    verdict, reason, estimated = compute_verdict(stats)
    print(f"\n{'='*50}")
    print(f"Verdict: {verdict}")
    print(f"Reason:  {reason}")
    if not args.ground_truth:
        print(f"Estimated score: ~{estimated}% (heuristic, no ground truth)")
    print(f"{'='*50}")

    if verdict == "SKIP":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
