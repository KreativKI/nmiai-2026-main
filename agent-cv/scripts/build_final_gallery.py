#!/usr/bin/env python3
"""Build final gallery combining ALL data sources.

Three data sources, blended per category:
A. Studio product photos (NM_NGD_product_images/): 327 products, multi-angle
B. Shelf crop annotations (train/): 22,731 annotated bboxes
C. Gemini synthetic photos (synthetic_test/): clean product photos on white bg

Blend weights (when all 3 exist for a category):
  60% studio + 20% shelf + 20% gemini

When only some exist:
  Studio + shelf only: 70% studio + 30% shelf (same as enhanced gallery)
  Shelf + gemini only: 50% shelf + 50% gemini
  Shelf only: 100% shelf
  Gemini only: 100% gemini

Exclude category 355 (unknown_product).

Output: gallery.npy + gallery_labels.json (allowed file types only!)

Usage: python3 build_final_gallery.py --data-dir trainingdata/ --synthetic-dir synthetic_test/ --output-dir output/
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import timm
from PIL import Image


EXCLUDE_CATEGORIES = {355}


def get_device():
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def load_dinov2():
    model = timm.create_model(
        "vit_small_patch14_dinov2.lvd142m", pretrained=True, num_classes=0)
    model.train(False)
    data_config = timm.data.resolve_model_data_config(model)
    transform = timm.data.create_transform(**data_config, is_training=False)
    return model, transform


def embed_single(model, transform, img_path, device):
    img = Image.open(img_path).convert("RGB")
    t = transform(img).unsqueeze(0).to(device)
    with torch.no_grad():
        emb = model(t).cpu().numpy().flatten()
    return emb / (np.linalg.norm(emb) + 1e-8)


def embed_batch(model, transform, images_pil, device, batch_size=32):
    all_embs = []
    for i in range(0, len(images_pil), batch_size):
        batch = images_pil[i:i + batch_size]
        tensors = torch.stack([transform(img) for img in batch]).to(device)
        with torch.no_grad():
            embs = model(tensors).cpu().numpy()
        norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-8
        all_embs.append(embs / norms)
    return np.concatenate(all_embs, axis=0)


def main():
    parser = argparse.ArgumentParser(description="Build final gallery from all sources")
    parser.add_argument("--data-dir", required=True, help="Path to trainingdata/")
    parser.add_argument("--synthetic-dir", required=True, help="Path to synthetic_test/")
    parser.add_argument("--output-dir", required=True, help="Output directory for gallery files")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    syn_dir = Path(args.synthetic_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    product_dir = data_dir / "NM_NGD_product_images"
    ann_path = data_dir / "train" / "annotations.json"
    images_dir = data_dir / "train" / "images"

    # Load annotations + metadata
    print("Loading annotations...")
    with open(ann_path) as f:
        coco = json.load(f)
    cat_by_name = {c["name"]: c["id"] for c in coco["categories"]}
    cat_by_id = {c["id"]: c["name"] for c in coco["categories"]}
    image_map = {i["id"]: i for i in coco["images"]}

    with open(product_dir / "metadata.json") as f:
        metadata = json.load(f)

    device = get_device()
    print(f"Device: {device}")
    model, transform = load_dinov2()
    model = model.to(device)

    # --- Source A: Studio photos ---
    print("\n--- Source A: Studio product photos ---")
    studio = {}
    for product in metadata["products"]:
        name = product["product_name"]
        cat_id = cat_by_name.get(name)
        if cat_id is None or cat_id in EXCLUDE_CATEGORIES or not product.get("has_images"):
            continue
        prod_path = product_dir / product["product_code"]
        if not prod_path.exists():
            continue
        view_embs = []
        for img_type in product.get("image_types", []):
            ip = prod_path / f"{img_type}.jpg"
            if ip.exists():
                try:
                    view_embs.append(embed_single(model, transform, ip, device))
                except Exception:
                    pass
        if view_embs:
            avg = np.mean(view_embs, axis=0)
            studio[cat_id] = avg / (np.linalg.norm(avg) + 1e-8)
    print(f"Studio: {len(studio)} categories")

    # --- Source B: Shelf crops ---
    print("\n--- Source B: Shelf crop embeddings ---")
    MIN_CROP_AREA = 500
    anns_by_image = defaultdict(list)
    for ann in coco["annotations"]:
        if ann["category_id"] in EXCLUDE_CATEGORIES:
            continue
        if ann["bbox"][2] * ann["bbox"][3] < MIN_CROP_AREA:
            continue
        anns_by_image[ann["image_id"]].append(ann)

    total = sum(len(v) for v in anns_by_image.values())
    processed = 0
    shelf_embs = defaultdict(list)

    for img_id, img_anns in anns_by_image.items():
        img_info = image_map.get(img_id)
        if not img_info:
            continue
        img_path = images_dir / img_info["file_name"]
        if not img_path.exists():
            continue
        try:
            img = Image.open(img_path).convert("RGB")
        except Exception:
            continue
        img_w, img_h = img.size
        crops, cat_ids = [], []
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
            for cid, emb in zip(cat_ids, embs):
                shelf_embs[cid].append(emb)
        processed += len(img_anns)
        if processed % 2000 == 0:
            print(f"  Shelf crops: {processed}/{total}")

    shelf = {}
    for cid, embs in shelf_embs.items():
        avg = np.mean(embs, axis=0)
        shelf[cid] = avg / (np.linalg.norm(avg) + 1e-8)
    print(f"Shelf: {len(shelf)} categories")

    # --- Source C: Gemini synthetic ---
    print("\n--- Source C: Gemini synthetic photos ---")
    gemini = {}
    if syn_dir.exists():
        for crop_file in syn_dir.glob("cat_*_gemini_v1.png"):
            cat_str = crop_file.stem.replace("cat_", "").replace("_gemini_v1", "")
            try:
                cat_id = int(cat_str)
            except ValueError:
                continue
            if cat_id in EXCLUDE_CATEGORIES:
                continue
            gem_embs = []
            for suffix in ["_gemini_v1.png", "_gemini_v2.png"]:
                gp = syn_dir / f"cat_{cat_str}{suffix}"
                if gp.exists():
                    try:
                        gem_embs.append(embed_single(model, transform, gp, device))
                    except Exception:
                        pass
            if gem_embs:
                avg = np.mean(gem_embs, axis=0)
                gemini[cat_id] = avg / (np.linalg.norm(avg) + 1e-8)
    print(f"Gemini: {len(gemini)} categories")

    # --- Blend ---
    print("\n--- Blending ---")
    all_cats = (set(studio) | set(shelf) | set(gemini)) - EXCLUDE_CATEGORIES

    gallery_embs, gallery_labels = [], []
    stats = {"studio_shelf_gemini": 0, "studio_shelf": 0, "shelf_gemini": 0,
             "studio_only": 0, "shelf_only": 0, "gemini_only": 0}

    for cid in sorted(all_cats):
        s, sh, g = cid in studio, cid in shelf, cid in gemini

        if s and sh and g:
            combined = 0.6 * studio[cid] + 0.2 * shelf[cid] + 0.2 * gemini[cid]
            stats["studio_shelf_gemini"] += 1
        elif s and sh:
            combined = 0.7 * studio[cid] + 0.3 * shelf[cid]
            stats["studio_shelf"] += 1
        elif sh and g:
            combined = 0.5 * shelf[cid] + 0.5 * gemini[cid]
            stats["shelf_gemini"] += 1
        elif s:
            combined = studio[cid]
            stats["studio_only"] += 1
        elif sh:
            combined = shelf[cid]
            stats["shelf_only"] += 1
        elif g:
            combined = gemini[cid]
            stats["gemini_only"] += 1
        else:
            continue

        combined = combined / (np.linalg.norm(combined) + 1e-8)
        gallery_embs.append(combined)
        gallery_labels.append(cid)

    gallery_embs = np.array(gallery_embs, dtype=np.float32)
    gallery_labels_list = [int(x) for x in gallery_labels]

    print(f"\nFinal gallery: {len(gallery_labels)} categories, {gallery_embs.shape[1]} dims")
    for k, v in stats.items():
        if v > 0:
            print(f"  {k}: {v}")

    # Save as .npy + .json (ALLOWED file types only!)
    np.save(out_dir / "gallery.npy", gallery_embs)
    with open(out_dir / "gallery_labels.json", "w") as f:
        json.dump(gallery_labels_list, f)

    print(f"\nSaved: {out_dir / 'gallery.npy'} ({gallery_embs.nbytes / 1024:.0f} KB)")
    print(f"Saved: {out_dir / 'gallery_labels.json'}")


if __name__ == "__main__":
    main()
