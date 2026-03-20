#!/usr/bin/env python3
"""Evaluate synthetic image quality by comparing DINOv2 embeddings.

For each category with Gemini-generated images:
1. Embed the shelf crop (what we currently use in gallery)
2. Embed Gemini v1 and v2
3. Embed studio photos (if they exist, as ground truth)
4. Compare cosine similarities

If Gemini embeddings are closer to studio photos than shelf crops are,
Gemini images are BETTER gallery entries.

Usage: python3 eval_synthetic_quality.py --synthetic-dir synthetic_test/ --data-dir trainingdata/
"""
import argparse
import json
from pathlib import Path

import numpy as np
import torch
import timm
from PIL import Image


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


def embed(model, transform, img_path, device):
    img = Image.open(img_path).convert("RGB")
    t = transform(img).unsqueeze(0).to(device)
    with torch.no_grad():
        emb = model(t).cpu().numpy().flatten()
    return emb / (np.linalg.norm(emb) + 1e-8)


def cosine_sim(a, b):
    return float(np.dot(a, b))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic-dir", required=True)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--output", default="synthetic_eval_results.json")
    args = parser.parse_args()

    syn_dir = Path(args.synthetic_dir)
    data_dir = Path(args.data_dir)
    product_dir = data_dir / "NM_NGD_product_images"

    # Load category mapping
    with open(data_dir / "train" / "annotations.json") as f:
        coco = json.load(f)
    cat_by_id = {c["id"]: c["name"] for c in coco["categories"]}

    # Load product metadata for studio photo lookup
    with open(product_dir / "metadata.json") as f:
        meta = json.load(f)
    cat_by_name = {c["name"]: c["id"] for c in coco["categories"]}
    product_by_cat = {}
    for p in meta["products"]:
        cat_id = cat_by_name.get(p["product_name"])
        if cat_id is not None and p.get("has_images"):
            product_by_cat[cat_id] = p

    device = get_device()
    print(f"Device: {device}")
    model, transform = load_dinov2()
    model = model.to(device)

    # Find all categories with synthetic images
    crop_files = sorted(syn_dir.glob("cat_*_crop.jpg"))
    results = []

    for crop_path in crop_files:
        cat_id = int(crop_path.stem.split("_")[1])
        cat_name = cat_by_id.get(cat_id, "unknown")

        v1_path = syn_dir / f"cat_{cat_id:03d}_gemini_v1.png"
        v2_path = syn_dir / f"cat_{cat_id:03d}_gemini_v2.png"

        if not v1_path.exists():
            continue

        print(f"\nCat {cat_id}: {cat_name}")

        # Embed shelf crop
        emb_crop = embed(model, transform, crop_path, device)

        # Embed Gemini images
        emb_v1 = embed(model, transform, v1_path, device)
        emb_v2 = embed(model, transform, v2_path, device) if v2_path.exists() else None

        # Average Gemini embeddings
        if emb_v2 is not None:
            emb_gemini_avg = (emb_v1 + emb_v2) / 2
            emb_gemini_avg = emb_gemini_avg / (np.linalg.norm(emb_gemini_avg) + 1e-8)
        else:
            emb_gemini_avg = emb_v1

        # Check if studio photos exist for this category (ground truth)
        has_studio = cat_id in product_by_cat
        studio_sim_crop = None
        studio_sim_gemini = None

        if has_studio:
            product = product_by_cat[cat_id]
            prod_path = product_dir / product["product_code"]
            studio_embs = []
            for img_type in product.get("image_types", []):
                ip = prod_path / f"{img_type}.jpg"
                if ip.exists():
                    studio_embs.append(embed(model, transform, ip, device))

            if studio_embs:
                studio_avg = np.mean(studio_embs, axis=0)
                studio_avg = studio_avg / (np.linalg.norm(studio_avg) + 1e-8)
                studio_sim_crop = cosine_sim(studio_avg, emb_crop)
                studio_sim_gemini = cosine_sim(studio_avg, emb_gemini_avg)

        # Self-similarities
        crop_v1_sim = cosine_sim(emb_crop, emb_v1)
        crop_v2_sim = cosine_sim(emb_crop, emb_v2) if emb_v2 is not None else None
        v1_v2_sim = cosine_sim(emb_v1, emb_v2) if emb_v2 is not None else None

        result = {
            "cat_id": cat_id,
            "cat_name": cat_name,
            "has_studio": has_studio,
            "crop_v1_sim": round(crop_v1_sim, 4),
            "crop_v2_sim": round(crop_v2_sim, 4) if crop_v2_sim else None,
            "v1_v2_sim": round(v1_v2_sim, 4) if v1_v2_sim else None,
            "studio_vs_crop": round(studio_sim_crop, 4) if studio_sim_crop else None,
            "studio_vs_gemini": round(studio_sim_gemini, 4) if studio_sim_gemini else None,
        }
        results.append(result)

        if has_studio:
            delta = studio_sim_gemini - studio_sim_crop
            winner = "GEMINI" if delta > 0 else "CROP"
            print(f"  Studio vs Crop:   {studio_sim_crop:.4f}")
            print(f"  Studio vs Gemini: {studio_sim_gemini:.4f}  ({'+' if delta > 0 else ''}{delta:.4f}) -> {winner}")
        else:
            print(f"  Crop vs Gemini v1: {crop_v1_sim:.4f}")
            print(f"  No studio photos (this is an uncovered category)")

    # Summary
    print("\n" + "=" * 60)
    with_studio = [r for r in results if r["has_studio"]]
    without_studio = [r for r in results if not r["has_studio"]]

    if with_studio:
        gemini_wins = sum(1 for r in with_studio if r["studio_vs_gemini"] > r["studio_vs_crop"])
        print(f"Categories WITH studio photos: {len(with_studio)}")
        print(f"  Gemini closer to studio: {gemini_wins}/{len(with_studio)}")
        avg_crop = np.mean([r["studio_vs_crop"] for r in with_studio])
        avg_gemini = np.mean([r["studio_vs_gemini"] for r in with_studio])
        print(f"  Avg studio-crop sim:   {avg_crop:.4f}")
        print(f"  Avg studio-gemini sim: {avg_gemini:.4f}")

    print(f"Categories WITHOUT studio (uncovered): {len(without_studio)}")
    if without_studio:
        avg_crop_gemini = np.mean([r["crop_v1_sim"] for r in without_studio])
        print(f"  Avg crop-gemini sim: {avg_crop_gemini:.4f}")

    # Save results
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved: {args.output}")


if __name__ == "__main__":
    main()
