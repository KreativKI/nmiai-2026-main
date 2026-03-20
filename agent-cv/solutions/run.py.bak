"""NorgesGruppen Object Detection — Ensemble Submission.

Combines YOLO11m and YOLO26m predictions using Weighted Boxes Fusion.
SAFE IMPORTS ONLY. Blocked modules = instant ban.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from ensemble_boxes import weighted_boxes_fusion


# --- Configuration ---
YOLO11M_MODEL = "best.onnx"         # YOLO11m: output (1, 360, 33600)
YOLO26M_MODEL = "yolo26m_best.onnx" # YOLO26m: output (1, 300, 6) end-to-end
INPUT_SIZE = 1280
CONF_THRESHOLD = 0.10
IOU_THRESHOLD = 0.5
WBF_IOU_THRESHOLD = 0.55


def letterbox(img: np.ndarray, new_shape: int = 1280):
    """Resize image with letterboxing (preserve aspect ratio, pad with gray)."""
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


def postprocess_yolo11(output, scale, pad, orig_h, orig_w, conf_thresh=0.10):
    """YOLO11m output: (1, 4+nc, N) -> list of [x1,y1,x2,y2], scores, labels."""
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
        return np.array([]), np.array([]), np.array([])
    # cx,cy,w,h -> x1,y1,x2,y2 in original coords
    pad_top, pad_left = pad
    x1 = (boxes[:, 0] - boxes[:, 2] / 2 - pad_left) / scale
    y1 = (boxes[:, 1] - boxes[:, 3] / 2 - pad_top) / scale
    x2 = (boxes[:, 0] + boxes[:, 2] / 2 - pad_left) / scale
    y2 = (boxes[:, 1] + boxes[:, 3] / 2 - pad_top) / scale
    x1 = np.clip(x1, 0, orig_w)
    y1 = np.clip(y1, 0, orig_h)
    x2 = np.clip(x2, 0, orig_w)
    y2 = np.clip(y2, 0, orig_h)
    boxes_xyxy = np.stack([x1, y1, x2, y2], axis=1)
    return boxes_xyxy, confidences, class_ids


def postprocess_yolo26(output, scale, pad, orig_h, orig_w, conf_thresh=0.10):
    """YOLO26m end-to-end output: (1, 300, 6) -> [x1,y1,x2,y2,score,class_id]."""
    preds = output[0]  # (300, 6)
    # Filter by confidence
    scores = preds[:, 4]
    mask = scores >= conf_thresh
    preds = preds[mask]
    if len(preds) == 0:
        return np.array([]), np.array([]), np.array([])
    # Boxes are in input image coords, need to undo letterbox
    pad_top, pad_left = pad
    x1 = (preds[:, 0] - pad_left) / scale
    y1 = (preds[:, 1] - pad_top) / scale
    x2 = (preds[:, 2] - pad_left) / scale
    y2 = (preds[:, 3] - pad_top) / scale
    x1 = np.clip(x1, 0, orig_w)
    y1 = np.clip(y1, 0, orig_h)
    x2 = np.clip(x2, 0, orig_w)
    y2 = np.clip(y2, 0, orig_h)
    boxes_xyxy = np.stack([x1, y1, x2, y2], axis=1)
    return boxes_xyxy, preds[:, 4], preds[:, 5].astype(int)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", "--input", type=str, required=True)
    parser.add_argument("--output", type=str, default="/tmp/predictions.json")
    args, _ = parser.parse_known_args()

    input_dir = Path(args.images)
    output_path = Path(args.output)
    model_dir = Path(__file__).parent

    # Load both ONNX models
    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    sess11 = ort.InferenceSession(str(model_dir / YOLO11M_MODEL), providers=providers)
    sess26 = ort.InferenceSession(str(model_dir / YOLO26M_MODEL), providers=providers)
    input_name_11 = sess11.get_inputs()[0].name
    input_name_26 = sess26.get_inputs()[0].name

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

        # Preprocess
        img_lb, scale, pad = letterbox(img, INPUT_SIZE)
        img_rgb = cv2.cvtColor(img_lb, cv2.COLOR_BGR2RGB)
        img_norm = img_rgb.astype(np.float32) / 255.0
        img_batch = np.transpose(img_norm, (2, 0, 1))[np.newaxis, ...]

        # Run YOLO11m
        out11 = sess11.run(None, {input_name_11: img_batch})
        boxes11, scores11, labels11 = postprocess_yolo11(
            out11[0], scale, pad, orig_h, orig_w, CONF_THRESHOLD)

        # Run YOLO26m
        out26 = sess26.run(None, {input_name_26: img_batch})
        boxes26, scores26, labels26 = postprocess_yolo26(
            out26[0], scale, pad, orig_h, orig_w, CONF_THRESHOLD)

        # WBF (Weighted Boxes Fusion) - normalize boxes to [0,1]
        all_boxes = []
        all_scores = []
        all_labels = []
        weights = [2.0, 1.0]  # YOLO11m has higher weight (better mAP)

        for bxs, scs, lbs in [(boxes11, scores11, labels11),
                               (boxes26, scores26, labels26)]:
            if len(bxs) == 0:
                all_boxes.append(np.array([]).reshape(0, 4))
                all_scores.append(np.array([]))
                all_labels.append(np.array([]))
            else:
                # Normalize to [0,1]
                norm_bxs = bxs.copy()
                norm_bxs[:, 0] /= orig_w
                norm_bxs[:, 1] /= orig_h
                norm_bxs[:, 2] /= orig_w
                norm_bxs[:, 3] /= orig_h
                norm_bxs = np.clip(norm_bxs, 0, 1)
                all_boxes.append(norm_bxs.tolist())
                all_scores.append(scs.tolist())
                all_labels.append(lbs.tolist())

        if any(len(b) > 0 for b in all_boxes):
            fused_boxes, fused_scores, fused_labels = weighted_boxes_fusion(
                all_boxes, all_scores, all_labels,
                weights=weights,
                iou_thr=WBF_IOU_THRESHOLD,
                skip_box_thr=CONF_THRESHOLD,
            )
            # Denormalize
            fused_boxes[:, 0] *= orig_w
            fused_boxes[:, 1] *= orig_h
            fused_boxes[:, 2] *= orig_w
            fused_boxes[:, 3] *= orig_h
            # Convert x1,y1,x2,y2 -> x,y,w,h (COCO)
            for box, score, label in zip(fused_boxes, fused_scores, fused_labels):
                predictions.append({
                    "image_id": image_id,
                    "category_id": int(label),
                    "bbox": [round(float(box[0]), 2), round(float(box[1]), 2),
                             round(float(box[2] - box[0]), 2), round(float(box[3] - box[1]), 2)],
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
