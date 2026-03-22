"""Quick eval: centroid classifier with PCA whitening.

Tests centroid classification accuracy on training crops.
"""
import argparse
import json
import random
from pathlib import Path
from collections import defaultdict

import cv2
import numpy as np
import onnxruntime as ort

DINO_INPUT_SIZE = 518


def preprocess_crop(crop_bgr, size=518):
    crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    crop_resized = cv2.resize(crop_rgb, (size, size), interpolation=cv2.INTER_LINEAR)
    crop_float = crop_resized.astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    crop_norm = (crop_float - mean) / std
    return np.transpose(crop_norm, (2, 0, 1))[np.newaxis, ...].astype(np.float32)


def pca_whiten_fit(embeddings, n_components):
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
    centered = embeddings - mean
    transformed = centered @ whitening_matrix.T
    norms = np.linalg.norm(transformed, axis=1, keepdims=True) + 1e-8
    return transformed / norms


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--annotations", required=True)
    parser.add_argument("--images", required=True)
    parser.add_argument("--dino-model", required=True)
    parser.add_argument("--gallery", required=True)
    parser.add_argument("--gallery-labels", required=True)
    parser.add_argument("--max-crops", type=int, default=2000)
    parser.add_argument("--pca-dims", type=int, default=384)
    args = parser.parse_args()

    with open(args.annotations) as f:
        coco = json.load(f)
    img_dir = Path(args.images)
    img_lookup = {img["id"]: img["file_name"] for img in coco["images"]}

    gallery = np.load(args.gallery)
    with open(args.gallery_labels) as f:
        gallery_labels = np.array(json.load(f), dtype=np.int32)

    # PCA whiten gallery
    gallery_pca, pca_mean, pca_matrix = pca_whiten_fit(gallery, args.pca_dims)

    # Build centroids
    unique_labels = np.unique(gallery_labels)
    centroids = np.zeros((len(unique_labels), gallery_pca.shape[1]), dtype=np.float32)
    centroid_labels = np.zeros(len(unique_labels), dtype=np.int32)
    for i, label in enumerate(unique_labels):
        mask = gallery_labels == label
        centroid = gallery_pca[mask].mean(axis=0)
        centroid = centroid / (np.linalg.norm(centroid) + 1e-8)
        centroids[i] = centroid
        centroid_labels[i] = label
    print(f"Built {len(centroids)} centroids from {gallery.shape[0]} gallery entries")

    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    dino_sess = ort.InferenceSession(args.dino_model, providers=providers)
    dino_input = dino_sess.get_inputs()[0].name

    anns = [a for a in coco["annotations"]
            if a["bbox"][2] >= 10 and a["bbox"][3] >= 10]
    random.seed(42)
    if len(anns) > args.max_crops:
        anns = random.sample(anns, args.max_crops)

    img_cache = {}
    correct = 0
    total = 0
    per_cat_correct = defaultdict(int)
    per_cat_total = defaultdict(int)

    for i, ann in enumerate(anns):
        img_id = ann["image_id"]
        gt_cat = ann["category_id"]
        x, y, w, h = int(ann["bbox"][0]), int(ann["bbox"][1]), int(ann["bbox"][2]), int(ann["bbox"][3])

        if img_id not in img_cache:
            fname = img_lookup.get(img_id)
            if not fname:
                continue
            img_path = img_dir / fname
            if not img_path.exists():
                continue
            img_cache[img_id] = cv2.imread(str(img_path))

        img = img_cache[img_id]
        if img is None:
            continue

        ih, iw = img.shape[:2]
        # Add 10% padding
        pad_x = int(w * 0.1)
        pad_y = int(h * 0.1)
        x1 = max(0, x - pad_x)
        y1 = max(0, y - pad_y)
        x2 = min(iw, x + w + pad_x)
        y2 = min(ih, y + h + pad_y)
        if x2 - x1 < 10 or y2 - y1 < 10:
            continue

        crop = img[y1:y2, x1:x2]
        inp = preprocess_crop(crop, DINO_INPUT_SIZE)
        emb = dino_sess.run(None, {dino_input: inp})[0].flatten()
        emb = emb / (np.linalg.norm(emb) + 1e-8)

        emb_pca = pca_whiten_transform(emb.reshape(1, -1), pca_mean, pca_matrix)
        sims = emb_pca @ centroids.T
        pred_cat = int(centroid_labels[np.argmax(sims)])

        per_cat_total[gt_cat] += 1
        if pred_cat == gt_cat:
            correct += 1
            per_cat_correct[gt_cat] += 1

        total += 1
        if (i + 1) % 500 == 0:
            print(f"  {i+1}/{len(anns)}: accuracy={correct/total:.4f}")

    acc = correct / total if total > 0 else 0
    cat_accs = [per_cat_correct.get(c, 0) / per_cat_total[c] for c in per_cat_total]
    mean_cat = np.mean(cat_accs)

    print(f"\n=== CENTROID RESULTS (PCA {args.pca_dims}d, 10% padding) ===")
    print(f"Overall accuracy: {correct}/{total} = {acc:.4f}")
    print(f"Mean per-category accuracy: {mean_cat:.4f}")

    # Compare to kNN baseline
    print(f"\nComparison:")
    print(f"  kNN k=5 no-PCA:        0.7840 / 0.8228")
    print(f"  kNN k=10 PCA-320 dist²: 0.8340 / 0.9056")
    print(f"  Centroid PCA-{args.pca_dims} +pad:  {acc:.4f} / {mean_cat:.4f}")


if __name__ == "__main__":
    main()
