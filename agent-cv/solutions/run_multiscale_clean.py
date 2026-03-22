"""NorgesGruppen Object Detection — Multiscale YOLO + WBF + Pre-trained SVC.

Stage 1: YOLO11m at TWO scales (1280, 1920), fused with Weighted Boxes Fusion
Stage 2: DINOv2 ViT-S + pre-computed PCA whitening + pre-computed LinearSVC
         All classifier params loaded from classifier_params.json.
         Zero runtime training cost (saves ~49s of 300s budget).

SAFE IMPORTS ONLY. Blocked modules = instant ban.
"""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from ensemble_boxes import weighted_boxes_fusion


# --- Configuration ---
YOLO_MODEL = "best.onnx"
DINO_MODEL = "dinov2_vits.onnx"
CLASSIFIER_PARAMS = "classifier_params.json"
YOLO_SCALES = [1280, 1920]
DINO_INPUT_SIZE = 518
CONF_THRESHOLD = 0.15
IOU_THRESHOLD = 0.6
WBF_IOU_THRESHOLD = 0.55
MAX_DETECTIONS = 500
DINO_BATCH_SIZE = 16


def pca_whiten_transform(embeddings, mean, whitening_matrix):
    centered = embeddings - mean
    transformed = centered @ whitening_matrix.T
    norms = np.linalg.norm(transformed, axis=1, keepdims=True) + 1e-8
    return transformed / norms


def letterbox(img, new_shape=1280):
    h, w = img.shape[:2]
    scale = min(new_shape / h, new_shape / w)
    new_h, new_w = int(h * scale), int(w * scale)
    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    top = (new_shape - new_h) // 2
    left = (new_shape - new_w) // 2
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

    coords = np.stack([x1, y1, x2, y2], axis=1)
    coords[:, [0, 2]] = np.clip(coords[:, [0, 2]], 0, orig_w)
    coords[:, [1, 3]] = np.clip(coords[:, [1, 3]], 0, orig_h)

    return coords, confidences, class_ids


def run_yolo_at_scale(yolo_sess, yolo_input, img, orig_h, orig_w, scale_size):
    """Run YOLO inference at a given input scale and return decoded detections."""
    img_lb, scale, pad = letterbox(img, scale_size)
    img_rgb = cv2.cvtColor(img_lb, cv2.COLOR_BGR2RGB)
    img_norm = img_rgb.astype(np.float32) / 255.0
    img_batch = np.transpose(img_norm, (2, 0, 1))[np.newaxis, ...]
    yolo_out = yolo_sess.run(None, {yolo_input: img_batch})
    boxes, scores, labels = decode_yolo(
        yolo_out[0], scale, pad, orig_h, orig_w, CONF_THRESHOLD)
    return boxes, scores, labels


def fuse_multiscale_detections(all_boxes, all_scores, all_labels, orig_h, orig_w):
    """Fuse detections from multiple scales using Weighted Boxes Fusion.

    WBF expects boxes normalized to [0,1] in [x1,y1,x2,y2] format,
    grouped as lists-of-lists (one list per model/scale).
    """
    if all(len(b) == 0 for b in all_boxes):
        return np.zeros((0, 4)), np.array([]), np.array([])

    boxes_list = []
    scores_list = []
    labels_list = []

    for boxes, scores, labels in zip(all_boxes, all_scores, all_labels):
        if len(boxes) == 0:
            boxes_list.append(np.zeros((0, 4)))
            scores_list.append(np.array([]))
            labels_list.append(np.array([]))
            continue
        # Normalize to [0,1]
        norm_boxes = boxes.copy()
        norm_boxes[:, [0, 2]] /= orig_w
        norm_boxes[:, [1, 3]] /= orig_h
        # Clip to [0,1] for safety
        norm_boxes = np.clip(norm_boxes, 0.0, 1.0)
        boxes_list.append(norm_boxes.tolist())
        scores_list.append(scores.tolist())
        labels_list.append(labels.astype(int).tolist())

    fused_boxes, fused_scores, fused_labels = weighted_boxes_fusion(
        boxes_list, scores_list, labels_list,
        iou_thr=WBF_IOU_THRESHOLD,
        skip_box_thr=CONF_THRESHOLD,
    )

    if len(fused_boxes) == 0:
        return np.zeros((0, 4)), np.array([]), np.array([])

    # Denormalize back to pixel coordinates
    fused_boxes[:, [0, 2]] *= orig_w
    fused_boxes[:, [1, 3]] *= orig_h

    return fused_boxes, fused_scores, fused_labels.astype(np.int32)


def preprocess_crop_for_dino(crop_bgr, size=518):
    crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    crop_resized = cv2.resize(crop_rgb, (size, size), interpolation=cv2.INTER_LINEAR)
    crop_float = crop_resized.astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    crop_norm = (crop_float - mean) / std
    return np.transpose(crop_norm, (2, 0, 1)).astype(np.float32)


