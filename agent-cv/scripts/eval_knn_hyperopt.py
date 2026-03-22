"""Grid search kNN hyperparameters: k, PCA dimensions, distance weighting.

Tests combinations on training crops and reports classification accuracy.

Usage:
  python eval_knn_hyperopt.py \
    --annotations ~/trainingdata/train/annotations.json \
    --images ~/trainingdata/train/images/ \
    --dino-model ~/dinov2_vits.onnx \
    --gallery ~/gallery_output/gallery_rich.npy \
    --gallery-labels ~/gallery_output/gallery_rich_labels.json \
    --max-crops 2000
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


def knn_classify(query_emb, gallery, gallery_labels, top_k=5, weighted=False):
    similarities = query_emb @ gallery.T
    top_k_idx = np.argsort(similarities)[-top_k:]
    k_sims = similarities[top_k_idx]
    k_labels = gallery_labels[top_k_idx]

    class_votes = {}
    for label, sim in zip(k_labels, k_sims):
        label = int(label)
        if weighted:
            # Distance-weighted: higher similarity = stronger vote (squared)
            weight = float(sim) ** 2
        else:
            weight = float(sim)
        class_votes[label] = class_votes.get(label, 0.0) + weight

    return max(class_votes, key=class_votes.get)


def pca_whiten(embeddings, n_components):
    """Fit PCA whitening on embeddings, return transformed + components."""
    mean = embeddings.mean(axis=0)
    centered = embeddings - mean
    cov = (centered.T @ centered) / len(centered)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    # Take top n_components (eigenvalues sorted ascending, so take from end)
    idx = np.argsort(eigenvalues)[::-1][:n_components]
    components = eigenvectors[:, idx].T  # (n_components, 384)
    eigenvals = eigenvalues[idx]
    # Whiten: project and normalize by sqrt(eigenvalue)
    whitening_matrix = components / np.sqrt(eigenvals[:, np.newaxis] + 1e-8)
    transformed = (centered @ whitening_matrix.T)
    # L2 normalize
    norms = np.linalg.norm(transformed, axis=1, keepdims=True) + 1e-8
    transformed = transformed / norms
    return transformed, mean, whitening_matrix


def apply_pca(embeddings, mean, whitening_matrix):
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
    args = parser.parse_args()

    with open(args.annotations) as f:
        coco = json.load(f)
    img_dir = Path(args.images)
    img_lookup = {img["id"]: img["file_name"] for img in coco["images"]}

    gallery = np.load(args.gallery)
    with open(args.gallery_labels) as f:
        gallery_labels = np.array(json.load(f), dtype=np.int32)

    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    dino_sess = ort.InferenceSession(args.dino_model, providers=providers)
    dino_input = dino_sess.get_inputs()[0].name

    # Sample and embed test crops
    anns = [a for a in coco["annotations"]
            if a["bbox"][2] >= 10 and a["bbox"][3] >= 10]
    random.seed(42)
    if len(anns) > args.max_crops:
        anns = random.sample(anns, args.max_crops)

    print(f"Embedding {len(anns)} test crops...")
    img_cache = {}
    test_embeddings = []
    test_labels = []

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
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(iw, x + w), min(ih, y + h)
        if x2 - x1 < 10 or y2 - y1 < 10:
            continue

        crop = img[y1:y2, x1:x2]
        inp = preprocess_crop(crop, DINO_INPUT_SIZE)
        emb = dino_sess.run(None, {dino_input: inp})[0].flatten()
        emb = emb / (np.linalg.norm(emb) + 1e-8)
        test_embeddings.append(emb)
        test_labels.append(gt_cat)

        if (i + 1) % 500 == 0:
            print(f"  {i+1}/{len(anns)}")

    test_embeddings = np.array(test_embeddings)
    test_labels = np.array(test_labels)
    print(f"Test set: {len(test_labels)} crops")

    # Grid search
    k_values = [1, 3, 5, 7, 10, 15, 20]
    pca_dims = [0, 64, 128, 192, 256, 320]  # 0 = no PCA
    weight_options = [False, True]

    print(f"\n{'k':>4} {'PCA':>4} {'Weighted':>8} {'Accuracy':>10} {'Mean-Cat':>10}")
    print("-" * 50)

    best_acc = 0
    best_config = None

    for pca_dim in pca_dims:
        if pca_dim > 0:
            gallery_pca, pca_mean, pca_matrix = pca_whiten(gallery, pca_dim)
            test_pca = apply_pca(test_embeddings, pca_mean, pca_matrix)
        else:
            gallery_pca = gallery
            test_pca = test_embeddings

        for k in k_values:
            for weighted in weight_options:
                correct = 0
                per_cat_correct = defaultdict(int)
                per_cat_total = defaultdict(int)

                for i in range(len(test_pca)):
                    pred = knn_classify(test_pca[i], gallery_pca, gallery_labels,
                                       top_k=k, weighted=weighted)
                    gt = test_labels[i]
                    per_cat_total[gt] += 1
                    if pred == gt:
                        correct += 1
                        per_cat_correct[gt] += 1

                acc = correct / len(test_labels)
                cat_accs = [per_cat_correct.get(c, 0) / per_cat_total[c]
                           for c in per_cat_total]
                mean_cat = np.mean(cat_accs)

                if acc > best_acc:
                    best_acc = acc
                    best_config = (k, pca_dim, weighted, acc, mean_cat)

                pca_str = str(pca_dim) if pca_dim > 0 else "none"
                print(f"{k:>4} {pca_str:>4} {str(weighted):>8} {acc:>10.4f} {mean_cat:>10.4f}")

    print(f"\n=== BEST CONFIG ===")
    k, pca_dim, weighted, acc, mean_cat = best_config
    print(f"k={k}, PCA={pca_dim if pca_dim > 0 else 'none'}, weighted={weighted}")
    print(f"Accuracy: {acc:.4f}, Mean-category: {mean_cat:.4f}")

    # Save PCA parameters if PCA was best
    if pca_dim > 0:
        gallery_pca, pca_mean, pca_matrix = pca_whiten(gallery, pca_dim)
        np.save("pca_mean.npy", pca_mean.astype(np.float32))
        np.save("pca_matrix.npy", pca_matrix.astype(np.float32))
        np.save("gallery_pca.npy", gallery_pca.astype(np.float32))
        print(f"\nSaved: pca_mean.npy, pca_matrix.npy, gallery_pca.npy")


if __name__ == "__main__":
    main()
