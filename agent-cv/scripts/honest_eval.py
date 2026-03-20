#!/usr/bin/env python3
"""Honest evaluation of YOLO model on proper val split.

Runs YOLO inference on held-out val images, computes detection + classification mAP
using the same scoring as the competition (70% det + 30% cls).

Also checks for category ID mapping issues (off-by-one, etc.)

Usage (on GCP cv-train-1):
    python3 honest_eval.py \
        --model /home/jcfrugaard/cv-train/models/best.onnx \
        --dataset-dir /home/jcfrugaard/cv-train/data/yolo_dataset \
        --annotations /home/jcfrugaard/trainingdata/train/annotations.json
"""

import argparse
import json
import tempfile
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

try:
    import onnxruntime as ort
except ImportError:
    ort = None

try:
    from pycocotools.coco import COCO
    from pycocotools.cocoeval import COCOeval
except ImportError:
    COCO = None


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="Path to best.onnx")
    parser.add_argument("--dataset-dir", required=True, help="Path to yolo_dataset/")
    parser.add_argument("--annotations", help="Path to original COCO annotations.json")
    parser.add_argument("--conf-threshold", type=float, default=0.15)
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    return parser.parse_args()


def letterbox(img, new_shape=1280):
    h, w = img.shape[:2]
    scale = min(new_shape / h, new_shape / w)
    new_h, new_w = int(h * scale), int(w * scale)
    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    pad_h = new_shape - new_h
    pad_w = new_shape - new_w
    top = pad_h // 2
    left = pad_w // 2
    padded = np.full((new_shape, new_shape, 3), 114, dtype=np.uint8)
    padded[top:top + new_h, left:left + new_w] = resized
    return padded, scale, (top, left)


def decode_yolo(output, scale, pad, orig_h, orig_w, conf_thresh):
    preds = output[0].T
    boxes = preds[:, :4]
    scores = preds[:, 4:]
    class_ids = np.argmax(scores, axis=1)
    confidences = np.max(scores, axis=1)

    mask = confidences >= conf_thresh
    boxes, class_ids, confidences = boxes[mask], class_ids[mask], confidences[mask]

    if len(boxes) == 0:
        return [], [], []

    pad_top, pad_left = pad
    x1 = (boxes[:, 0] - boxes[:, 2] / 2 - pad_left) / scale
    y1 = (boxes[:, 1] - boxes[:, 3] / 2 - pad_top) / scale
    x2 = (boxes[:, 0] + boxes[:, 2] / 2 - pad_left) / scale
    y2 = (boxes[:, 1] + boxes[:, 3] / 2 - pad_top) / scale

    x1 = np.clip(x1, 0, orig_w)
    y1 = np.clip(y1, 0, orig_h)
    x2 = np.clip(x2, 0, orig_w)
    y2 = np.clip(y2, 0, orig_h)

    return (
        np.stack([x1, y1, x2, y2], axis=1),
        confidences,
        class_ids,
    )


def nms(boxes, scores, labels, iou_thresh=0.5):
    if len(boxes) == 0:
        return np.zeros((0, 4)), np.array([]), np.array([])
    keep_all = []
    for cls_id in np.unique(labels):
        cls_mask = labels == cls_id
        cls_idx = np.where(cls_mask)[0]
        cls_boxes = boxes[cls_mask]
        cls_scores = scores[cls_mask]
        order = cls_scores.argsort()[::-1]
        keep = []
        while len(order) > 0:
            i = order[0]
            keep.append(cls_idx[i])
            if len(order) == 1:
                break
            xx1 = np.maximum(cls_boxes[i, 0], cls_boxes[order[1:], 0])
            yy1 = np.maximum(cls_boxes[i, 1], cls_boxes[order[1:], 1])
            xx2 = np.minimum(cls_boxes[i, 2], cls_boxes[order[1:], 2])
            yy2 = np.minimum(cls_boxes[i, 3], cls_boxes[order[1:], 3])
            inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
            area_i = (cls_boxes[i, 2] - cls_boxes[i, 0]) * (cls_boxes[i, 3] - cls_boxes[i, 1])
            area_j = (cls_boxes[order[1:], 2] - cls_boxes[order[1:], 0]) * \
                     (cls_boxes[order[1:], 3] - cls_boxes[order[1:], 1])
            iou = inter / (area_i + area_j - inter + 1e-6)
            remaining = np.where(iou <= iou_thresh)[0]
            order = order[remaining + 1]
        keep_all.extend(keep)
    idx = np.array(keep_all)
    return boxes[idx], scores[idx], labels[idx]


