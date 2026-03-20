"""Build DINOv2 embedding gallery from product reference images.

For each product, embed multiple views (front, back, left, right, main),
average the embeddings for a robust gallery vector.
Save gallery.npy (embeddings) and gallery_labels.npy (category IDs).
Also export DINOv2 ViT-S to ONNX for sandbox inference.
"""
import json
from pathlib import Path

import numpy as np
import torch
import timm
from PIL import Image
from torchvision import transforms


def build_gallery():
    base = Path("/Volumes/devdrive/github_dev/nmiai-2026-main/trainingdata")
    product_dir = base / "NM_NGD_product_images"
    ann_path = base / "train" / "annotations.json"
    output_dir = Path("/Volumes/devdrive/github_dev/nmiai-2026-main/agent-cv/solutions")

    # Load category mapping
    with open(ann_path) as f:
        coco = json.load(f)
    cat_by_name = {c["name"]: c["id"] for c in coco["categories"]}

    # Load product metadata
    with open(product_dir / "metadata.json") as f:
        meta = json.load(f)

    # Load DINOv2 ViT-S model from timm
    print("Loading DINOv2 ViT-S...")
    model = timm.create_model("vit_small_patch14_dinov2.lvd142m", pretrained=True, num_classes=0)
    model.eval()

    # Get model config for transforms
    data_config = timm.data.resolve_model_data_config(model)
    transform = timm.data.create_transform(**data_config, is_training=False)

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model = model.to(device)

    gallery_embeddings = []
    gallery_labels = []

    print(f"Processing {len(meta['products'])} products...")
    for i, product in enumerate(meta["products"]):
        name = product["product_name"]
        code = product["product_code"]
        cat_id = cat_by_name.get(name)

        if cat_id is None or not product["has_images"]:
            continue

        prod_path = product_dir / code
        if not prod_path.exists():
            continue

        # Embed all available views
        view_embeddings = []
        for img_type in product["image_types"]:
            img_path = prod_path / f"{img_type}.jpg"
            if not img_path.exists():
                continue

            try:
                img = Image.open(img_path).convert("RGB")
                img_t = transform(img).unsqueeze(0).to(device)

                with torch.no_grad():
                    emb = model(img_t)  # (1, embed_dim)
                    emb = emb.cpu().numpy().flatten()
                    emb = emb / (np.linalg.norm(emb) + 1e-8)  # L2 normalize
                    view_embeddings.append(emb)
            except Exception:
                continue

        if view_embeddings:
            # Average all views for this product
            avg_emb = np.mean(view_embeddings, axis=0)
            avg_emb = avg_emb / (np.linalg.norm(avg_emb) + 1e-8)  # Re-normalize
            gallery_embeddings.append(avg_emb)
            gallery_labels.append(cat_id)

        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(meta['products'])} products processed")

    gallery_embeddings = np.array(gallery_embeddings, dtype=np.float32)
    gallery_labels = np.array(gallery_labels, dtype=np.int32)

    print(f"Gallery: {gallery_embeddings.shape[0]} products, {gallery_embeddings.shape[1]} dims")

    # Save gallery
    np.save(output_dir / "gallery.npy", gallery_embeddings)
    np.save(output_dir / "gallery_labels.npy", gallery_labels)
    print(f"Saved: gallery.npy ({gallery_embeddings.nbytes / 1024:.0f} KB)")
    print(f"Saved: gallery_labels.npy ({gallery_labels.nbytes / 1024:.0f} KB)")

    # Export DINOv2 to ONNX
    print("Exporting DINOv2 to ONNX...")
    model = model.to("cpu")
    dummy = torch.randn(1, 3, 518, 518)  # DINOv2 ViT-S default resolution
    onnx_path = output_dir / "dinov2_vits.onnx"

    torch.onnx.export(
        model,
        dummy,
        str(onnx_path),
        opset_version=17,
        input_names=["input"],
        output_names=["embedding"],
        dynamic_axes={"input": {0: "batch"}, "embedding": {0: "batch"}},
    )

    # Check size
    size_mb = onnx_path.stat().st_size / (1024 * 1024)
    print(f"DINOv2 ONNX: {size_mb:.1f} MB")

    # Total weight budget
    yolo_size = (output_dir / "best.onnx").stat().st_size / (1024 * 1024)
    total = yolo_size + size_mb + gallery_embeddings.nbytes / (1024 * 1024)
    print(f"Total weight budget: YOLO {yolo_size:.0f}MB + DINOv2 {size_mb:.0f}MB + gallery <1MB = {total:.0f}MB / 420MB")


if __name__ == "__main__":
    build_gallery()
