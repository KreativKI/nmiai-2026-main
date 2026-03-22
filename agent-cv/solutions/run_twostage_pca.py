"""NorgesGruppen Object Detection — Two-Stage (YOLO + DINOv2) with PCA Whitening.

Stage 1: YOLO11m detects product bounding boxes (detection mAP, 70% of score)
Stage 2: DINOv2 ViT-S + PCA whitening (320 dims) + kNN (k=10, distance²-weighted)
         reclassifies each crop against product gallery (classification mAP, 30%)

PCA whitening computed at load time from gallery embeddings. Removes noisy
dimensions and decorrelates features. Validated: +5.0% accuracy over raw kNN.

SAFE IMPORTS ONLY. Blocked modules = instant ban.
"""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort


# --- Configuration ---
YOLO_MODEL = "best.onnx"
DINO_MODEL = "dinov2_vits.onnx"
GALLERY_FILE = "gallery_rich.npy"
GALLERY_LABELS_FILE = "gallery_rich_labels.json"
YOLO_INPUT_SIZE = 1280
DINO_INPUT_SIZE = 518
CONF_THRESHOLD = 0.25
IOU_THRESHOLD = 0.5
MAX_DETECTIONS = 500
DINO_TOP_K = 10
DINO_BATCH_SIZE = 16
PCA_DIMS = 320


def pca_whiten_fit(embeddings, n_components):
    """Fit PCA whitening on gallery embeddings. Returns whitened gallery + transform params."""
    mean = embeddings.mean(axis=0)
    centered = embeddings - mean
    cov = (centered.T @ centered) / len(centered)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    idx = np.argsort(eigenvalues)[::-1][:n_components]
    components = eigenvectors[:, idx].T
    eigenvals = eigenvalues[idx]
    whitening_matrix = components / np.sqrt(eigenvals[:, np.newaxis] + 1e-8)
    transformed = centered @ whitening_matrix.T
    norms = np.linalg.norm(transformed, axis=1, keepdims=True) + 1e-8
    return transformed / norms, mean, whitening_matrix


def pca_whiten_transform(embeddings, mean, whitening_matrix):
    """Apply pre-fitted PCA whitening to new embeddings."""
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
            area_j = ((cls_boxes[order[1:], 2] - cls_boxes[order[1:], 0]) *
                     (cls_boxes[order[1:], 3] - cls_boxes[order[1:], 1]))
            iou = inter / (area_i + area_j - inter + 1e-6)
            remaining = np.where(iou <= iou_thresh)[0]
            order = order[remaining + 1]
        keep_all.extend(keep)
    idx = np.array(keep_all)
    return boxes[idx], scores[idx], labels[idx]


def preprocess_crop_for_dino(crop_bgr, size=518):
    crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    crop_resized = cv2.resize(crop_rgb, (size, size), interpolation=cv2.INTER_LINEAR)
    crop_float = crop_resized.astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    crop_norm = (crop_float - mean) / std
    return np.transpose(crop_norm, (2, 0, 1)).astype(np.float32)


def classify_crops_batched(dino_session, dino_input_name, crops_bgr, valid_mask,
                           gallery_pca, gallery_labels, yolo_labels,
                           pca_mean, pca_matrix, top_k=10, batch_size=16):
    """Classify crops using batched DINOv2 + PCA whitening + distance²-weighted kNN."""
    n = len(crops_bgr)
    result_labels = yolo_labels.astype(np.int32).copy()

    if n == 0:
        return result_labels

    valid_indices = [i for i in range(n) if valid_mask[i]]
    if not valid_indices:
        return result_labels

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

    # PCA whitening on query embeddings
    embeddings_pca = pca_whiten_transform(embeddings, pca_mean, pca_matrix)

    # kNN in PCA-whitened space
    similarities = embeddings_pca @ gallery_pca.T

    top_k_idx = np.argsort(similarities, axis=1)[:, -top_k:]
    for vi, orig_i in enumerate(valid_indices):
        k_indices = top_k_idx[vi]
        k_sims = similarities[vi, k_indices]
        k_labels = gallery_labels[k_indices]

        # Distance²-weighted voting
        class_votes = {}
        for label, sim in zip(k_labels, k_sims):
            label = int(label)
            weight = max(0.0, float(sim)) ** 2
            class_votes[label] = class_votes.get(label, 0.0) + weight

        result_labels[orig_i] = max(class_votes, key=class_votes.get)

    return result_labels


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

    # Load gallery and compute PCA whitening
    gallery_raw = np.load(str(model_dir / GALLERY_FILE))
    with open(model_dir / GALLERY_LABELS_FILE, "r") as f:
        gallery_labels = np.array(json.load(f), dtype=np.int32)

    gallery_pca, pca_mean, pca_matrix = pca_whiten_fit(gallery_raw, PCA_DIMS)

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

        # Stage 1: YOLO detection
        img_lb, scale, pad = letterbox(img, YOLO_INPUT_SIZE)
        img_rgb = cv2.cvtColor(img_lb, cv2.COLOR_BGR2RGB)
        img_norm = img_rgb.astype(np.float32) / 255.0
        img_batch = np.transpose(img_norm, (2, 0, 1))[np.newaxis, ...]

        yolo_out = yolo_sess.run(None, {yolo_input: img_batch})
        boxes, det_scores, yolo_labels = decode_yolo(
            yolo_out[0], scale, pad, orig_h, orig_w, CONF_THRESHOLD)

        if len(boxes) == 0:
            continue

        boxes, det_scores, yolo_labels = nms_per_class(
            boxes, det_scores, yolo_labels, IOU_THRESHOLD)

        if len(det_scores) > MAX_DETECTIONS:
            top_idx = np.argsort(det_scores)[-MAX_DETECTIONS:]
            boxes = boxes[top_idx]
            det_scores = det_scores[top_idx]
            yolo_labels = yolo_labels[top_idx]

        # Stage 2: Crop, embed with DINOv2, PCA whiten, kNN classify
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

        dino_labels = classify_crops_batched(
            dino_sess, dino_input, crops, valid_mask,
            gallery_pca, gallery_labels, yolo_labels,
            pca_mean, pca_matrix, DINO_TOP_K, DINO_BATCH_SIZE)

        for i, (box, score) in enumerate(zip(boxes, det_scores)):
            x1, y1, x2, y2 = box
            predictions.append({
                "image_id": image_id,
                "category_id": int(dino_labels[i]),
                "bbox": [round(float(x1), 2), round(float(y1), 2),
                         round(float(x2 - x1), 2), round(float(y2 - y1), 2)],
                "score": round(float(score), 4),
            })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(predictions, f)

    print(f"Wrote {len(predictions)} predictions for {len(image_files)} images")


if __name__ == "__main__":
    main()
