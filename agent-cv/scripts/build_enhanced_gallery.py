#!/usr/bin/env python3
"""Build enhanced DINOv2 gallery from ALL available training data.

Two data sources:
A. Studio product photos (NM_NGD_product_images/): 327 products, multi-angle
B. Shelf crop annotations (train/): 22,731 annotated bboxes from 248 shelf images

For each category:
- If studio photos exist: blend studio + shelf crop embeddings (70/30)
- If NO studio photos: use shelf crop embeddings only (fills 35 uncovered categories)
- Exclude category 355 ("unknown_product"): would poison gallery matching

Output: gallery_enhanced.npz (embeddings + labels)

Usage: python3 build_enhanced_gallery.py --data-dir /path/to/trainingdata --output gallery_enhanced.npz
  Best on GPU (L4): ~2 min for 22K crops. CPU: ~30-60 min.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import timm
from PIL import Image


EXCLUDE_CATEGORIES = {355}  # category 355 = unknown_product
STUDIO_WEIGHT = 0.7
MIN_CROP_AREA = 500  # skip very tiny crops


def get_device():
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def load_dinov2():
    """Load DINOv2 ViT-S from timm with proper transforms."""
    model = timm.create_model(
        "vit_small_patch14_dinov2.lvd142m", pretrained=True, num_classes=0)
    model.train(False)
    data_config = timm.data.resolve_model_data_config(model)
    transform = timm.data.create_transform(**data_config, is_training=False)
    return model, transform


def embed_single(model, transform, img_pil, device):
    """Embed a single PIL image, return L2-normalized numpy vector."""
    img_t = transform(img_pil).unsqueeze(0).to(device)
    with torch.no_grad():
        emb = model(img_t).cpu().numpy().flatten()
    return emb / (np.linalg.norm(emb) + 1e-8)


def embed_batch(model, transform, images_pil, device, batch_size=32):
    """Embed a list of PIL images in batches, return L2-normalized array."""
    all_embs = []
    for i in range(0, len(images_pil), batch_size):
        batch = images_pil[i:i + batch_size]
        tensors = torch.stack([transform(img) for img in batch]).to(device)
        with torch.no_grad():
            embs = model(tensors).cpu().numpy()
        norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-8
        all_embs.append(embs / norms)
    return np.concatenate(all_embs, axis=0)


def build_studio_embeddings(model, transform, product_dir, metadata, cat_by_name, device):
    """Embed studio product photos. Returns {cat_id: averaged_embedding}."""
    studio = {}
    for product in metadata["products"]:
        name = product["product_name"]
        code = product["product_code"]
        cat_id = cat_by_name.get(name)

        if cat_id is None or cat_id in EXCLUDE_CATEGORIES:
            continue
        if not product.get("has_images"):
            continue

        prod_path = product_dir / code
        if not prod_path.exists():
            continue

        view_embs = []
        for img_type in product.get("image_types", []):
            img_path = prod_path / f"{img_type}.jpg"
            if not img_path.exists():
                continue
            try:
                img = Image.open(img_path).convert("RGB")
                view_embs.append(embed_single(model, transform, img, device))
            except Exception:
                continue

        if view_embs:
            avg = np.mean(view_embs, axis=0)
            studio[cat_id] = avg / (np.linalg.norm(avg) + 1e-8)

    return studio


def build_shelf_embeddings(model, transform, images_dir, annotations, image_map, device):
    """Crop annotated products from shelf images, embed. Returns {cat_id: averaged_embedding}."""
    # Group annotations by image for efficient loading
    anns_by_image = defaultdict(list)
    for ann in annotations:
        if ann["category_id"] in EXCLUDE_CATEGORIES:
            continue
        if ann["bbox"][2] * ann["bbox"][3] < MIN_CROP_AREA:
            continue
        anns_by_image[ann["image_id"]].append(ann)

    total_crops = sum(len(v) for v in anns_by_image.values())
    processed = 0
    cat_embs = defaultdict(list)

    for img_id, img_anns in anns_by_image.items():
        img_info = image_map.get(img_id)
        if img_info is None:
            continue

        img_path = images_dir / img_info["file_name"]
        if not img_path.exists():
            continue

        try:
            img = Image.open(img_path).convert("RGB")
        except Exception:
            continue

        img_w, img_h = img.size
        crops = []
        cat_ids = []

        for ann in img_anns:
            x, y, w, h = ann["bbox"]
            x1, y1 = max(0, int(x)), max(0, int(y))
            x2, y2 = min(img_w, int(x + w)), min(img_h, int(y + h))
            if x2 - x1 < 10 or y2 - y1 < 10:
                continue
            crops.append(img.crop((x1, y1, x2, y2)))
            cat_ids.append(ann["category_id"])

        if crops:
            embs = embed_batch(model, transform, crops, device)
            for cat_id, emb in zip(cat_ids, embs):
                cat_embs[cat_id].append(emb)

        processed += len(img_anns)
        if processed % 2000 == 0 or processed == total_crops:
            print(f"  Shelf crops: {processed}/{total_crops} embedded")

    # Average per category
    shelf_avg = {}
    for cat_id, embs in cat_embs.items():
        avg = np.mean(embs, axis=0)
        shelf_avg[cat_id] = avg / (np.linalg.norm(avg) + 1e-8)

    return shelf_avg


def main():
    parser = argparse.ArgumentParser(description="Build enhanced DINOv2 gallery")
    parser.add_argument("--data-dir", required=True,
                        help="Path to trainingdata/ directory")
    parser.add_argument("--output", default="gallery_enhanced.npz",
                        help="Output path (default: gallery_enhanced.npz)")
    parser.add_argument("--studio-weight", type=float, default=STUDIO_WEIGHT,
                        help=f"Studio blend weight (default: {STUDIO_WEIGHT})")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    product_dir = data_dir / "NM_NGD_product_images"
    ann_path = data_dir / "train" / "annotations.json"
    images_dir = data_dir / "train" / "images"
    output_path = Path(args.output)

    for p, name in [
        (product_dir, "product images"),
        (ann_path, "annotations"),
        (images_dir, "training images"),
    ]:
        if not p.exists():
            print(f"FAIL: {name} not found at {p}")
            raise SystemExit(1)

    print("Loading annotations...")
    with open(ann_path) as f:
        coco = json.load(f)
    cat_by_name = {c["name"]: c["id"] for c in coco["categories"]}
    image_map = {i["id"]: i for i in coco["images"]}

    with open(product_dir / "metadata.json") as f:
        metadata = json.load(f)

    print(f"Categories: {len(coco['categories'])}")
    print(f"Annotations: {len(coco['annotations'])}")
    print(f"Products with images: {sum(1 for p in metadata['products'] if p.get('has_images'))}")

    device = get_device()
    print(f"Device: {device}")
    print("Loading DINOv2 ViT-S...")
    model, transform = load_dinov2()
    model = model.to(device)

    # Phase 1: Studio embeddings
    print("\n--- Phase 1: Studio product photos ---")
    studio = build_studio_embeddings(
        model, transform, product_dir, metadata, cat_by_name, device)
    print(f"Studio gallery: {len(studio)} categories")

    # Phase 2: Shelf crop embeddings
    print("\n--- Phase 2: Shelf crop embeddings ---")
    shelf = build_shelf_embeddings(
        model, transform, images_dir, coco["annotations"], image_map, device)
    print(f"Shelf gallery: {len(shelf)} categories")

    # Phase 3: Blend
    print("\n--- Phase 3: Blending ---")
    all_cat_ids = (set(studio.keys()) | set(shelf.keys())) - EXCLUDE_CATEGORIES

    gallery_embeddings = []
    gallery_labels = []
    studio_only = blended = shelf_only = 0

    for cat_id in sorted(all_cat_ids):
        has_studio = cat_id in studio
        has_shelf = cat_id in shelf

        if has_studio and has_shelf:
            combined = args.studio_weight * studio[cat_id] + (1 - args.studio_weight) * shelf[cat_id]
            gallery_embeddings.append(combined / (np.linalg.norm(combined) + 1e-8))
            blended += 1
        elif has_studio:
            gallery_embeddings.append(studio[cat_id])
            studio_only += 1
        elif has_shelf:
            gallery_embeddings.append(shelf[cat_id])
            shelf_only += 1

        gallery_labels.append(cat_id)

    gallery_embeddings = np.array(gallery_embeddings, dtype=np.float32)
    gallery_labels = np.array(gallery_labels, dtype=np.int32)

    print(f"\nFinal gallery: {len(gallery_labels)} categories, {gallery_embeddings.shape[1]} dims")
    print(f"  Blended (studio+shelf): {blended}")
    print(f"  Studio only: {studio_only}")
    print(f"  Shelf crops only (NEW): {shelf_only}")
    print(f"  Excluded: {len(EXCLUDE_CATEGORIES)}")

    # Coverage report
    ann_cats = set(a["category_id"] for a in coco["annotations"]) - EXCLUDE_CATEGORIES
    covered = set(gallery_labels)
    still_uncovered = ann_cats - covered
    if still_uncovered:
        print(f"\n  WARNING: {len(still_uncovered)} categories still uncovered: {sorted(still_uncovered)}")
    else:
        print(f"\n  All {len(ann_cats)} non-excluded categories covered!")

    np.savez_compressed(output_path, embeddings=gallery_embeddings, labels=gallery_labels)
    size_kb = output_path.stat().st_size / 1024
    print(f"\nSaved: {output_path} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
