"""NorgesGruppen Object Detection -- Multi-Scale YOLO + WBF + Pre-Trained SVC.

Stage 1: YOLO11m at TWO scales (1x and 1.5x), merged with Weighted Boxes Fusion.
         Multi-scale catches small products the single-pass misses.
         WBF averages overlapping boxes for tighter localization.
Stage 2: DINOv2 ViT-S + pre-computed PCA whitening + pre-computed LinearSVC.
         Zero runtime training cost (saves ~49s for the second YOLO pass).

Why this works:
- SAHI was tested before as YOLO-only (weak classifier). It HURT because
  more detections with wrong class labels = noise.
- Now those extra detections get reclassified by DINOv2+SVC.
  More recall from multi-scale + correct classification from SVC = net gain.
- 47s saved by pre-trained SVC pays for the second YOLO pass.

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
YOLO_INPUT_SIZE = 1280
DINO_INPUT_SIZE = 518
CONF_THRESHOLD = 0.10       # Lower than single-scale (WBF handles noise)
IOU_THRESHOLD = 0.6
WBF_IOU_THRESHOLD = 0.55    # WBF merge threshold
MAX_DETECTIONS = 500
DINO_BATCH_SIZE = 16
CROP_PAD_RATIO = 0.1
UPSCALE_FACTOR = 1.5        # Second pass: 1.5x zoom

# Pre-computed classifier files
PCA_MEAN_FILE = "pca_mean.npy"
PCA_MATRIX_FILE = "pca_matrix.npy"
SVC_COEF_FILE = "svc_coef.npy"
SVC_INTERCEPT_FILE = "svc_intercept.npy"
SVC_CLASSES_FILE = "svc_classes.npy"


def pca_whiten_transform(embeddings, mean, whitening_matrix):
    """Apply pre-computed PCA whitening."""
    centered = embeddings - mean
    transformed = centered @ whitening_matrix.T
    norms = np.linalg.norm(transformed, axis=1, keepdims=True) + 1e-8
    return transformed / norms


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

    coords = np.stack([x1, y1, x2, y2], axis=1)
    coords[:, [0, 2]] = np.clip(coords[:, [0, 2]], 0, orig_w)
    coords[:, [1, 3]] = np.clip(coords[:, [1, 3]], 0, orig_h)

    return coords, confidences, class_ids


def run_yolo_single(img, yolo_sess, yolo_input_name, orig_h, orig_w, conf_thresh):
    """Run YOLO on a single image. Returns boxes in original coords."""
    img_lb, scale, pad = letterbox(img, YOLO_INPUT_SIZE)
    img_rgb = cv2.cvtColor(img_lb, cv2.COLOR_BGR2RGB)
    img_norm = img_rgb.astype(np.float32) / 255.0
    img_batch = np.transpose(img_norm, (2, 0, 1))[np.newaxis, ...]
    yolo_out = yolo_sess.run(None, {yolo_input_name: img_batch})
    return decode_yolo(yolo_out[0], scale, pad, orig_h, orig_w, conf_thresh)


def multiscale_detect_wbf(img, yolo_sess, yolo_input_name, orig_h, orig_w):
    """Run YOLO at two scales, merge with Weighted Boxes Fusion."""
    # Pass 1: Original resolution
    boxes1, scores1, labels1 = run_yolo_single(
        img, yolo_sess, yolo_input_name, orig_h, orig_w, CONF_THRESHOLD)

    # Pass 2: Upscaled image (catches small products)
    up_h, up_w = int(orig_h * UPSCALE_FACTOR), int(orig_w * UPSCALE_FACTOR)
    img_up = cv2.resize(img, (up_w, up_h), interpolation=cv2.INTER_LINEAR)
    boxes2, scores2, labels2 = run_yolo_single(
        img_up, yolo_sess, yolo_input_name, up_h, up_w, CONF_THRESHOLD)

    # Scale pass-2 boxes back to original coords
    if len(boxes2) > 0:
        boxes2 = boxes2 / UPSCALE_FACTOR

    # If one pass has no detections, return the other
    if len(boxes1) == 0 and len(boxes2) == 0:
        return np.zeros((0, 4)), np.array([]), np.array([])
    if len(boxes1) == 0:
        return boxes2, scores2, labels2
    if len(boxes2) == 0:
        return boxes1, scores1, labels1

    # WBF needs boxes normalized to [0, 1] and grouped per model
    # boxes_list: list of lists of [x1, y1, x2, y2] normalized
    # scores_list: list of lists of confidence scores
    # labels_list: list of lists of integer labels

    def normalize_boxes(boxes, h, w):
        normed = boxes.copy().astype(np.float64)
        normed[:, [0, 2]] /= w
        normed[:, [1, 3]] /= h
        normed = np.clip(normed, 0, 1)
        return normed.tolist()

    boxes_list = [
        normalize_boxes(boxes1, orig_h, orig_w),
        normalize_boxes(boxes2, orig_h, orig_w),
    ]
    scores_list = [scores1.tolist(), scores2.tolist()]
    labels_list = [labels1.astype(int).tolist(), labels2.astype(int).tolist()]

    fused_boxes, fused_scores, fused_labels = weighted_boxes_fusion(
        boxes_list, scores_list, labels_list,
        iou_thr=WBF_IOU_THRESHOLD,
        skip_box_thr=CONF_THRESHOLD,
    )

    # Denormalize back to pixel coords
    if len(fused_boxes) > 0:
        fused_boxes = np.array(fused_boxes)
        fused_boxes[:, [0, 2]] *= orig_w
        fused_boxes[:, [1, 3]] *= orig_h
    else:
        fused_boxes = np.zeros((0, 4))

    fused_scores = np.array(fused_scores)
    fused_labels = np.array(fused_labels, dtype=np.int32)

    # Cap detections
    if len(fused_scores) > MAX_DETECTIONS:
        top_idx = np.argsort(fused_scores)[-MAX_DETECTIONS:]
        fused_boxes = fused_boxes[top_idx]
        fused_scores = fused_scores[top_idx]
        fused_labels = fused_labels[top_idx]

    return fused_boxes, fused_scores, fused_labels


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
    """Classify using pre-trained PCA + SVC. No runtime training."""
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

    # Batched DINOv2 inference
    all_embeddings = []
    for batch_start in range(0, len(preprocessed), batch_size):
        batch = np.stack(preprocessed[batch_start:batch_start + batch_size])
        embs = dino_session.run(None, {dino_input_name: batch})[0]
        norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-8
        all_embeddings.append(embs / norms)

    embeddings = np.concatenate(all_embeddings, axis=0)
    embeddings_pca = pca_whiten_transform(embeddings, pca_mean, pca_matrix)

    # Manual SVC prediction using pre-computed weights
    decision = embeddings_pca @ svc_coef.T + svc_intercept
    predicted_idx = np.argmax(decision, axis=1)
    predicted = svc_classes[predicted_idx]

    # Confidence from decision function
    cls_confidence = decision.max(axis=1)
    cls_confidence = 1.0 / (1.0 + np.exp(-cls_confidence))

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

    # Load models
    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    yolo_sess = ort.InferenceSession(str(model_dir / YOLO_MODEL), providers=providers)
    dino_sess = ort.InferenceSession(str(model_dir / DINO_MODEL), providers=providers)
    yolo_input = yolo_sess.get_inputs()[0].name
    dino_input = dino_sess.get_inputs()[0].name

    # Load pre-computed classifier (NO runtime training!)
    pca_mean = np.load(str(model_dir / PCA_MEAN_FILE))
    pca_matrix = np.load(str(model_dir / PCA_MATRIX_FILE))
    svc_coef = np.load(str(model_dir / SVC_COEF_FILE))
    svc_intercept = np.load(str(model_dir / SVC_INTERCEPT_FILE))
    svc_classes = np.load(str(model_dir / SVC_CLASSES_FILE))

    print(f"Pre-trained classifier: {len(svc_classes)} classes, coef {svc_coef.shape}")
    print(f"Multi-scale: 1x + {UPSCALE_FACTOR}x, WBF IoU={WBF_IOU_THRESHOLD}")

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

        # Stage 1: Multi-scale YOLO + WBF
        boxes, det_scores, yolo_labels = multiscale_detect_wbf(
            img, yolo_sess, yolo_input, orig_h, orig_w)

        if len(boxes) == 0:
            continue

        # Stage 2: Crop with padding, embed, classify with pre-trained SVC
        crops = []
        valid_mask = []
        for box in boxes:
            bx1, by1, bx2, by2 = box
            bw = bx2 - bx1
            bh = by2 - by1
            pad_x = bw * CROP_PAD_RATIO
            pad_y = bh * CROP_PAD_RATIO
            x1 = max(0, int(bx1 - pad_x))
            y1 = max(0, int(by1 - pad_y))
            x2 = min(orig_w, int(bx2 + pad_x))
            y2 = min(orig_h, int(by2 + pad_y))
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
