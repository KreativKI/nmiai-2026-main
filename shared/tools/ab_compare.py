#!/usr/bin/env python3
"""
NM i AI 2026 — A/B Compare Tool (shared/tools/ab_compare.py)

Compares two CV prediction sets side by side to show exactly which
images and categories improved or regressed. Uses the same scoring
as cv_judge.py (pycocotools mAP@0.5).

Adapted from grocery bot ab_compare.py pattern (Welch's t-test).

Usage:
    # Compare two predictions.json files
    python3 shared/tools/ab_compare.py --a preds_yolo.json --b preds_dinov2.json

    # Custom labels
    python3 shared/tools/ab_compare.py --a preds_v1.json --b preds_v2.json \
        --label-a "YOLO-only" --label-b "DINOv2+YOLO"

    # Show per-image breakdown
    python3 shared/tools/ab_compare.py --a a.json --b b.json --per-image

    # JSON output
    python3 shared/tools/ab_compare.py --a a.json --b b.json --json

Dependencies: pycocotools, numpy, scipy (optional, for Welch's t-test)
"""

import argparse
import contextlib
import io
import json
import math
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

try:
    import numpy as np
    from pycocotools.coco import COCO
    from pycocotools.cocoeval import COCOeval
except ImportError:
    print("ERROR: pycocotools and numpy required.")
    raise SystemExit(1)

DEFAULT_IMAGES_DIR = "agent-cv/data/yolo_dataset/images/train"
DEFAULT_LABELS_DIR = "agent-cv/data/yolo_dataset/labels/train"
HOLDOUT_MOD = 5
HOLDOUT_REMAINDER = 0


def extract_image_id(filename: str) -> int | None:
    m = re.search(r"img_(\d+)", Path(filename).stem)
    return int(m.group(1)) if m else None


def get_image_dimensions(image_path: Path) -> tuple[int, int]:
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            return img.width, img.height
    except ImportError:
        return 2000, 2000


def build_coco_gt(images_dir: Path, labels_dir: Path) -> dict:
    """Build COCO ground truth from YOLO labels for holdout split."""
    images = []
    annotations = []
    categories = set()
    ann_id = 1

    for img_path in sorted(images_dir.iterdir()):
        if img_path.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            continue
        image_id = extract_image_id(img_path.name)
        if image_id is None or image_id % HOLDOUT_MOD != HOLDOUT_REMAINDER:
            continue

        img_w, img_h = get_image_dimensions(img_path)
        images.append({"id": image_id, "file_name": img_path.name, "width": img_w, "height": img_h})

        label_path = labels_dir / f"{img_path.stem}.txt"
        if not label_path.exists():
            continue

        for line in label_path.read_text().strip().splitlines():
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            cls_id = int(parts[0])
            cx, cy, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
            x = (cx - w / 2) * img_w
            y = (cy - h / 2) * img_h
            bw, bh = w * img_w, h * img_h
            categories.add(cls_id)
            annotations.append({
                "id": ann_id, "image_id": image_id, "category_id": cls_id,
                "bbox": [round(x, 2), round(y, 2), round(bw, 2), round(bh, 2)],
                "area": round(bw * bh, 2), "iscrowd": 0,
            })
            ann_id += 1

    return {
        "images": images,
        "annotations": annotations,
        "categories": [{"id": c, "name": str(c)} for c in sorted(categories)],
    }


def score_coco(gt_dict: dict, predictions: list) -> float:
    """Run pycocotools and return mAP@0.5."""
    if not predictions:
        return 0.0
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(gt_dict, f)
        gt_path = f.name
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            coco_gt = COCO(gt_path)
            coco_dt = coco_gt.loadRes(predictions)
            evaluator = COCOeval(coco_gt, coco_dt, "bbox")
            evaluator.evaluate()
            evaluator.accumulate()
            evaluator.summarize()
        return float(evaluator.stats[1])  # mAP@IoU=0.5
    finally:
        Path(gt_path).unlink(missing_ok=True)


def per_image_ap(gt_dict: dict, predictions: list) -> dict[int, float]:
    """Compute AP@0.5 per image."""
    holdout_ids = {img["id"] for img in gt_dict["images"]}
    results = {}

    for img_id in holdout_ids:
        img_preds = [p for p in predictions if p["image_id"] == img_id]
        img_gt = {
            "images": [img for img in gt_dict["images"] if img["id"] == img_id],
            "annotations": [a for a in gt_dict["annotations"] if a["image_id"] == img_id],
            "categories": gt_dict["categories"],
        }
        if not img_gt["annotations"]:
            results[img_id] = 0.0
            continue
        results[img_id] = score_coco(img_gt, img_preds)

    return results


