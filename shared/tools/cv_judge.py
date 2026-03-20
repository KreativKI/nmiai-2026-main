#!/usr/bin/env python3
"""
NM i AI 2026 — CV QC Judge (shared/tools/cv_judge.py)

Scores a CV submission exactly like the competition, BEFORE uploading.
Prevents wasting limited submission slots on regressions.

Competition scoring: final_score = 0.7 * detection_mAP + 0.3 * classification_mAP

Detection mAP:  All category_ids set to 0 (location-only evaluation)
Classification mAP: Real category_ids (location + correct product)

Usage:
    # Score a submission ZIP against holdout set
    python3 shared/tools/cv_judge.py path/to/submission.zip

    # Specify custom data paths
    python3 shared/tools/cv_judge.py submission.zip \
        --images-dir agent-cv/data/yolo_dataset/images/train \
        --labels-dir agent-cv/data/yolo_dataset/labels/train

    # Score predictions.json directly (skip ZIP extraction + run.py)
    python3 shared/tools/cv_judge.py --predictions-json path/to/predictions.json

    # JSON output for dashboard
    python3 shared/tools/cv_judge.py submission.zip --json

Dependencies: pycocotools, numpy, Pillow (all pre-installed in competition sandbox)
"""

import argparse
import contextlib
import io
import json
import re
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

try:
    import numpy as np
    from pycocotools.coco import COCO
    from pycocotools.cocoeval import COCOeval
except ImportError:
    print("ERROR: pycocotools and numpy required. Install: pip install pycocotools numpy")
    raise SystemExit(1)

# Paths relative to repo root (defaults)
DEFAULT_IMAGES_DIR = "agent-cv/data/yolo_dataset/images/train"
DEFAULT_LABELS_DIR = "agent-cv/data/yolo_dataset/labels/train"
RESULTS_FILE = "shared/tools/cv_results.json"

# Holdout split: image_id % 5 == 0
HOLDOUT_MOD = 5
HOLDOUT_REMAINDER = 0


def extract_image_id(filename: str) -> int | None:
    """Extract numeric ID from img_XXXXX.jpg/jpeg filename."""
    m = re.search(r"img_(\d+)", Path(filename).stem)
    return int(m.group(1)) if m else None


def get_image_dimensions(image_path: Path) -> tuple[int, int]:
    """Get image width and height."""
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            return img.width, img.height
    except ImportError:
        return 2000, 2000  # Conservative fallback


def build_coco_ground_truth(images_dir: Path, labels_dir: Path) -> dict:
    """Convert YOLO labels to COCO format for the holdout split.

    YOLO format: class_id center_x center_y width height (all normalized 0-1)
    COCO format: [x, y, width, height] in pixels (top-left corner)
    """
    images = []
    annotations = []
    categories = set()
    ann_id = 1

    image_files = sorted(images_dir.iterdir())

    for img_path in image_files:
        if img_path.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            continue

        image_id = extract_image_id(img_path.name)
        if image_id is None:
            continue

        # Only holdout images
        if image_id % HOLDOUT_MOD != HOLDOUT_REMAINDER:
            continue

        img_w, img_h = get_image_dimensions(img_path)

        images.append({
            "id": image_id,
            "file_name": img_path.name,
            "width": img_w,
            "height": img_h,
        })

        # Find matching label file
        label_path = labels_dir / f"{img_path.stem}.txt"
        if not label_path.exists():
            continue

        for line in label_path.read_text().strip().splitlines():
            parts = line.strip().split()
            if len(parts) < 5:
                continue

            cls_id = int(parts[0])
            cx, cy, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])

            # Convert normalized YOLO to pixel COCO format
            x = (cx - w / 2) * img_w
            y = (cy - h / 2) * img_h
            bw = w * img_w
            bh = h * img_h

            categories.add(cls_id)
            annotations.append({
                "id": ann_id,
                "image_id": image_id,
                "category_id": cls_id,
                "bbox": [round(x, 2), round(y, 2), round(bw, 2), round(bh, 2)],
                "area": round(bw * bh, 2),
                "iscrowd": 0,
            })
            ann_id += 1

    coco_dict = {
        "images": images,
        "annotations": annotations,
        "categories": [{"id": c, "name": str(c)} for c in sorted(categories)],
    }

    return coco_dict


def filter_holdout_predictions(predictions: list, holdout_ids: set) -> list:
    """Keep only predictions for holdout images."""
    return [p for p in predictions if p["image_id"] in holdout_ids]


