"""Add product reference images to existing rich gallery.

Embeds each product photo individually (front, back, left, right, etc.)
and appends to the existing gallery_rich.npy/gallery_rich_labels.json.

Uses metadata.json to map product folder -> category_id.

Usage:
  python add_product_images_to_gallery.py \
    --product-dir ~/trainingdata/NM_NGD_product_images \
    --annotations ~/trainingdata/train/annotations.json \
    --existing-gallery ~/gallery_output/gallery_rich.npy \
    --existing-labels ~/gallery_output/gallery_rich_labels.json \
    --dino-model ~/dinov2_vits.onnx \
    --output-dir ~/gallery_output/
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

DINO_INPUT_SIZE = 518


def preprocess_crop(img_bgr, size=518):
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(img_rgb, (size, size), interpolation=cv2.INTER_LINEAR)
    img_float = resized.astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    normed = (img_float - mean) / std
    return np.transpose(normed, (2, 0, 1))[np.newaxis, ...].astype(np.float32)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-dir", required=True)
    parser.add_argument("--annotations", required=True)
    parser.add_argument("--existing-gallery", required=True)
    parser.add_argument("--existing-labels", required=True)
    parser.add_argument("--dino-model", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    product_dir = Path(args.product_dir)
    out_dir = Path(args.output_dir)

    # Load annotations for category name -> id mapping
    with open(args.annotations) as f:
        coco = json.load(f)
    cat_by_name = {c["name"]: c["id"] for c in coco["categories"]}

    # Load metadata for product_code -> product_name mapping
    metadata_path = product_dir / "metadata.json"
    with open(metadata_path) as f:
        metadata = json.load(f)

    # Load existing gallery
    existing_embs = np.load(args.existing_gallery)
    with open(args.existing_labels) as f:
        existing_labels = json.load(f)
    print(f"Existing gallery: {existing_embs.shape[0]} embeddings")

    # Load DINOv2
    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    dino_sess = ort.InferenceSession(args.dino_model, providers=providers)
    dino_input = dino_sess.get_inputs()[0].name

    new_embs = []
    new_labels = []
    skipped = 0

    for product in metadata["products"]:
        name = product["product_name"]
        cat_id = cat_by_name.get(name)
        if cat_id is None or not product.get("has_images"):
            skipped += 1
            continue

        prod_path = product_dir / product["product_code"]
        if not prod_path.exists():
            skipped += 1
            continue

        for img_type in product.get("image_types", []):
            img_path = prod_path / f"{img_type}.jpg"
            if not img_path.exists() or img_path.name.startswith("._"):
                continue
            img = cv2.imread(str(img_path))
            if img is None:
                continue
            inp = preprocess_crop(img, DINO_INPUT_SIZE)
            emb = dino_sess.run(None, {dino_input: inp})[0].flatten()
            emb = emb / (np.linalg.norm(emb) + 1e-8)
            new_embs.append(emb)
            new_labels.append(cat_id)

    print(f"Product reference images: {len(new_embs)} embeddings")
    print(f"Skipped: {skipped} products (no category match or no images)")

    # Merge
    if new_embs:
        new_embs = np.array(new_embs, dtype=np.float32)
        combined_embs = np.concatenate([existing_embs, new_embs], axis=0)
        combined_labels = existing_labels + new_labels
    else:
        combined_embs = existing_embs
        combined_labels = existing_labels

    print(f"Combined gallery: {combined_embs.shape[0]} embeddings, "
          f"{len(set(combined_labels))} categories")

    np.save(str(out_dir / "gallery_combined.npy"), combined_embs)
    with open(out_dir / "gallery_combined_labels.json", "w") as f:
        json.dump(combined_labels, f)

    print(f"Saved to {out_dir}")


if __name__ == "__main__":
    main()