def run_yolo_on_val(model_path, val_images_dir, conf_threshold, iou_threshold):
    """Run YOLO inference on all val images, return COCO-format predictions."""
    if ort is None:
        print("ERROR: onnxruntime not installed")
        return []

    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    sess = ort.InferenceSession(str(model_path), providers=providers)
    input_name = sess.get_inputs()[0].name

    predictions = []
    image_files = sorted(val_images_dir.glob("*.jpg"))
    print(f"Running YOLO on {len(image_files)} val images...")

    for img_path in image_files:
        stem = img_path.stem
        try:
            image_id = int(stem.replace("img_", ""))
        except ValueError:
            continue

        img = cv2.imread(str(img_path))
        if img is None:
            continue
        orig_h, orig_w = img.shape[:2]

        img_lb, scale, pad = letterbox(img, 1280)
        img_rgb = cv2.cvtColor(img_lb, cv2.COLOR_BGR2RGB)
        img_norm = img_rgb.astype(np.float32) / 255.0
        img_batch = np.transpose(img_norm, (2, 0, 1))[np.newaxis, ...]

        output = sess.run(None, {input_name: img_batch})
        boxes, scores, labels = decode_yolo(
            output[0], scale, pad, orig_h, orig_w, conf_threshold)

        if len(boxes) == 0:
            continue

        boxes, scores, labels = nms(
            np.array(boxes), np.array(scores), np.array(labels), iou_threshold)

        for box, score, label in zip(boxes, scores, labels):
            x1, y1, x2, y2 = box
            predictions.append({
                "image_id": image_id,
                "category_id": int(label),
                "bbox": [round(float(x1), 2), round(float(y1), 2),
                         round(float(x2 - x1), 2), round(float(y2 - y1), 2)],
                "score": round(float(score), 4),
            })

    print(f"Generated {len(predictions)} predictions")
    return predictions


def build_gt_from_yolo_labels(val_images_dir, val_labels_dir):
    """Build COCO ground truth from YOLO labels for val set."""
    from PIL import Image

    images = []
    annotations = []
    categories = set()
    ann_id = 1

    for img_path in sorted(val_images_dir.glob("*.jpg")):
        stem = img_path.stem
        try:
            image_id = int(stem.replace("img_", ""))
        except ValueError:
            continue

        with Image.open(img_path) as im:
            img_w, img_h = im.size

        images.append({
            "id": image_id,
            "file_name": img_path.name,
            "width": img_w,
            "height": img_h,
        })

        label_file = val_labels_dir / f"{stem}.txt"
        if not label_file.exists():
            continue

        for line in label_file.read_text().strip().splitlines():
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            cls_id = int(parts[0])
            cx, cy, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
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

    return {
        "images": images,
        "annotations": annotations,
        "categories": [{"id": c, "name": str(c)} for c in sorted(categories)],
    }


def score_coco(gt_dict, predictions):
    """Compute mAP@0.5 using pycocotools."""
    import contextlib
    import io

    if not predictions or COCO is None:
        return 0.0

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(gt_dict, f)
        gt_path = f.name

    try:
        with contextlib.redirect_stdout(io.StringIO()):
            coco_gt = COCO(gt_path)
            coco_dt = coco_gt.loadRes(predictions)
            coco_evaluator = COCOeval(coco_gt, coco_dt, "bbox")
            coco_evaluator.evaluate()
            coco_evaluator.accumulate()
            coco_evaluator.summarize()
        return float(coco_evaluator.stats[1])  # mAP@0.5
    finally:
        Path(gt_path).unlink(missing_ok=True)


def check_category_mapping(annotations_path, dataset_yaml_names):
    """Check if YOLO category IDs match COCO annotation IDs."""
    if not annotations_path:
        return

    print("\n" + "=" * 55)
    print("  CATEGORY ID MAPPING CHECK")
    print("=" * 55)

    with open(annotations_path) as f:
        coco = json.load(f)

    coco_cats = {c["id"]: c["name"] for c in coco["categories"]}
    print(f"COCO categories: {len(coco_cats)} (IDs {min(coco_cats)}-{max(coco_cats)})")

    # Check if YOLO names match COCO names at same indices
    mismatches = 0
    for yolo_id, yolo_name in dataset_yaml_names.items():
        if yolo_id in coco_cats:
            coco_name = coco_cats[yolo_id]
            if yolo_name.strip() != coco_name.strip():
                if mismatches < 10:
                    print(f"  MISMATCH at ID {yolo_id}:")
                    print(f"    YOLO:  '{yolo_name}'")
                    print(f"    COCO:  '{coco_name}'")
                mismatches += 1

    if mismatches == 0:
        print("  All category names match between YOLO and COCO")
    else:
        print(f"\n  TOTAL MISMATCHES: {mismatches}")
        print("  WARNING: Category ID mismatch could explain the score gap!")

    # Check for off-by-one
    print(f"\n  YOLO outputs category IDs: 0-{max(dataset_yaml_names.keys())}")
    print(f"  COCO ground truth IDs: {min(coco_cats.keys())}-{max(coco_cats.keys())}")

    # Check annotation statistics
    ann_cats = Counter(a["category_id"] for a in coco["annotations"])
    print(f"\n  Annotation category range: {min(ann_cats.keys())}-{max(ann_cats.keys())}")
    print(f"  Categories with annotations: {len(ann_cats)}")


