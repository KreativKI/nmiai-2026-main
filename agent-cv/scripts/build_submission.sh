#!/bin/bash
# Build submission ZIP from retrained model.
# Run on GCP VM after training completes.
#
# Usage: bash build_submission.sh /path/to/best.pt [output_name]

set -e

WEIGHTS="${1:?Usage: build_submission.sh /path/to/best.pt [output_name]}"
NAME="${2:-submission_gemini}"

echo "=== Building submission: ${NAME}.zip ==="

WORK_DIR=$(mktemp -d)
echo "Work dir: $WORK_DIR"

# 1. Export to ONNX if needed
if [[ "$WEIGHTS" == *.pt ]]; then
    echo "Exporting to ONNX..."
    cd ~/cv-train/venv 2>/dev/null || true
    python3 -c "
from ultralytics import YOLO
m = YOLO('${WEIGHTS}')
m.export(format='onnx', imgsz=1280, opset=17, simplify=True)
print('ONNX exported')
"
    ONNX="${WEIGHTS%.pt}.onnx"
else
    ONNX="$WEIGHTS"
fi

# 2. Copy files
cp "$ONNX" "$WORK_DIR/best.onnx"

# 3. Get run.py (YOLO-only version, no DINOv2)
# Use the simple YOLO-only run.py for reliability
cat > "$WORK_DIR/run.py" << 'RUNPY'
"""NorgesGruppen Object Detection — YOLO11m inference."""
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
MAX_DETECTIONS = 300

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

def decode_yolo(output, scale, pad, orig_h, orig_w, conf_thresh=0.25):
    preds = output[0].T
    scores = preds[:, 4:]
    max_scores = scores.max(axis=1)
    mask = max_scores >= conf_thresh
    preds = preds[mask]
    scores = scores[mask]
    max_scores = max_scores[mask]
    class_ids = scores.argmax(axis=1)
    cx = preds[:, 0]
    cy = preds[:, 1]
    w = preds[:, 2]
    h = preds[:, 3]
    x1 = ((cx - w / 2) - pad[1]) / scale
    y1 = ((cy - h / 2) - pad[0]) / scale
    x2 = ((cx + w / 2) - pad[1]) / scale
    y2 = ((cy + h / 2) - pad[0]) / scale
    x1 = np.clip(x1, 0, orig_w)
    y1 = np.clip(y1, 0, orig_h)
    x2 = np.clip(x2, 0, orig_w)
    y2 = np.clip(y2, 0, orig_h)
    boxes = np.stack([x1, y1, x2, y2], axis=1)
    return boxes, max_scores, class_ids

def nms(boxes, scores, iou_threshold=0.5):
    if len(boxes) == 0:
        return []
    x1 = boxes[:, 0]; y1 = boxes[:, 1]
    x2 = boxes[:, 2]; y2 = boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep = []
    while len(order) > 0:
        i = order[0]
        keep.append(i)
        if len(order) == 1:
            break
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
        inds = np.where(iou <= iou_threshold)[0]
        order = order[inds + 1]
    return keep

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    images_dir = Path(args.images)
    output_path = Path(args.output)
    script_dir = Path(__file__).parent
    model_path = str(script_dir / YOLO_MODEL)
    session = ort.InferenceSession(model_path, providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    image_files = sorted([f for f in images_dir.iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png")])
    results = []
    for img_path in image_files:
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        orig_h, orig_w = img.shape[:2]
        padded, scale, pad = letterbox(img, YOLO_INPUT_SIZE)
        blob = padded.astype(np.float32) / 255.0
        blob = blob.transpose(2, 0, 1)[np.newaxis]
        output = session.run(None, {input_name: blob})
        boxes, scores, class_ids = decode_yolo(output, scale, pad, orig_h, orig_w, CONF_THRESHOLD)
        if len(boxes) > 0:
            keep = nms(boxes, scores, IOU_THRESHOLD)
            boxes = boxes[keep][:MAX_DETECTIONS]
            scores = scores[keep][:MAX_DETECTIONS]
            class_ids = class_ids[keep][:MAX_DETECTIONS]
            for box, score, cls_id in zip(boxes, scores, class_ids):
                x1, y1, x2, y2 = box
                results.append({
                    "image_id": img_path.stem,
                    "category_id": int(cls_id),
                    "bbox": [float(x1), float(y1), float(x2 - x1), float(y2 - y1)],
                    "score": float(score),
                })
    with open(output_path, "w") as f:
        json.dump(results, f)

if __name__ == "__main__":
    main()
RUNPY

# 4. Validate
echo "Files in ZIP:"
ls -lh "$WORK_DIR/"

echo ""
echo "Checking blocked imports..."
if grep -rn "import os\b\|import sys\b\|import subprocess\|import socket\|import pickle\|import yaml\b\|import requests\b\|import shutil\b" "$WORK_DIR/run.py"; then
    echo "BLOCKED IMPORT FOUND! Aborting."
    exit 1
fi
echo "No blocked imports."

# 5. Build ZIP
cd "$WORK_DIR"
zip -r ~/"${NAME}.zip" run.py best.onnx
echo ""
echo "=== ZIP created: ~/${NAME}.zip ==="
ls -lh ~/"${NAME}.zip"

# 6. Validate with cv_pipeline if available
if [ -f ~/shared/tools/validate_cv_zip.py ]; then
    python3 ~/shared/tools/validate_cv_zip.py ~/"${NAME}.zip"
fi

echo ""
echo "Ready for JC to upload."
