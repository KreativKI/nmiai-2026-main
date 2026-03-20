#!/usr/bin/env python3
"""
NM i AI 2026 — Batch Evaluation Tool (shared/tools/batch_eval.py)

Runs cv_judge scoring across all CV submission predictions at once.
Prints a ranked table showing which submission is actually best.

Usage:
    # Evaluate specific predictions.json files
    python3 shared/tools/batch_eval.py --predictions preds_v1.json preds_v2.json preds_v3.json

    # Evaluate all .json files in a directory
    python3 shared/tools/batch_eval.py --predictions-dir agent-cv/docker_output/

    # JSON output
    python3 shared/tools/batch_eval.py --predictions preds_v1.json preds_v2.json --json

Dependencies: pycocotools, numpy, Pillow
"""

import argparse
import contextlib
import io
import json
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
DEFAULT_SUBMISSIONS_DIR = "agent-cv/submissions"
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
    images, annotations, categories = [], [], set()
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
            x, y = (cx - w / 2) * img_w, (cy - h / 2) * img_h
            bw, bh = w * img_w, h * img_h
            categories.add(cls_id)
            annotations.append({
                "id": ann_id, "image_id": image_id, "category_id": cls_id,
                "bbox": [round(x, 2), round(y, 2), round(bw, 2), round(bh, 2)],
                "area": round(bw * bh, 2), "iscrowd": 0,
            })
            ann_id += 1
    return {
        "images": images, "annotations": annotations,
        "categories": [{"id": c, "name": str(c)} for c in sorted(categories)],
    }


def score_coco(gt_dict: dict, predictions: list) -> float:
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
        return float(evaluator.stats[1])
    finally:
        Path(gt_path).unlink(missing_ok=True)


def score_submission(gt_dict: dict, predictions: list, holdout_ids: set) -> dict:
    """Score one prediction set: detection mAP + classification mAP + combined."""
    preds = [p for p in predictions if p["image_id"] in holdout_ids]
    det_gt = {
        "images": gt_dict["images"],
        "categories": [{"id": 0, "name": "object"}],
        "annotations": [{**a, "category_id": 0} for a in gt_dict["annotations"]],
    }
    det_map = score_coco(det_gt, [{**p, "category_id": 0} for p in preds])
    cls_map = score_coco(gt_dict, preds)
    combined = 0.7 * det_map + 0.3 * cls_map
    return {
        "prediction_count": len(preds),
        "detection_mAP": round(det_map, 4),
        "classification_mAP": round(cls_map, 4),
        "combined": round(combined, 4),
    }


def load_predictions_from_json(path: Path) -> list | None:
    """Load predictions from a JSON file."""
    try:
        data = json.loads(path.read_text())
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "predictions" in data:
            return data["predictions"]
        return None
    except (json.JSONDecodeError, AttributeError):
        return None


def find_repo_root() -> Path:
    cwd = Path.cwd()
    for p in [cwd] + list(cwd.parents):
        if (p / "CLAUDE.md").exists() or (p / "shared").exists():
            return p
    return cwd


def main():
    parser = argparse.ArgumentParser(description="Batch evaluate all CV submissions")
    parser.add_argument("--predictions-dir", help="Directory containing predictions.json files")
    parser.add_argument("--predictions", nargs="+", help="Specific predictions.json files")
    parser.add_argument("--images-dir", help="Path to images directory")
    parser.add_argument("--labels-dir", help="Path to YOLO labels directory")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    repo_root = find_repo_root()
    images_dir = Path(args.images_dir) if args.images_dir else repo_root / DEFAULT_IMAGES_DIR
    labels_dir = Path(args.labels_dir) if args.labels_dir else repo_root / DEFAULT_LABELS_DIR

    if not images_dir.exists() or not labels_dir.exists():
        print("ERROR: Data directories not found")
        raise SystemExit(1)

    # Collect prediction sources
    sources = []

    if args.predictions:
        for p in args.predictions:
            path = Path(p)
            preds = load_predictions_from_json(path)
            if preds is not None:
                sources.append((path.name, preds))
            else:
                print(f"WARNING: Could not load {path}")

    elif args.predictions_dir:
        pred_dir = Path(args.predictions_dir)
        for f in sorted(pred_dir.glob("*.json")):
            preds = load_predictions_from_json(f)
            if preds is not None:
                sources.append((f.name, preds))

    else:
        # Default: look for predictions.json files in common locations
        for search_dir in [
            repo_root / "agent-cv" / "docker_output",
            repo_root / DEFAULT_SUBMISSIONS_DIR,
        ]:
            if search_dir.exists():
                for f in sorted(search_dir.glob("*.json")):
                    preds = load_predictions_from_json(f)
                    if preds is not None:
                        sources.append((f"{search_dir.name}/{f.name}", preds))

    if not sources:
        print("ERROR: No prediction files found.")
        print("  Provide --predictions or --predictions-dir")
        print("  Or place .json files in agent-cv/docker_output/ or agent-cv/submissions/")
        raise SystemExit(1)

    # Build ground truth once
    print(f"Building ground truth (holdout split)...")
    gt = build_coco_gt(images_dir, labels_dir)
    holdout_ids = {img["id"] for img in gt["images"]}
    print(f"  Holdout images: {len(holdout_ids)}, GT annotations: {len(gt['annotations'])}")

    # Score each source
    results = []
    for name, preds in sources:
        print(f"  Scoring: {name}...")
        scores = score_submission(gt, preds, holdout_ids)
        scores["name"] = name
        results.append(scores)

    # Rank by combined score
    results.sort(key=lambda r: r["combined"], reverse=True)
    for i, r in enumerate(results, 1):
        r["rank"] = i
        r["best"] = (i == 1)

    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "holdout_images": len(holdout_ids),
        "gt_annotations": len(gt["annotations"]),
        "submissions": results,
    }

    if args.json:
        print(json.dumps(output, indent=2))
    else:
        print(f"\n{'='*75}")
        print(f"  Batch Evaluation: {len(results)} submissions ranked")
        print(f"{'='*75}")
        print()
        print(f"  {'#':<4s} {'Name':<40s} {'Det mAP':>8s} {'Cls mAP':>8s} {'Combined':>9s} {'Preds':>6s}")
        print(f"  {'-'*71}")
        for r in results:
            marker = " *" if r["best"] else "  "
            print(
                f"  {r['rank']:<4d} {r['name']:<40s} "
                f"{r['detection_mAP']:>8.4f} {r['classification_mAP']:>8.4f} "
                f"{r['combined']:>9.4f} {r['prediction_count']:>6d}{marker}"
            )
        print()
        print("  * = best submission")
        if len(results) > 1:
            gap = results[0]["combined"] - results[1]["combined"]
            print(f"  Gap between #1 and #2: {gap:+.4f}")
        print(f"{'='*75}\n")

    raise SystemExit(0)


if __name__ == "__main__":
    main()