def classify_crops_pretrained(dino_session, dino_input_name, crops_bgr, valid_mask,
                              yolo_labels, pca_mean, pca_matrix,
                              svc_coef, svc_intercept, svc_classes,
                              batch_size=16):
    n = len(crops_bgr)
    result_labels = yolo_labels.astype(np.int32).copy()
    result_confidence = np.ones(n, dtype=np.float32)

    if n == 0:
        return result_labels, result_confidence

    valid_indices = [i for i in range(n) if valid_mask[i]]
    if not valid_indices:
        return result_labels, result_confidence

    preprocessed = [preprocess_crop_for_dino(crops_bgr[i], DINO_INPUT_SIZE)
                    for i in valid_indices]

    all_embeddings = []
    for batch_start in range(0, len(preprocessed), batch_size):
        batch = np.stack(preprocessed[batch_start:batch_start + batch_size])
        embs = dino_session.run(None, {dino_input_name: batch})[0]
        norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-8
        all_embeddings.append(embs / norms)

    embeddings = np.concatenate(all_embeddings, axis=0)
    embeddings_pca = pca_whiten_transform(embeddings, pca_mean, pca_matrix)

    # SVC prediction: decision = X @ coef.T + intercept
    decision = embeddings_pca @ svc_coef.T + svc_intercept
    predicted_idx = np.argmax(decision, axis=1)
    predicted = svc_classes[predicted_idx]

    # Sigmoid of max decision value for confidence
    cls_confidence = 1.0 / (1.0 + np.exp(-decision.max(axis=1)))

    for vi, orig_i in enumerate(valid_indices):
        result_labels[orig_i] = int(predicted[vi])
        result_confidence[orig_i] = float(cls_confidence[vi])

    return result_labels, result_confidence


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
    dino_sess = ort.InferenceSession(str(model_dir / DINO_MODEL), providers=providers)
    yolo_input = yolo_sess.get_inputs()[0].name
    dino_input = dino_sess.get_inputs()[0].name

    # Load all classifier params from single JSON
    with open(model_dir / CLASSIFIER_PARAMS, "r") as f:
        params = json.load(f)
    pca_mean = np.array(params["pca_mean"], dtype=np.float32)
    pca_matrix = np.array(params["pca_wm"], dtype=np.float32)
    svc_coef = np.array(params["svc_coef"], dtype=np.float32)
    svc_intercept = np.array(params["svc_intercept"], dtype=np.float32)
    svc_classes = np.array(params["svc_classes"], dtype=np.int32)

    predictions = []
    image_files = sorted(
        [f for f in input_dir.iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png")]
    )

    for img_path in image_files:
        stem = img_path.stem
        try:
            image_id = int(stem.replace("img_", ""))
        except ValueError:
            image_id = int(hashlib.md5(stem.encode()).hexdigest(), 16) % (10**6)

        img = cv2.imread(str(img_path))
        if img is None:
            continue
        orig_h, orig_w = img.shape[:2]

        # --- Multiscale YOLO: run at each scale ---
        all_boxes = []
        all_scores = []
        all_labels = []
        for scale_size in YOLO_SCALES:
            boxes, scores, labels = run_yolo_at_scale(
                yolo_sess, yolo_input, img, orig_h, orig_w, scale_size)
            all_boxes.append(boxes)
            all_scores.append(scores)
            all_labels.append(labels)

        # --- Fuse detections with WBF ---
        boxes, det_scores, yolo_labels = fuse_multiscale_detections(
            all_boxes, all_scores, all_labels, orig_h, orig_w)

        if len(boxes) == 0:
            continue

        if len(det_scores) > MAX_DETECTIONS:
            top_idx = np.argsort(det_scores)[-MAX_DETECTIONS:]
            boxes = boxes[top_idx]
            det_scores = det_scores[top_idx]
            yolo_labels = yolo_labels[top_idx]

        crops = []
        valid_mask = []
        for box in boxes:
            x1 = max(0, int(box[0]))
            y1 = max(0, int(box[1]))
            x2 = min(orig_w, int(box[2]))
            y2 = min(orig_h, int(box[3]))
            if x2 - x1 < 5 or y2 - y1 < 5:
                crops.append(np.zeros((10, 10, 3), dtype=np.uint8))
                valid_mask.append(False)
                continue
            crops.append(img[y1:y2, x1:x2])
            valid_mask.append(True)

        dino_labels, cls_conf = classify_crops_pretrained(
            dino_sess, dino_input, crops, valid_mask,
            yolo_labels, pca_mean, pca_matrix,
            svc_coef, svc_intercept, svc_classes, DINO_BATCH_SIZE)

        for i, (box, det_score) in enumerate(zip(boxes, det_scores)):
            x1, y1, x2, y2 = box
            combined_score = float(det_score) * float(cls_conf[i])
            predictions.append({
                "image_id": image_id,
                "category_id": int(dino_labels[i]),
                "bbox": [round(float(x1), 2), round(float(y1), 2),
                         round(float(x2 - x1), 2), round(float(y2 - y1), 2)],
                "score": round(combined_score, 4),
            })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(predictions, f)

    print(f"Wrote {len(predictions)} predictions for {len(image_files)} images")


if __name__ == "__main__":
    main()
