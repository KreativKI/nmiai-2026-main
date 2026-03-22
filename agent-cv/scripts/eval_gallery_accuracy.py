"""Evaluate kNN classification accuracy of different gallery configurations.

For each annotated crop in training data, embed with DINOv2 and check if
kNN against a given gallery returns the correct category_id.

For gallery_rich (built from training crops), uses leave-one-out: excludes
the query crop's embedding from the gallery before kNN lookup.

Usage:
  python eval_gallery_accuracy.py \
    --annotations ~/trainingdata/train/annotations.json \
    --images ~/trainingdata/train/images/ \
    --dino-model ~/dinov2_vits.onnx \
    --gallery ~/gallery_output/gallery_rich.npy \
    --gallery-labels ~/gallery_output/gallery_rich_labels.json \
    --max-crops 2000 \
    --top-k 5
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


def knn_classify(query_emb, gallery, gallery_labels, top_k=5):
    similarities = query_emb @ gallery.T
    top_k_idx = np.argsort(similarities)[-top_k:]
    k_sims = similarities[top_k_idx]
    k_labels = gallery_labels[top_k_idx]

    class_votes = {}
    for label, sim in zip(k_labels, k_sims):
        label = int(label)
        class_votes[label] = class_votes.get(label, 0.0) + float(sim)

    return max(class_votes, key=class_votes.get)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--annotations", required=True)
    parser.add_argument("--images", required=True)
    parser.add_argument("--dino-model", required=True)
    parser.add_argument("--gallery", required=True)
    parser.add_argument("--gallery-labels", required=True)
    parser.add_argument("--max-crops", type=int, default=2000)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--min-crop-size", type=int, default=10)
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

    # Sample annotations
    anns = [a for a in coco["annotations"]
            if a["bbox"][2] >= args.min_crop_size and a["bbox"][3] >= args.min_crop_size]
    random.seed(42)
    if len(anns) > args.max_crops:
        anns = random.sample(anns, args.max_crops)

    print(f"Gallery: {gallery.shape[0]} entries, {len(set(gallery_labels.tolist()))} categories")
    print(f"Evaluating {len(anns)} crops with top-k={args.top_k}")

    img_cache = {}
    correct = 0
    total = 0
    per_cat_correct = defaultdict(int)
    per_cat_total = defaultdict(int)
    confusions = defaultdict(int)

    for i, ann in enumerate(anns):
        img_id = ann["image_id"]
        gt_cat = ann["category_id"]
        x, y, w, h = ann["bbox"]
        x, y, w, h = int(x), int(y), int(w), int(h)

        if img_id not in img_cache:
            fname = img_lookup.get(img_id)
            if fname is None:
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
        if x2 - x1 < args.min_crop_size or y2 - y1 < args.min_crop_size:
            continue

        crop = img[y1:y2, x1:x2]
        inp = preprocess_crop(crop, DINO_INPUT_SIZE)
        emb = dino_sess.run(None, {dino_input: inp})[0].flatten()
        emb = emb / (np.linalg.norm(emb) + 1e-8)

        pred_cat = knn_classify(emb, gallery, gallery_labels, args.top_k)

        per_cat_total[gt_cat] += 1
        if pred_cat == gt_cat:
            correct += 1
            per_cat_correct[gt_cat] += 1
        else:
            confusions[(gt_cat, pred_cat)] += 1

        total += 1
        if (i + 1) % 500 == 0:
            print(f"  {i+1}/{len(anns)}: accuracy={correct/total:.4f}")

    acc = correct / total if total > 0 else 0
    print(f"\n=== RESULTS ===")
    print(f"Overall accuracy: {correct}/{total} = {acc:.4f}")

    # Per-category stats
    cat_accs = []
    for cat_id in sorted(per_cat_total.keys()):
        c = per_cat_correct.get(cat_id, 0)
        t = per_cat_total[cat_id]
        cat_accs.append(c / t if t > 0 else 0)
    mean_cat_acc = np.mean(cat_accs) if cat_accs else 0
    print(f"Mean per-category accuracy: {mean_cat_acc:.4f}")

    # Worst categories
    worst = [(cat_id, per_cat_correct.get(cat_id, 0) / per_cat_total[cat_id])
             for cat_id in per_cat_total if per_cat_total[cat_id] >= 3]
    worst.sort(key=lambda x: x[1])
    print(f"\nWorst 10 categories (>= 3 samples):")
    for cat_id, acc in worst[:10]:
        print(f"  cat {cat_id}: {per_cat_correct.get(cat_id, 0)}/{per_cat_total[cat_id]} = {acc:.2f}")

    # Top confusions
    top_conf = sorted(confusions.items(), key=lambda x: -x[1])[:10]
    print(f"\nTop 10 confusions:")
    for (gt, pred), count in top_conf:
        print(f"  gt={gt} -> pred={pred}: {count}x")


if __name__ == "__main__":
    main()