def welch_ttest(scores_a: list, scores_b: list) -> dict:
    """Welch's t-test for independent samples with unequal variance."""
    try:
        from scipy.stats import ttest_ind
        t_stat, p_value = ttest_ind(scores_a, scores_b, equal_var=False)
        return {"t_stat": round(float(t_stat), 4), "p_value": round(float(p_value), 6)}
    except ImportError:
        # Manual fallback
        n_a, n_b = len(scores_a), len(scores_b)
        if n_a < 2 or n_b < 2:
            return {"t_stat": 0, "p_value": 1.0}
        mean_a = sum(scores_a) / n_a
        mean_b = sum(scores_b) / n_b
        var_a = sum((x - mean_a) ** 2 for x in scores_a) / (n_a - 1)
        var_b = sum((x - mean_b) ** 2 for x in scores_b) / (n_b - 1)
        se = (var_a / n_a + var_b / n_b) ** 0.5
        if se == 0:
            return {"t_stat": 0, "p_value": 1.0}
        t_stat = (mean_a - mean_b) / se
        p_value = 2 * (1 - 0.5 * (1 + math.erf(abs(t_stat) / math.sqrt(2))))
        return {"t_stat": round(t_stat, 4), "p_value": round(p_value, 6)}


def load_predictions(path: str) -> list:
    data = json.loads(Path(path).read_text())
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "predictions" in data:
        return data["predictions"]
    raise ValueError(
        f"Unrecognized predictions format in {path}. "
        "Expected a list or a dict with a 'predictions' key."
    )


def find_repo_root() -> Path:
    cwd = Path.cwd()
    for p in [cwd] + list(cwd.parents):
        if (p / "CLAUDE.md").exists() or (p / "shared").exists():
            return p
    return cwd


