"""Pre-train classifier on GCP: embed ALL training crops, fit PCA + SVC, export weights.

Run on GCP VM with L4 GPU:
  python3 pretrain_classifier_gcp.py \
    --annotations ~/trainingdata/train/annotations.json \
    --images ~/trainingdata/train/images/ \
    --dino-model ~/dinov2_vits.onnx \
    --output-dir ~/pretrained_classifier/

Ships 4 files (~1 MB total):
  - pca_mean.npy (384,)
  - pca_matrix.npy (320, 384)
  - svc_coef.npy (357, 320)
  - svc_intercept.npy (357,)
  - svc_classes.npy (357,)

These replace runtime PCA fitting + SVC training, saving ~49s.
The gallery_rich.npy is NO LONGER needed in the submission.
"""
import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

DINO_INPUT_SIZE = 518
BATCH_SIZE = 32  # L4 GPU can handle larger batches


def preprocess_crop(crop_bgr, size=518):
    crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    crop_resized = cv2.resize(crop_rgb, (size, size), interpolation=cv2.INTER_LINEAR)
    crop_float = crop_resized.astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    crop_norm = (crop_float - mean) / std
    return np.transpose(crop_norm, (2, 0, 1)).astype(np.float32)


def pca_whiten_fit(embeddings, n_components):
    """Fit PCA whitening. Returns transformed data, mean, whitening matrix."""
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--annotations", required=True)
    parser.add_argument("--images", required=True)
    parser.add_argument("--dino-model", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--min-crop-size", type=int, default=10)
    parser.add_argument("--pca-dims", type=int, default=320)
    parser.add_argument("--max-per-category", type=int, default=200,
                        help="More data per category than the old gallery cap of 50")
    args = parser.parse_args()

    t_start = time.time()

    with open(args.annotations) as f:
        coco = json.load(f)

    img_dir = Path(args.images)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    img_lookup = {img["id"]: img["file_name"] for img in coco["images"]}

    # Group by category, cap to max_per_category (take largest crops)
    cat_anns = defaultdict(list)
    for ann in coco["annotations"]:
        cat_anns[ann["category_id"]].append(ann)

    selected_anns = []
    for cat_id, anns in cat_anns.items():
        if len(anns) > args.max_per_category:
            anns.sort(key=lambda a: a["area"], reverse=True)
            anns = anns[:args.max_per_category]
        selected_anns.extend(anns)

    print(f"Total annotations: {len(coco['annotations'])}")
    print(f"After capping at {args.max_per_category}/category: {len(selected_anns)}")
    print(f"Categories: {len(cat_anns)}")

    # Load DINOv2
    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    dino_sess = ort.InferenceSession(args.dino_model, providers=providers)
    dino_input = dino_sess.get_inputs()[0].name
    print(f"DINOv2 loaded ({dino_input}), using GPU: {'CUDA' in str(dino_sess.get_providers())}")

    # Embed all crops in batches
    img_cache = {}
    all_preprocessed = []
    all_labels = []
    skipped = 0

    for i, ann in enumerate(selected_anns):
        img_id = ann["image_id"]
        cat_id = ann["category_id"]
        x, y, w, h = ann["bbox"]
        x, y, w, h = int(x), int(y), int(w), int(h)

        if w < args.min_crop_size or h < args.min_crop_size:
            skipped += 1
            continue

        if img_id not in img_cache:
            fname = img_lookup.get(img_id)
            if fname is None:
                skipped += 1
                continue
            img_path = img_dir / fname
            if not img_path.exists():
                img_path = img_dir / Path(fname).name
            if not img_path.exists():
                skipped += 1
                continue
            img_cache[img_id] = cv2.imread(str(img_path))

        img = img_cache[img_id]
        if img is None:
            skipped += 1
            continue

        ih, iw = img.shape[:2]
        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(iw, x + w)
        y2 = min(ih, y + h)

        if x2 - x1 < args.min_crop_size or y2 - y1 < args.min_crop_size:
            skipped += 1
            continue

        crop = img[y1:y2, x1:x2]
        preprocessed = preprocess_crop(crop, DINO_INPUT_SIZE)
        all_preprocessed.append(preprocessed)
        all_labels.append(cat_id)

        if (i + 1) % 2000 == 0:
            print(f"  Prepared {i+1}/{len(selected_anns)} crops...")

    print(f"Crops prepared: {len(all_preprocessed)}, skipped: {skipped}")

    # Batch DINOv2 inference on GPU
    print("Running DINOv2 inference on GPU...")
    t_embed = time.time()
    all_embeddings = []
    for batch_start in range(0, len(all_preprocessed), BATCH_SIZE):
        batch = np.stack(all_preprocessed[batch_start:batch_start + BATCH_SIZE])
        embs = dino_sess.run(None, {dino_input: batch})[0]
        norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-8
        all_embeddings.append(embs / norms)

        if (batch_start + BATCH_SIZE) % (BATCH_SIZE * 50) == 0:
            done = min(batch_start + BATCH_SIZE, len(all_preprocessed))
            print(f"  Embedded {done}/{len(all_preprocessed)}...")

    embeddings = np.concatenate(all_embeddings, axis=0)
    labels = np.array(all_labels, dtype=np.int32)
    print(f"Embedding done: {embeddings.shape} in {time.time()-t_embed:.1f}s")

    # PCA whitening
    print(f"Fitting PCA whitening to {args.pca_dims} dims...")
    t_pca = time.time()
    gallery_pca, pca_mean, pca_matrix = pca_whiten_fit(embeddings, args.pca_dims)
    print(f"PCA done in {time.time()-t_pca:.1f}s")

    # Train LinearSVC
    print("Training LinearSVC...")
    t_svc = time.time()
    from sklearn.svm import LinearSVC
    classifier = LinearSVC(C=1.0, max_iter=5000, dual=False, tol=1e-4)
    classifier.fit(gallery_pca, labels)
    print(f"SVC done in {time.time()-t_svc:.1f}s")
    print(f"SVC classes: {len(classifier.classes_)}")

    # Quick accuracy check: predict on training data
    preds = classifier.predict(gallery_pca)
    acc = (preds == labels).mean()
    print(f"Training accuracy: {acc:.4f}")

    # Save pre-computed weights
    np.save(str(out_dir / "pca_mean.npy"), pca_mean.astype(np.float32))
    np.save(str(out_dir / "pca_matrix.npy"), pca_matrix.astype(np.float32))
    np.save(str(out_dir / "svc_coef.npy"), classifier.coef_.astype(np.float32))
    np.save(str(out_dir / "svc_intercept.npy"), classifier.intercept_.astype(np.float32))
    np.save(str(out_dir / "svc_classes.npy"), classifier.classes_.astype(np.int32))

    # Also save the full gallery for fallback
    np.save(str(out_dir / "gallery_full.npy"), embeddings.astype(np.float32))
    with open(out_dir / "gallery_full_labels.json", "w") as f:
        json.dump(all_labels, f)

    # Report sizes
    for fname in ["pca_mean.npy", "pca_matrix.npy", "svc_coef.npy",
                   "svc_intercept.npy", "svc_classes.npy"]:
        fpath = out_dir / fname
        sz = fpath.stat().st_size / 1024
        print(f"  {fname}: {sz:.1f} KB")

    total_time = time.time() - t_start
    print(f"\nDone in {total_time:.0f}s ({total_time/60:.1f} min)")
    print(f"Output: {out_dir}")
    print(f"\nCopy to local with:")
    print(f"  gcloud compute scp cv-train-1:~/{out_dir.name}/*.npy /tmp/pretrained/ --zone=europe-west1-c --project=ai-nm26osl-1779")


if __name__ == "__main__":
    main()