def score_with_coco(gt_dict: dict, predictions: list) -> float:
    """Run pycocotools COCO evaluation and return mAP@0.5."""
    if not predictions:
        return 0.0

    # Write GT to temp file (pycocotools needs a file path)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(gt_dict, f)
        gt_path = f.name

    try:
        # Suppress all pycocotools stdout noise
        with contextlib.redirect_stdout(io.StringIO()):
            coco_gt = COCO(gt_path)
            coco_dt = coco_gt.loadRes(predictions)

            evaluator = COCOeval(coco_gt, coco_dt, "bbox")
            # Use default IoU thresholds (0.5:0.05:0.95) for numpy compatibility
            evaluator.evaluate()
            evaluator.accumulate()
            evaluator.summarize()

        # stats[1] = mAP@IoU=0.5 (standard COCO metric ordering)
        return float(evaluator.stats[1])
    finally:
        Path(gt_path).unlink(missing_ok=True)


def compute_detection_map(gt_dict: dict, predictions: list) -> float:
    """Detection mAP: set all category_ids to 0 (location-only)."""
    det_gt = {
        "images": gt_dict["images"],
        "categories": [{"id": 0, "name": "object"}],
        "annotations": [
            {**ann, "category_id": 0} for ann in gt_dict["annotations"]
        ],
    }
    det_preds = [{**p, "category_id": 0} for p in predictions]

    return score_with_coco(det_gt, det_preds)


def compute_classification_map(gt_dict: dict, predictions: list) -> float:
    """Classification mAP: real category_ids (location + correct class)."""
    return score_with_coco(gt_dict, predictions)


