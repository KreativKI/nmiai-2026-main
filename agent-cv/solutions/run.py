"""NorgesGruppen Object Detection — YOLO11m Only.

Single-stage detection: YOLO detects and classifies products.
No DINOv2, no SAHI. Fast, reliable.

SAFE IMPORTS ONLY. Blocked modules = instant ban.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort


YOLO_MODEL = "best.onnx"
YOLO_INPUT_SIZE = 1280
CONF_THRESHOLD = 0.25
IOU_THRESHOLD = 0.5
MAX_DETECTIONS = 500


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", "--input", type=str, required=True)
    parser.add_argument("--output", type=str, default="/tmp/predictions.json")
    args, _ = parser.parse_known_args()

    input_dir = Path(args.images)
    output_path = Path(args.output)
    model_dir = Path(__file__).parent

    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    yolo_sess = ort.InferenceSession(str(model_dir / YOLO_MODEL), providers=providers)
    yolo_input = yolo_sess.get_inputs()[0].name

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

        img_lb, scale, pad = letterbox(img, YOLO_INPUT_SIZE)
        img_rgb = cv2.cvtColor(img_lb, cv2.COLOR_BGR2RGB)
        img_norm = img_rgb.astype(np.float32) / 255.0
        img_batch = np.transpose(img_norm, (2, 0, 1))[np.newaxis, ...]

        yolo_out = yolo_sess.run(None, {yolo_input: img_batch})
        boxes, scores, labels = decode_yolo(
            yolo_out[0], scale, pad, orig_h, orig_w, CONF_THRESHOLD)

        if len(boxes) == 0:
            continue

        boxes, scores, labels = nms_per_class(boxes, scores, labels, IOU_THRESHOLD)

        if len(scores) > MAX_DETECTIONS:
            top_idx = np.argsort(scores)[-MAX_DETECTIONS:]
            boxes = boxes[top_idx]
            scores = scores[top_idx]
            labels = labels[top_idx]

        for box, score, label in zip(boxes, scores, labels):
            x1, y1, x2, y2 = box
            predictions.append({
                "image_id": image_id,
                "category_id": int(label),
                "bbox": [round(float(x1), 2), round(float(y1), 2),
                         round(float(x2 - x1), 2), round(float(y2 - y1), 2)],
                "score": round(float(score), 4),
            })

    parent = output_path.parent
    if not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(predictions, f)

    print(f"Wrote {len(predictions)} predictions for {len(image_files)} images")


if __name__ == "__main__":
    main()
