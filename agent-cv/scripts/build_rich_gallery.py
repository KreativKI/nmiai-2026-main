"""Build rich gallery from COCO training annotations.

Crops each annotated bounding box, embeds with DINOv2 ONNX, saves gallery.
Output: gallery_rich.npy (N, 384) and gallery_rich_labels.json (N,)

Usage:
  python build_rich_gallery.py \
    --annotations ~/trainingdata/train/annotations.json \
    --images ~/trainingdata/train/ \
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


def preprocess_crop(crop_bgr, size=518):
    crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    crop_resized = cv2.resize(crop_rgb, (size, size), interpolation=cv2.INTER_LINEAR)
    crop_float = crop_resized.astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    crop_norm = (crop_float - mean) / std
    return np.transpose(crop_norm, (2, 0, 1))[np.newaxis, ...].astype(np.float32)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--annotations", required=True)
    parser.add_argument("--images", required=True)
    parser.add_argument("--dino-model", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--min-crop-size", type=int, default=10,
                        help="Skip crops smaller than this (pixels)")
    parser.add_argument("--max-per-category", type=int, default=50,
                        help="Cap samples per category to keep gallery balanced")
    args = parser.parse_args()

    with open(args.annotations) as f:
        coco = json.load(f)

    img_dir = Path(args.images)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build image lookup
    img_lookup = {img["id"]: img["file_name"] for img in coco["images"]}

    # Group annotations by category to cap per-category
    from collections import defaultdict
    cat_anns = defaultdict(list)
    for ann in coco["annotations"]:
        cat_anns[ann["category_id"]].append(ann)

    # Cap per category
    selected_anns = []
    for cat_id, anns in cat_anns.items():
        if len(anns) > args.max_per_category:
            # Take the largest crops (most information)
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
    print(f"DINOv2 loaded, input: {dino_input}")

    # Cache loaded images
    img_cache = {}
    embeddings = []
    labels = []
    skipped = 0

    for i, ann in enumerate(selected_anns):
        img_id = ann["image_id"]
        cat_id = ann["category_id"]
        x, y, w, h = ann["bbox"]
        x, y, w, h = int(x), int(y), int(w), int(h)

        if w < args.min_crop_size or h < args.min_crop_size:
            skipped += 1
            continue

        # Load image (cached)
        if img_id not in img_cache:
            fname = img_lookup.get(img_id)
            if fname is None:
                skipped += 1
                continue
            img_path = img_dir / fname
            if not img_path.exists():
                # Try without path prefix
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
        inp = preprocess_crop(crop, DINO_INPUT_SIZE)
        emb = dino_sess.run(None, {dino_input: inp})[0].flatten()
        emb = emb / (np.linalg.norm(emb) + 1e-8)

        embeddings.append(emb)
        labels.append(cat_id)

        if (i + 1) % 500 == 0:
            print(f"  Processed {i+1}/{len(selected_anns)} crops...")

    embeddings = np.array(embeddings, dtype=np.float32)
    print(f"\nGallery built: {embeddings.shape}")
    print(f"Skipped: {skipped} (too small or missing images)")
    print(f"Unique categories: {len(set(labels))}")

    np.save(str(out_dir / "gallery_rich.npy"), embeddings)
    with open(out_dir / "gallery_rich_labels.json", "w") as f:
        json.dump(labels, f)

    print(f"Saved to {out_dir}/gallery_rich.npy and gallery_rich_labels.json")


if __name__ == "__main__":
    main()