def main():
    parser = argparse.ArgumentParser(description="A/B Compare two CV prediction sets")
    parser.add_argument("--a", required=True, help="Path to predictions A (JSON)")
    parser.add_argument("--b", required=True, help="Path to predictions B (JSON)")
    parser.add_argument("--label-a", default="A", help="Label for version A")
    parser.add_argument("--label-b", default="B", help="Label for version B")
    parser.add_argument("--images-dir", help="Path to images directory")
    parser.add_argument("--labels-dir", help="Path to YOLO labels directory")
    parser.add_argument("--per-image", action="store_true", help="Show per-image breakdown")
    parser.add_argument("--top-n", type=int, default=10, help="Show top N changed items (default: 10)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    repo_root = find_repo_root()
    images_dir = Path(args.images_dir) if args.images_dir else repo_root / DEFAULT_IMAGES_DIR
    labels_dir = Path(args.labels_dir) if args.labels_dir else repo_root / DEFAULT_LABELS_DIR

    if not images_dir.exists() or not labels_dir.exists():
        print("ERROR: Data directories not found")
        raise SystemExit(1)

    preds_a = load_predictions(args.a)
    preds_b = load_predictions(args.b)

    print("Building ground truth (holdout split)...")
    gt = build_coco_gt(images_dir, labels_dir)
    holdout_ids = {img["id"] for img in gt["images"]}

    preds_a = [p for p in preds_a if p["image_id"] in holdout_ids]
    preds_b = [p for p in preds_b if p["image_id"] in holdout_ids]

    print(f"  Holdout images: {len(holdout_ids)}")
    print(f"  Predictions A ({args.label_a}): {len(preds_a)}")
    print(f"  Predictions B ({args.label_b}): {len(preds_b)}")

    # Overall scores: detection + classification
    print("\nScoring...")
    det_gt = {
        "images": gt["images"],
        "categories": [{"id": 0, "name": "object"}],
        "annotations": [{**a, "category_id": 0} for a in gt["annotations"]],
    }
    det_a = score_coco(det_gt, [{**p, "category_id": 0} for p in preds_a])
    cls_a = score_coco(gt, preds_a)
    combined_a = 0.7 * det_a + 0.3 * cls_a

    det_b = score_coco(det_gt, [{**p, "category_id": 0} for p in preds_b])
    cls_b = score_coco(gt, preds_b)
    combined_b = 0.7 * det_b + 0.3 * cls_b

    # Per-image comparison
    print("Per-image analysis...")
    img_ap_a = per_image_ap(gt, preds_a)
    img_ap_b = per_image_ap(gt, preds_b)

    improved, regressed, unchanged = [], [], []
    for img_id in holdout_ids:
        ap_a = img_ap_a.get(img_id, 0)
        ap_b = img_ap_b.get(img_id, 0)
        delta = ap_b - ap_a
        entry = {"image_id": img_id, "ap_a": round(ap_a, 4), "ap_b": round(ap_b, 4), "delta": round(delta, 4)}
        if delta > 0.01:
            improved.append(entry)
        elif delta < -0.01:
            regressed.append(entry)
        else:
            unchanged.append(entry)

    improved.sort(key=lambda x: x["delta"], reverse=True)
    regressed.sort(key=lambda x: x["delta"])

    # Statistical test
    all_ap_a = [img_ap_a.get(i, 0) for i in holdout_ids]
    all_ap_b = [img_ap_b.get(i, 0) for i in holdout_ids]
    ttest = welch_ttest(all_ap_a, all_ap_b)

    # Resolve direction from the same per-image AP values that were tested
    mean_ap_a = sum(all_ap_a) / len(all_ap_a) if all_ap_a else 0
    mean_ap_b = sum(all_ap_b) / len(all_ap_b) if all_ap_b else 0
    if ttest["p_value"] < 0.05:
        verdict = "B_BETTER" if mean_ap_b > mean_ap_a else "A_BETTER"
    else:
        verdict = "NO_SIGNIFICANT_DIFFERENCE"

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "label_a": args.label_a, "label_b": args.label_b,
        "scores": {
            "a": {"detection_mAP": round(det_a, 4), "classification_mAP": round(cls_a, 4), "combined": round(combined_a, 4)},
            "b": {"detection_mAP": round(det_b, 4), "classification_mAP": round(cls_b, 4), "combined": round(combined_b, 4)},
        },
        "delta": {"detection_mAP": round(det_b - det_a, 4), "classification_mAP": round(cls_b - cls_a, 4), "combined": round(combined_b - combined_a, 4)},
        "per_image_summary": {"improved": len(improved), "regressed": len(regressed), "unchanged": len(unchanged)},
        "ttest": ttest, "verdict": verdict,
    }

    if args.json:
        result["improved_images"] = improved[:args.top_n]
        result["regressed_images"] = regressed[:args.top_n]
        print(json.dumps(result, indent=2))
    else:
        la, lb = args.label_a, args.label_b
        print(f"\n{'='*62}")
        print(f"  A/B Comparison: {la} vs {lb}")
        print(f"{'='*62}")
        print()
        print(f"  {'Metric':<25s}  {la:>10s}  {lb:>10s}  {'Delta':>10s}")
        print(f"  {'-'*57}")
        print(f"  {'Detection mAP@0.5':<25s}  {det_a:>10.4f}  {det_b:>10.4f}  {det_b-det_a:>+10.4f}")
        print(f"  {'Classification mAP':<25s}  {cls_a:>10.4f}  {cls_b:>10.4f}  {cls_b-cls_a:>+10.4f}")
        print(f"  {'Combined (70/30)':<25s}  {combined_a:>10.4f}  {combined_b:>10.4f}  {combined_b-combined_a:>+10.4f}")
        print()
        print(f"  Per-image breakdown ({len(holdout_ids)} images):")
        print(f"    Improved:   {len(improved):>4d}")
        print(f"    Regressed:  {len(regressed):>4d}")
        print(f"    Unchanged:  {len(unchanged):>4d}")

        if args.per_image and improved:
            print(f"\n  Top {min(args.top_n, len(improved))} improved images ({lb} better):")
            for e in improved[:args.top_n]:
                print(f"    img_{e['image_id']:05d}: {e['ap_a']:.4f} -> {e['ap_b']:.4f} ({e['delta']:+.4f})")
        if args.per_image and regressed:
            print(f"\n  Top {min(args.top_n, len(regressed))} regressed images ({la} better):")
            for e in regressed[:args.top_n]:
                print(f"    img_{e['image_id']:05d}: {e['ap_a']:.4f} -> {e['ap_b']:.4f} ({e['delta']:+.4f})")

        print(f"\n  Statistical test (Welch's t-test on per-image AP):")
        print(f"    t-statistic: {ttest['t_stat']}")
        print(f"    p-value:     {ttest['p_value']}")
        sig = "YES (p < 0.05)" if ttest["p_value"] < 0.05 else "NO (p >= 0.05)"
        print(f"    Significant: {sig}")

        print(f"\n  Verdict: {verdict}")
        if verdict == "B_BETTER":
            print(f"  {lb} is statistically better than {la}.")
        elif verdict == "A_BETTER":
            print(f"  {la} is statistically better than {lb}.")
        else:
            print(f"  No significant difference between {la} and {lb}.")
        print(f"{'='*62}\n")

    raise SystemExit(0)


if __name__ == "__main__":
    main()
