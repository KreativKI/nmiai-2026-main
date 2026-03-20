#!/usr/bin/env python3
"""
NM i AI 2026 — Oracle/Ceiling Estimator (shared/tools/oracle_sim.py)

Calculates theoretical ceiling per track to focus effort where headroom exists.
If CV max is 0.75, don't chase 0.90. If ML is already at 85% of ceiling, focus elsewhere.

Ceilings:
- CV: Perfect classification on detected boxes = detection-only mAP (your ceiling
  is bounded by detection quality). Also estimates "perfect detector" ceiling.
- ML: Uniform prior score (baseline) vs your predictions (how much better than guessing?)

Usage:
    # CV ceiling analysis from predictions
    python3 shared/tools/oracle_sim.py cv --predictions predictions.json

    # ML ceiling analysis
    python3 shared/tools/oracle_sim.py ml --predictions predictions.json --ground-truth gt.json

    # JSON output
    python3 shared/tools/oracle_sim.py cv --predictions p.json --json

Dependencies: pycocotools, numpy
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
GRID_W, GRID_H, NUM_CLASSES = 40, 40, 6
KL_MULTIPLIER = 3.0


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


def cv_ceiling(predictions: list, gt_dict: dict, holdout_ids: set) -> dict:
    """Calculate CV track ceilings."""
    preds = [p for p in predictions if p["image_id"] in holdout_ids]

    det_gt = {
        "images": gt_dict["images"],
        "categories": [{"id": 0, "name": "object"}],
        "annotations": [{**a, "category_id": 0} for a in gt_dict["annotations"]],
    }
    det_map = score_coco(det_gt, [{**p, "category_id": 0} for p in preds])
    cls_map = score_coco(gt_dict, preds)
    combined = 0.7 * det_map + 0.3 * cls_map

    # Ceiling: perfect classifier on your detected boxes = det_map (approximate)
    # In edge cases with partial coverage, cls_map can exceed det_map,
    # so ceiling is at least your current combined score
    ceiling_combined = max(det_map, combined)
    headroom = max(0, ceiling_combined - combined)
    efficiency = (combined / ceiling_combined * 100) if ceiling_combined > 0 else 0

    return {
        "detection_mAP": round(det_map, 4),
        "classification_mAP": round(cls_map, 4),
        "combined": round(combined, 4),
        "ceiling_combined": round(ceiling_combined, 4),
        "headroom": round(headroom, 4),
        "efficiency_pct": round(efficiency, 1),
        "prediction_count": len(preds),
        "analysis": {
            "detection_is_bottleneck": det_map < 0.5,
            "classification_is_bottleneck": cls_map < det_map * 0.5,
            "recommendation": (
                "Improve detection (more/better bounding boxes)"
                if det_map < 0.5
                else "Improve classification (better category assignment)"
                if cls_map < det_map * 0.5
                else "Both detection and classification are contributing well"
            ),
        },
    }


def ml_ceiling(predictions: list, ground_truth: list | None) -> dict:
    """Calculate ML track ceilings."""
    uniform_kl_estimate = math.log(6)
    uniform_score = max(0, min(100, 100 * math.exp(-KL_MULTIPLIER * uniform_kl_estimate)))

    result = {
        "uniform_baseline_score": round(uniform_score, 1),
        "perfect_score": 100.0,
        "your_score": None,
        "headroom": None,
        "efficiency_pct": None,
        "above_baseline": None,
    }

    if ground_truth is not None and predictions:
        seed_scores = []
        for pred_t, gt_t in zip(predictions, ground_truth):
            weighted_kl_sum = 0.0
            entropy_sum = 0.0
            for y in range(min(GRID_H, len(gt_t))):
                for x in range(min(GRID_W, len(gt_t[y]))):
                    gt_p = gt_t[y][x]
                    pred_p = pred_t[y][x]
                    ent = -sum(p * math.log(p) for p in gt_p if p > 0)
                    if ent <= 0:
                        continue
                    kl = sum(
                        g * math.log(g / max(p, 1e-10))
                        for g, p in zip(gt_p, pred_p)
                        if g > 0
                    )
                    weighted_kl_sum += ent * kl
                    entropy_sum += ent
            wkl = weighted_kl_sum / entropy_sum if entropy_sum > 0 else 0
            seed_score = max(0, min(100, 100 * math.exp(-KL_MULTIPLIER * wkl)))
            seed_scores.append(seed_score)

        avg_score = sum(seed_scores) / len(seed_scores) if seed_scores else 0
        result["your_score"] = round(avg_score, 1)
        result["headroom"] = round(100 - avg_score, 1)
        result["efficiency_pct"] = round(avg_score, 1)
        result["above_baseline"] = round(avg_score - uniform_score, 1)
        result["per_seed_scores"] = [round(s, 1) for s in seed_scores]

    return result


def parse_ml_data(raw) -> list:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in ("predictions", "seeds", "tensors", "data"):
            if key in raw:
                return parse_ml_data(raw[key])
    return raw


def find_repo_root() -> Path:
    cwd = Path.cwd()
    for p in [cwd] + list(cwd.parents):
        if (p / "CLAUDE.md").exists() or (p / "shared").exists():
            return p
    return cwd


def main():
    parser = argparse.ArgumentParser(description="Oracle/Ceiling Estimator per track")
    parser.add_argument("track", choices=["cv", "ml", "all"], help="Track to analyze")
    parser.add_argument("--predictions", help="Predictions JSON")
    parser.add_argument("--ground-truth", help="ML ground truth JSON")
    parser.add_argument("--cv-predictions", help="CV predictions (for 'all' mode)")
    parser.add_argument("--ml-predictions", help="ML predictions (for 'all' mode)")
    parser.add_argument("--ml-ground-truth", help="ML ground truth (for 'all' mode)")
    parser.add_argument("--images-dir", help="CV images directory")
    parser.add_argument("--labels-dir", help="CV YOLO labels directory")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo_root = find_repo_root()
    results = {"timestamp": datetime.now(timezone.utc).isoformat()}

    if args.track in ("cv", "all"):
        cv_preds_path = args.predictions or args.cv_predictions
        if not cv_preds_path:
            print("ERROR: --predictions or --cv-predictions required for CV track")
            raise SystemExit(1)

        images_dir = Path(args.images_dir) if args.images_dir else repo_root / DEFAULT_IMAGES_DIR
        labels_dir = Path(args.labels_dir) if args.labels_dir else repo_root / DEFAULT_LABELS_DIR

        print("CV Track: Building ground truth...")
        gt = build_coco_gt(images_dir, labels_dir)
        holdout_ids = {img["id"] for img in gt["images"]}
        preds = json.loads(Path(cv_preds_path).read_text())
        if not isinstance(preds, list):
            preds = preds.get("predictions", [])

        print("CV Track: Calculating ceilings...")
        results["cv"] = cv_ceiling(preds, gt, holdout_ids)

    if args.track in ("ml", "all"):
        ml_preds_path = args.predictions or args.ml_predictions
        if not ml_preds_path:
            print("ERROR: --predictions or --ml-predictions required for ML track")
            raise SystemExit(1)

        ml_preds = parse_ml_data(json.loads(Path(ml_preds_path).read_text()))
        ml_gt = None
        gt_path = args.ground_truth or args.ml_ground_truth
        if gt_path and Path(gt_path).exists():
            ml_gt = parse_ml_data(json.loads(Path(gt_path).read_text()))

        print("ML Track: Calculating ceilings...")
        results["ml"] = ml_ceiling(ml_preds, ml_gt)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"  Oracle/Ceiling Analysis")
        print(f"{'='*60}")

        if "cv" in results:
            cv = results["cv"]
            print(f"\n  CV Track (NorgesGruppen):")
            print(f"    Detection mAP:        {cv['detection_mAP']:.4f}")
            print(f"    Classification mAP:   {cv['classification_mAP']:.4f}")
            print(f"    Combined score:       {cv['combined']:.4f}")
            print(f"    Ceiling (perfect cls): {cv['ceiling_combined']:.4f}")
            print(f"    Headroom:             {cv['headroom']:.4f}")
            print(f"    Efficiency:           {cv['efficiency_pct']:.1f}%")
            print(f"    Recommendation:       {cv['analysis']['recommendation']}")

        if "ml" in results:
            ml = results["ml"]
            print(f"\n  ML Track (Astar Island):")
            print(f"    Uniform baseline:     {ml['uniform_baseline_score']:.1f} / 100")
            if ml["your_score"] is not None:
                print(f"    Your score:           {ml['your_score']:.1f} / 100")
                print(f"    Above baseline:       +{ml['above_baseline']:.1f}")
                print(f"    Headroom to perfect:  {ml['headroom']:.1f}")
                print(f"    Efficiency:           {ml['efficiency_pct']:.1f}%")
                if ml.get("per_seed_scores"):
                    print(f"    Per-seed:             {ml['per_seed_scores']}")
            else:
                print("    (No ground truth provided, cannot compute your score)")

        print(f"\n{'='*60}\n")

    raise SystemExit(0)


if __name__ == "__main__":
    main()