def main():
    args = parse_args()
    dataset_dir = Path(args.dataset_dir)
    val_images = dataset_dir / "images" / "val"
    val_labels = dataset_dir / "labels" / "val"

    if not val_images.exists():
        print(f"ERROR: {val_images} not found. Run create_val_split.py first.")
        return 1

    val_count = len(list(val_images.glob("*.jpg")))
    if val_count == 0:
        print("ERROR: No images in val set")
        return 1

    print(f"Val set: {val_count} images")

    # Step 1: Check category mapping
    if args.annotations:
        # Parse dataset.yaml names manually (avoiding yaml import)
        yaml_path = dataset_dir / "dataset.yaml"
        names = {}
        if yaml_path.exists():
            in_names = False
            for line in yaml_path.read_text().splitlines():
                if line.strip().startswith("names:"):
                    in_names = True
                    continue
                if in_names and ":" in line:
                    parts = line.strip().split(":", 1)
                    try:
                        idx = int(parts[0].strip())
                        name = parts[1].strip()
                        names[idx] = name
                    except ValueError:
                        in_names = False
            check_category_mapping(args.annotations, names)

    # Step 2: Build ground truth from YOLO val labels
    print("\nBuilding ground truth from val labels...")
    gt_dict = build_gt_from_yolo_labels(val_images, val_labels)
    print(f"  GT images: {len(gt_dict['images'])}")
    print(f"  GT annotations: {len(gt_dict['annotations'])}")
    print(f"  GT categories: {len(gt_dict['categories'])}")

    # Step 3: Run YOLO inference on val images
    predictions = run_yolo_on_val(
        args.model, val_images, args.conf_threshold, args.iou_threshold)

    if not predictions:
        print("ERROR: No predictions generated")
        return 1

    # Filter predictions to val image IDs only
    val_ids = {img["id"] for img in gt_dict["images"]}
    predictions = [p for p in predictions if p["image_id"] in val_ids]
    print(f"Predictions on val set: {len(predictions)}")

    # Step 4: Score - Detection mAP (all categories -> 0)
    print("\nScoring...")
    det_gt = {
        "images": gt_dict["images"],
        "categories": [{"id": 0, "name": "object"}],
        "annotations": [{**a, "category_id": 0} for a in gt_dict["annotations"]],
    }
    det_preds = [{**p, "category_id": 0} for p in predictions]
    det_map = score_coco(det_gt, det_preds)

    # Step 5: Score - Classification mAP (real categories)
    cls_map = score_coco(gt_dict, predictions)

    # Combined
    combined = 0.7 * det_map + 0.3 * cls_map

    print(f"\n{'=' * 55}")
    print(f"  HONEST EVALUATION (proper val split)")
    print(f"{'=' * 55}")
    print(f"  Val images:          {len(gt_dict['images'])}")
    print(f"  Val annotations:     {len(gt_dict['annotations'])}")
    print(f"  Predictions:         {len(predictions)}")
    print()
    print(f"  Detection mAP@0.5:   {det_map:.4f}  (weight: 70%)")
    print(f"  Classification mAP:  {cls_map:.4f}  (weight: 30%)")
    print(f"  Combined score:      {combined:.4f}")
    print()
    print(f"  Leaderboard score:   0.5756")
    print(f"  Gap:                 {combined - 0.5756:+.4f}")
    print(f"{'=' * 55}")

    # Category-level analysis
    pred_cats = Counter(p["category_id"] for p in predictions)
    gt_cats = Counter(a["category_id"] for a in gt_dict["annotations"])
    print(f"\n  Predicted unique categories: {len(pred_cats)}")
    print(f"  GT unique categories: {len(gt_cats)}")
    print(f"  Categories predicted but not in GT: {len(set(pred_cats.keys()) - set(gt_cats.keys()))}")
    print(f"  Categories in GT but not predicted: {len(set(gt_cats.keys()) - set(pred_cats.keys()))}")

    # Save results
    results = {
        "val_images": len(gt_dict["images"]),
        "val_annotations": len(gt_dict["annotations"]),
        "predictions": len(predictions),
        "detection_mAP": round(det_map, 6),
        "classification_mAP": round(cls_map, 6),
        "combined_score": round(combined, 6),
        "leaderboard_score": 0.5756,
        "gap": round(combined - 0.5756, 6),
        "unique_pred_cats": len(pred_cats),
        "unique_gt_cats": len(gt_cats),
    }
    results_path = dataset_dir / "honest_eval_results.json"
    results_path.write_text(json.dumps(results, indent=2))
    print(f"\nResults saved to {results_path}")

    return 0


if __name__ == "__main__":
    exit(main())