def run_submission(zip_path: Path, images_dir: Path, holdout_ids: set) -> list | str:
    """Unzip submission and run run.py against holdout images.

    Returns predictions list on success, error string on failure.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Unzip
        with zipfile.ZipFile(str(zip_path), "r") as zf:
            zf.extractall(tmpdir)

        run_py = tmpdir / "run.py"
        if not run_py.exists():
            return "run.py not found in ZIP root"

        # Create holdout images directory with symlinks
        holdout_dir = tmpdir / "holdout_images"
        holdout_dir.mkdir()
        for img_path in images_dir.iterdir():
            img_id = extract_image_id(img_path.name)
            if img_id is not None and img_id in holdout_ids:
                (holdout_dir / img_path.name).symlink_to(img_path.resolve())

        output_path = tmpdir / "predictions.json"

        # WARNING: run.py executes with full user permissions. Only use with your own ZIPs.
        # The competition Docker sandbox is the authoritative safety gate.
        cmd = [
            "python3", str(run_py),
            "--images", str(holdout_dir),
            "--output", str(output_path),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 min local timeout (competition is 5 min)
                cwd=str(tmpdir),
            )
        except subprocess.TimeoutExpired:
            return "run.py timed out after 600 seconds"

        if result.returncode != 0:
            stderr = result.stderr[:1000] if result.stderr else "no stderr"
            return f"run.py failed (exit {result.returncode}): {stderr}"

        if not output_path.exists():
            return f"run.py did not create output file at {output_path}"

        try:
            predictions = json.loads(output_path.read_text())
        except json.JSONDecodeError as e:
            return f"Invalid JSON in predictions: {e}"

        if not isinstance(predictions, list):
            return f"Predictions must be a list, got {type(predictions).__name__}"

        return predictions


def load_previous_results(results_path: Path) -> list:
    """Load previous evaluation results for comparison."""
    if results_path.exists():
        return json.loads(results_path.read_text())
    return []


def save_result(results_path: Path, result: dict):
    """Append result to history file."""
    results_path.parent.mkdir(parents=True, exist_ok=True)
    history = load_previous_results(results_path)
    history.append(result)
    results_path.write_text(json.dumps(history, indent=2))


def determine_verdict(current_score: float, history: list) -> str:
    """SUBMIT if improved, SKIP if worse, RISKY if marginal."""
    if not history:
        return "SUBMIT"

    best_previous = max(h["combined_score"] for h in history)

    if current_score > best_previous + 0.005:
        return "SUBMIT"
    elif current_score < best_previous - 0.005:
        return "SKIP"
    else:
        return "RISKY"


def find_repo_root() -> Path:
    """Walk up from cwd to find the repo root (contains CLAUDE.md or shared/)."""
    cwd = Path.cwd()
    for p in [cwd] + list(cwd.parents):
        if (p / "CLAUDE.md").exists() or (p / "shared").exists():
            return p
    return cwd


def main():
    parser = argparse.ArgumentParser(
        description="CV QC Judge: Score submissions before uploading"
    )
    parser.add_argument("zip_path", nargs="?", help="Path to submission ZIP")
    parser.add_argument(
        "--predictions-json",
        help="Score an existing predictions.json (skip ZIP extraction + run.py)",
    )
    parser.add_argument("--images-dir", help="Path to images directory")
    parser.add_argument("--labels-dir", help="Path to YOLO labels directory")
    parser.add_argument("--json", action="store_true", help="JSON output for dashboard")
    parser.add_argument(
        "--skip-run",
        action="store_true",
        help="Only build GT and validate, don't run run.py",
    )
    args = parser.parse_args()

    if not args.zip_path and not args.predictions_json:
        parser.error("Provide either a ZIP path or --predictions-json")

    repo_root = find_repo_root()

    images_dir = Path(args.images_dir) if args.images_dir else repo_root / DEFAULT_IMAGES_DIR
    labels_dir = Path(args.labels_dir) if args.labels_dir else repo_root / DEFAULT_LABELS_DIR

    if not images_dir.exists():
        print(f"ERROR: Images directory not found: {images_dir}")
        raise SystemExit(1)
    if not labels_dir.exists():
        print(f"ERROR: Labels directory not found: {labels_dir}")
        raise SystemExit(1)

    # Build COCO ground truth from YOLO labels
    print("Building COCO ground truth from YOLO labels (holdout split)...")
    gt_dict = build_coco_ground_truth(images_dir, labels_dir)
    holdout_ids = {img["id"] for img in gt_dict["images"]}

    print(f"  Holdout images: {len(holdout_ids)}")
    print(f"  Ground truth annotations: {len(gt_dict['annotations'])}")
    print(f"  Categories: {len(gt_dict['categories'])}")

    if not holdout_ids:
        print("ERROR: No holdout images found. Check image naming (img_XXXXX.jpg).")
        raise SystemExit(1)

    # Get predictions
    if args.predictions_json:
        pred_path = Path(args.predictions_json)
        if not pred_path.exists():
            print(f"ERROR: Predictions file not found: {pred_path}")
            raise SystemExit(1)
        predictions = json.loads(pred_path.read_text())
        source = str(pred_path)
    elif args.skip_run:
        print("--skip-run: Ground truth built. Exiting.")
        if args.json:
            print(json.dumps({"holdout_images": len(holdout_ids), "annotations": len(gt_dict["annotations"])}))
        raise SystemExit(0)
    else:
        zip_path = Path(args.zip_path)
        if not zip_path.exists():
            print(f"ERROR: ZIP file not found: {zip_path}")
            raise SystemExit(1)

        print(f"\nRunning submission: {zip_path.name}")
        print("  (This may take a few minutes without GPU...)")
        result = run_submission(zip_path, images_dir, holdout_ids)
        if isinstance(result, str):
            print(f"ERROR: {result}")
            raise SystemExit(1)
        predictions = result
        source = str(zip_path)

    # Filter to holdout images only
    predictions = filter_holdout_predictions(predictions, holdout_ids)
    print(f"\nPredictions on holdout: {len(predictions)}")

    if len(predictions) == 0:
        print("WARNING: No predictions for holdout images. Score will be 0.")

    # Compute scores
    print("\nScoring...")
    det_map = compute_detection_map(gt_dict, predictions)
    cls_map = compute_classification_map(gt_dict, predictions)
    combined = 0.7 * det_map + 0.3 * cls_map

    # Load history and determine verdict
    results_path = repo_root / RESULTS_FILE
    history = load_previous_results(results_path)
    verdict = determine_verdict(combined, history)

    # Save this result
    this_result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "detection_mAP": round(det_map, 6),
        "classification_mAP": round(cls_map, 6),
        "combined_score": round(combined, 6),
        "holdout_images": len(holdout_ids),
        "prediction_count": len(predictions),
        "verdict": verdict,
    }
    save_result(results_path, this_result)

    if args.json:
        print(json.dumps(this_result, indent=2))
    else:
        best_prev = max((h["combined_score"] for h in history), default=0)
        delta = combined - best_prev if history else 0

        print(f"\n{'='*55}")
        print(f"  CV QC Judge Results")
        print(f"{'='*55}")
        print(f"  Source:              {source}")
        print(f"  Holdout images:      {len(holdout_ids)}")
        print(f"  Predictions:         {len(predictions)}")
        print()
        print(f"  Detection mAP@0.5:   {det_map:.4f}  (weight: 70%)")
        print(f"  Classification mAP:  {cls_map:.4f}  (weight: 30%)")
        print(f"  Combined score:      {combined:.4f}")
        if history:
            sign = "+" if delta >= 0 else ""
            print(f"  vs previous best:    {sign}{delta:.4f} (was {best_prev:.4f})")
        print()
        print(f"  Verdict: {verdict}")
        if verdict == "SUBMIT":
            print("  Score improved. Safe to submit.")
        elif verdict == "SKIP":
            print("  Score regressed. Do NOT submit.")
        else:
            print("  Marginal change. Review before submitting.")
        print(f"{'='*55}\n")

    raise SystemExit(0 if verdict != "SKIP" else 1)


if __name__ == "__main__":
    main()
