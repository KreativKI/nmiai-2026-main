"""NorgesGruppen Object Detection — DINOv2 Crop-and-Classify.

Two-stage pipeline:
1. YOLO11m detects product bounding boxes
2. DINOv2 ViT-S classifies each crop via kNN against product gallery

SAFE IMPORTS ONLY. Blocked modules = instant ban.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort


# --- Configuration ---
YOLO_MODEL = "best.onnx"
DINO_MODEL = "dinov2_vits.onnx"
GALLERY_FILE = "gallery.npy"
GALLERY_LABELS_FILE = "gallery_labels.json"
YOLO_INPUT_SIZE = 1280
DINO_INPUT_SIZE = 518
CONF_THRESHOLD = 0.05
IOU_THRESHOLD = 0.5


def letterbox(img, new_shape=1280):
    """Resize with letterboxing."""
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


def decode_yolo(output, scale, pad, orig_h, orig_w, conf_thresh=0.05):
    """Decode YOLO11 output to boxes in original coords."""
    preds = output[0].T
    boxes = preds[:, :4]
    scores = preds[:, 4:]
    class_ids = np.argmax(scores, axis=1)
    confidences = np.max(scores, axis=1)

    mask = confidences >= conf_thresh
    boxes = boxes[mask]
    class_ids = class_ids[mask]
    confidences = confidences[mask]

    if len(boxes) == 0:
        return np.zeros((0, 4)), np.array([]), np.array([])

    pad_top, pad_left = pad
    x1 = (boxes[:, 0] - boxes[:, 2] / 2 - pad_left) / scale
    y1 = (boxes[:, 1] - boxes[:, 3] / 2 - pad_top) / scale
    x2 = (boxes[:, 0] + boxes[:, 2] / 2 - pad_left) / scale
    y2 = (boxes[:, 1] + boxes[:, 3] / 2 - pad_top) / scale

    x1 = np.clip(x1, 0, orig_w)
    y1 = np.clip(y1, 0, orig_h)
    x2 = np.clip(x2, 0, orig_w)
    y2 = np.clip(y2, 0, orig_h)

    return np.stack([x1, y1, x2, y2], axis=1), confidences, class_ids


def nms_per_class(boxes, scores, labels, iou_thresh=0.5):
    """Per-class NMS."""
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
    keep_all = np.array(keep_all)
    return boxes[keep_all], scores[keep_all], labels[keep_all]


def preprocess_crop_for_dino(crop_bgr, size=518):
    """Preprocess a crop for DINOv2: resize, normalize with ImageNet stats."""
    crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    crop_resized = cv2.resize(crop_rgb, (size, size), interpolation=cv2.INTER_LINEAR)
    crop_float = crop_resized.astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    crop_norm = (crop_float - mean) / std
    return np.transpose(crop_norm, (2, 0, 1))[np.newaxis, ...].astype(np.float32)


def classify_crops(dino_session, dino_input_name, crops_bgr, gallery, gallery_labels):
    """Classify cropped detections using DINOv2 + kNN against gallery."""
    if len(crops_bgr) == 0:
        return np.array([]), np.array([])

    embeddings = []
    for crop in crops_bgr:
        inp = preprocess_crop_for_dino(crop, DINO_INPUT_SIZE)
        emb = dino_session.run(None, {dino_input_name: inp})[0].flatten()
        emb = emb / (np.linalg.norm(emb) + 1e-8)
        embeddings.append(emb)

    embeddings = np.array(embeddings)
    similarities = embeddings @ gallery.T
    best_idx = np.argmax(similarities, axis=1)
    best_scores = np.max(similarities, axis=1)
    best_labels = gallery_labels[best_idx]

    return best_labels, best_scores


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", "--input", type=str, required=True)
    parser.add_argument("--output", type=str, default="/tmp/predictions.json")
    args, _ = parser.parse_known_args()

    input_dir = Path(args.images)
    output_path = Path(args.output)
    model_dir = Path(__file__).parent

    # Load models
    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    yolo_sess = ort.InferenceSession(str(model_dir / YOLO_MODEL), providers=providers)
    dino_sess = ort.InferenceSession(str(model_dir / DINO_MODEL), providers=providers)
    yolo_input = yolo_sess.get_inputs()[0].name
    dino_input = dino_sess.get_inputs()[0].name

    # Load gallery: .npy for embeddings, .json for labels
    gallery = np.load(str(model_dir / GALLERY_FILE))
    with open(model_dir / GALLERY_LABELS_FILE, "r") as f:
        gallery_labels = np.array(json.load(f), dtype=np.int32)

    predictions = []
    image_files = sorted(input_dir.glob("*.jpg"))

    for img_path in image_files:
        stem = img_path.stem
        try:
            image_id = int(stem.replace("img_", ""))
        except ValueError:
            image_id = hash(stem) % (10**6)

        img = cv2.imread(str(img_path))
        if img is None:
            continue
        orig_h, orig_w = img.shape[:2]

        # Stage 1: YOLO detection
        img_lb, scale, pad = letterbox(img, YOLO_INPUT_SIZE)
        img_rgb = cv2.cvtColor(img_lb, cv2.COLOR_BGR2RGB)
        img_norm = img_rgb.astype(np.float32) / 255.0
        img_batch = np.transpose(img_norm, (2, 0, 1))[np.newaxis, ...]

        yolo_out = yolo_sess.run(None, {yolo_input: img_batch})
        boxes, det_scores, yolo_labels = decode_yolo(
            yolo_out[0], scale, pad, orig_h, orig_w, CONF_THRESHOLD)

        boxes, det_scores, yolo_labels = nms_per_class(
            boxes, det_scores, yolo_labels, IOU_THRESHOLD)

        if len(boxes) == 0:
            continue

        # Stage 2: Crop and classify with DINOv2
        crops = []
        for box in boxes:
            x1, y1, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(orig_w, x2)
            y2 = min(orig_h, y2)
            if x2 - x1 < 5 or y2 - y1 < 5:
                crops.append(np.zeros((10, 10, 3), dtype=np.uint8))
                continue
            crop = img[y1:y2, x1:x2]
            crops.append(crop)

        dino_labels, dino_scores = classify_crops(
            dino_sess, dino_input, crops, gallery, gallery_labels)

        for i, (box, det_score) in enumerate(zip(boxes, det_scores)):
            x1, y1, x2, y2 = box

            if len(dino_labels) > i:
                cat_id = int(dino_labels[i])
                cls_sim = float(dino_scores[i])
                combined_score = float(np.sqrt(det_score * max(cls_sim, 0.01)))
            else:
                cat_id = int(yolo_labels[i])
                combined_score = float(det_score)

            predictions.append({
                "image_id": image_id,
                "category_id": cat_id,
                "bbox": [round(float(x1), 2), round(float(y1), 2),
                         round(float(x2 - x1), 2), round(float(y2 - y1), 2)],
                "score": round(combined_score, 4),
            })

    parent = output_path.parent
    if not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(predictions, f)

    print(f"Wrote {len(predictions)} predictions for {len(image_files)} images")


if __name__ == "__main__":
    main()
