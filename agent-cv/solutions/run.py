"""NorgesGruppen Object Detection — Competition Submission.

SAFE IMPORTS ONLY. Blocked modules = instant ban.
Uses ONNX Runtime for inference, pathlib for file I/O, json for output.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort


# --- Configuration ---
MODEL_NAME = "best.onnx"
INPUT_SIZE = 1280          # Must match training/export imgsz
CONF_THRESHOLD = 0.15      # Low threshold, let mAP calculation handle filtering
IOU_THRESHOLD = 0.5        # NMS IoU threshold
NUM_CLASSES = 356           # IDs 0-355 from training data (model output: 4+356=360 channels)


def letterbox(img: np.ndarray, new_shape: int = 1280):
    """Resize image with letterboxing (preserve aspect ratio, pad with gray)."""
    h, w = img.shape[:2]
    scale = min(new_shape / h, new_shape / w)
    new_h, new_w = int(h * scale), int(w * scale)

    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    # Pad to square
    pad_h = new_shape - new_h
    pad_w = new_shape - new_w
    top = pad_h // 2
    left = pad_w // 2

    padded = np.full((new_shape, new_shape, 3), 114, dtype=np.uint8)
    padded[top:top + new_h, left:left + new_w] = resized

    return padded, scale, (top, left)


def postprocess(output: np.ndarray, scale: float, pad: tuple,
                orig_h: int, orig_w: int,
                conf_thresh: float = 0.15, iou_thresh: float = 0.5):
    """Process YOLO ONNX output to COCO-format predictions.

    YOLO11 output shape: (1, 4+num_classes, num_detections)
    Transpose to (num_detections, 4+num_classes)
    """
    # output shape: (1, 4+nc, N) -> (N, 4+nc)
    preds = output[0].T

    # Split boxes and class scores
    boxes = preds[:, :4]        # cx, cy, w, h (in input image coords)
    scores = preds[:, 4:]       # class scores

    # Get best class per detection
    class_ids = np.argmax(scores, axis=1)
    confidences = np.max(scores, axis=1)

    # Filter by confidence
    mask = confidences >= conf_thresh
    boxes = boxes[mask]
    class_ids = class_ids[mask]
    confidences = confidences[mask]

    if len(boxes) == 0:
        return [], [], []

    # Convert from cx,cy,w,h to x1,y1,x2,y2
    x1 = boxes[:, 0] - boxes[:, 2] / 2
    y1 = boxes[:, 1] - boxes[:, 3] / 2
    x2 = boxes[:, 0] + boxes[:, 2] / 2
    y2 = boxes[:, 1] + boxes[:, 3] / 2

    # Remove letterbox padding and rescale to original image
    pad_top, pad_left = pad
    x1 = (x1 - pad_left) / scale
    y1 = (y1 - pad_top) / scale
    x2 = (x2 - pad_left) / scale
    y2 = (y2 - pad_top) / scale

    # Clip to image bounds
    x1 = np.clip(x1, 0, orig_w)
    y1 = np.clip(y1, 0, orig_h)
    x2 = np.clip(x2, 0, orig_w)
    y2 = np.clip(y2, 0, orig_h)

    # Convert to COCO format: [x, y, width, height]
    bboxes_coco = np.stack([x1, y1, x2 - x1, y2 - y1], axis=1)

    # NMS per class
    keep_indices = []
    for cls_id in np.unique(class_ids):
        cls_mask = class_ids == cls_id
        cls_indices = np.where(cls_mask)[0]
        cls_boxes_xyxy = np.stack([x1[cls_mask], y1[cls_mask],
                                   x2[cls_mask], y2[cls_mask]], axis=1)
        cls_scores = confidences[cls_mask]

        # Simple NMS
        order = cls_scores.argsort()[::-1]
        keep = []
        while len(order) > 0:
            i = order[0]
            keep.append(cls_indices[i])

            if len(order) == 1:
                break

            # IoU with remaining
            xx1 = np.maximum(cls_boxes_xyxy[i, 0], cls_boxes_xyxy[order[1:], 0])
            yy1 = np.maximum(cls_boxes_xyxy[i, 1], cls_boxes_xyxy[order[1:], 1])
            xx2 = np.minimum(cls_boxes_xyxy[i, 2], cls_boxes_xyxy[order[1:], 2])
            yy2 = np.minimum(cls_boxes_xyxy[i, 3], cls_boxes_xyxy[order[1:], 3])

            inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
            area_i = ((cls_boxes_xyxy[i, 2] - cls_boxes_xyxy[i, 0]) *
                      (cls_boxes_xyxy[i, 3] - cls_boxes_xyxy[i, 1]))
            area_j = ((cls_boxes_xyxy[order[1:], 2] - cls_boxes_xyxy[order[1:], 0]) *
                      (cls_boxes_xyxy[order[1:], 3] - cls_boxes_xyxy[order[1:], 1]))
            iou = inter / (area_i + area_j - inter + 1e-6)

            remaining = np.where(iou <= iou_thresh)[0]
            order = order[remaining + 1]

        keep_indices.extend(keep)

    keep_indices = np.array(keep_indices)
    return bboxes_coco[keep_indices], class_ids[keep_indices], confidences[keep_indices]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", "--input", type=str, required=True,
                        help="Path to directory with input images")
    parser.add_argument("--output", type=str, default="/tmp/predictions.json",
                        help="Path to output predictions JSON file")
    # Use parse_known_args to accept any extra arguments the sandbox may pass
    args, _ = parser.parse_known_args()

    input_dir = Path(args.images)
    output_path = Path(args.output)
    model_path = Path(__file__).parent / MODEL_NAME

    # Load ONNX model
    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    session = ort.InferenceSession(str(model_path), providers=providers)
    input_name = session.get_inputs()[0].name

    # Process all images
    predictions = []
    image_files = sorted(input_dir.glob("*.jpg"))

    for img_path in image_files:
        # Extract image_id from filename (img_XXXXX.jpg -> XXXXX)
        stem = img_path.stem
        try:
            image_id = int(stem.replace("img_", ""))
        except ValueError:
            # Fallback: use filename hash
            image_id = hash(stem) % (10**6)

        # Load image
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        orig_h, orig_w = img.shape[:2]

        # Preprocess: letterbox + normalize
        img_lb, scale, pad = letterbox(img, INPUT_SIZE)
        img_rgb = cv2.cvtColor(img_lb, cv2.COLOR_BGR2RGB)
        img_norm = img_rgb.astype(np.float32) / 255.0
        img_batch = np.transpose(img_norm, (2, 0, 1))[np.newaxis, ...]  # NCHW

        # Run inference
        outputs = session.run(None, {input_name: img_batch})

        # Postprocess
        bboxes, class_ids, scores = postprocess(
            outputs[0], scale, pad, orig_h, orig_w,
            conf_thresh=CONF_THRESHOLD, iou_thresh=IOU_THRESHOLD
        )

        # Build predictions
        for bbox, cls_id, score in zip(bboxes, class_ids, scores):
            predictions.append({
                "image_id": image_id,
                "category_id": int(cls_id),
                "bbox": [round(float(x), 2) for x in bbox],
                "score": round(float(score), 4),
            })

    # Write output
    # Ensure parent dir exists (use Path, NOT os)
    parent = output_path.parent
    if not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(predictions, f)

    print(f"Wrote {len(predictions)} predictions for {len(image_files)} images")


if __name__ == "__main__":
    main()
