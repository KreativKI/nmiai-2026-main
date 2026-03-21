#!/usr/bin/env python3
"""Generate massive copy-paste augmented training images.

Creates 1000 synthetic shelf images by pasting products onto shelf backgrounds
with heavy variation: scale, rotation, lighting, blur, occlusion.

Uses ALL available product sources:
- COCO annotation crops from 248 real images
- 327 product reference images (multi-angle studio photos)
- 699 Gemini-generated product photos

Targets rare categories aggressively (inverse frequency weighting).

Usage (on GCP cv-train-1):
    source ~/cv-train/venv/bin/activate
    python3 copy_paste_v3_massive.py
"""

import json
import random
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

# GCP paths
ANNOTATIONS = Path("/home/jcfrugaard/trainingdata/train/annotations.json")
IMAGES_DIR = Path("/home/jcfrugaard/trainingdata/train/images")
PRODUCT_IMAGES_DIR = Path("/home/jcfrugaard/trainingdata/NM_NGD_product_images")
GEMINI_DIR = Path("/home/jcfrugaard/synthetic_all")
OUTPUT_DIR = Path("/home/jcfrugaard/synthetic_data_v3")

NUM_IMAGES = 1000
PRODUCTS_PER_IMAGE_MIN = 4
PRODUCTS_PER_IMAGE_MAX = 15
IMAGE_ID_START = 50000
ANN_ID_START = 500000
SEED = 456


def remove_white_bg(img_bgr, threshold=230):
    """Remove white/light background from product image."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    return mask


def random_transform(img, mask, rng):
    """Apply random scale, rotation, brightness, blur to product."""
    h, w = img.shape[:2]

    # Random scale
    scale = rng.uniform(0.3, 1.8)
    new_h, new_w = max(10, int(h * scale)), max(10, int(w * scale))
    img = cv2.resize(img, (new_w, new_h))
    mask = cv2.resize(mask, (new_w, new_h))

    # Random rotation (-15 to +15 degrees)
    angle = rng.uniform(-15, 15)
    if abs(angle) > 2:
        M = cv2.getRotationMatrix2D((new_w // 2, new_h // 2), angle, 1.0)
        img = cv2.warpAffine(img, M, (new_w, new_h), borderValue=(114, 114, 114))
        mask = cv2.warpAffine(mask, M, (new_w, new_h), borderValue=0)

    # Random brightness/contrast
    alpha = rng.uniform(0.6, 1.4)
    beta = rng.uniform(-30, 30)
    img = np.clip(img.astype(np.float32) * alpha + beta, 0, 255).astype(np.uint8)

    # Random HSV jitter
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 0] = (hsv[:, :, 0] + rng.uniform(-8, 8)) % 180
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * rng.uniform(0.7, 1.3), 0, 255)
    hsv[:, :, 2] = np.clip(hsv[:, :, 2] * rng.uniform(0.7, 1.3), 0, 255)
    img = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    # Random blur (sometimes)
    if rng.random() < 0.2:
        ksize = rng.choice([3, 5])
        img = cv2.GaussianBlur(img, (ksize, ksize), 0)

    return img, mask


def paste_product(background, product_img, mask, x, y):
    """Paste product onto background with alpha blending."""
    ph, pw = product_img.shape[:2]
    bg_h, bg_w = background.shape[:2]

    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(bg_w, x + pw)
    y2 = min(bg_h, y + ph)

    sx1 = x1 - x
    sy1 = y1 - y
    sx2 = sx1 + (x2 - x1)
    sy2 = sy1 + (y2 - y1)

    if x2 - x1 < 5 or y2 - y1 < 5:
        return None

    roi = background[y1:y2, x1:x2]
    src = product_img[sy1:sy2, sx1:sx2]
    m = mask[sy1:sy2, sx1:sx2]

    m3 = cv2.merge([m, m, m]).astype(np.float32) / 255.0
    blended = (src.astype(np.float32) * m3 + roi.astype(np.float32) * (1 - m3)).astype(np.uint8)
    background[y1:y2, x1:x2] = blended

    return (x1, y1, x2 - x1, y2 - y1)


def main():
    rng = random.Random(SEED)
    np_rng = np.random.RandomState(SEED)

    print("Loading annotations...")
    with open(ANNOTATIONS) as f:
        coco = json.load(f)

    cat_by_id = {c["id"]: c["name"] for c in coco["categories"]}
    img_lookup = {img["id"]: img for img in coco["images"]}
    cat_counts = Counter(a["category_id"] for a in coco["annotations"])

    # Collect product crops from ALL sources
    print("Collecting product images from all sources...")
    cat_crops = {}  # cat_id -> list of (img_bgr, mask)

    # Source 1: COCO annotation crops (up to 5 per category)
    print("  Source 1: COCO annotation crops...")
    for ann in coco["annotations"]:
        cat_id = ann["category_id"]
        if cat_id in cat_crops and len(cat_crops[cat_id]) >= 5:
            continue

        img_info = img_lookup[ann["image_id"]]
        for ext in [".jpg", ".jpeg"]:
            img_path = IMAGES_DIR / img_info["file_name"]
            if not img_path.exists():
                img_path = IMAGES_DIR / img_info["file_name"].replace(".jpg", ".jpeg")
            if img_path.exists():
                break

        if not img_path.exists():
            continue

        img = cv2.imread(str(img_path))
        if img is None:
            continue

        x, y, w, h = [int(v) for v in ann["bbox"]]
        if w < 15 or h < 15:
            continue

        crop = img[max(0, y):y + h, max(0, x):x + w]
        if crop.size == 0:
            continue

        mask = np.ones(crop.shape[:2], dtype=np.uint8) * 255

        if cat_id not in cat_crops:
            cat_crops[cat_id] = []
        cat_crops[cat_id].append((crop, mask))

    print(f"    Crops from {len(cat_crops)} categories")

    # Source 2: Product reference images
    print("  Source 2: Product reference images...")
    metadata_path = PRODUCT_IMAGES_DIR / "metadata.json"
    if metadata_path.exists():
        with open(metadata_path) as f:
            metadata = json.load(f)
        name_to_cat = {name.strip(): cid for cid, name in cat_by_id.items()}
        ref_count = 0
        for entry in metadata.get("products", []):
            code = entry.get("product_code")
            name = entry.get("product_name", "").strip()
            if code and name in name_to_cat:
                cat_id = name_to_cat[name]
                prod_dir = PRODUCT_IMAGES_DIR / str(code)
                if prod_dir.exists():
                    for img_path in list(prod_dir.glob("*.jpg"))[:3] + list(prod_dir.glob("*.png"))[:3]:
                        img = cv2.imread(str(img_path))
                        if img is not None and img.shape[0] > 20 and img.shape[1] > 20:
                            mask = remove_white_bg(img)
                            if cat_id not in cat_crops:
                                cat_crops[cat_id] = []
                            cat_crops[cat_id].append((img, mask))
                            ref_count += 1
        print(f"    Added {ref_count} reference images")

    # Source 3: Gemini-generated photos
    print("  Source 3: Gemini product photos...")
    gemini_count = 0
    for png_path in sorted(GEMINI_DIR.glob("cat_*_gemini_*.png")):
        parts = png_path.stem.split("_")
        try:
            cat_id = int(parts[1])
        except (IndexError, ValueError):
            continue
        if cat_id not in cat_by_id:
            continue

        img = cv2.imread(str(png_path))
        if img is None or img.shape[0] < 30 or img.shape[1] < 30:
            continue

        mask = remove_white_bg(img, threshold=235)
        if cat_id not in cat_crops:
            cat_crops[cat_id] = []
        cat_crops[cat_id].append((img, mask))
        gemini_count += 1

    print(f"    Added {gemini_count} Gemini images")
    print(f"  Total: {sum(len(v) for v in cat_crops.values())} crops across {len(cat_crops)} categories")

    # Build weighted sampling: rare categories get more love
    cat_weights = {}
    for c in cat_crops:
        cat_weights[c] = 1.0 / max(1, cat_counts.get(c, 0))
    total_w = sum(cat_weights.values())
    cats_list = list(cat_weights.keys())
    probs_list = [cat_weights[c] / total_w for c in cats_list]

    # Load shelf backgrounds
    shelf_images = sorted(IMAGES_DIR.glob("*.jpg")) + sorted(IMAGES_DIR.glob("*.jpeg"))
    print(f"Shelf backgrounds: {len(shelf_images)}")

    # Generate!
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_images = OUTPUT_DIR / "images"
    out_labels = OUTPUT_DIR / "labels"
    out_images.mkdir(exist_ok=True)
    out_labels.mkdir(exist_ok=True)

    all_images = []
    all_annotations = []
    ann_id = ANN_ID_START

    for img_idx in range(NUM_IMAGES):
        image_id = IMAGE_ID_START + img_idx

        bg_path = rng.choice(shelf_images)
        bg = cv2.imread(str(bg_path))
        if bg is None:
            continue

        bg_h, bg_w = bg.shape[:2]

        # Random background augmentation
        alpha = rng.uniform(0.7, 1.3)
        beta = rng.uniform(-25, 25)
        bg = np.clip(bg.astype(np.float32) * alpha + beta, 0, 255).astype(np.uint8)

        n_products = rng.randint(PRODUCTS_PER_IMAGE_MIN, PRODUCTS_PER_IMAGE_MAX)
        sampled_cats = rng.choices(cats_list, weights=probs_list, k=n_products)

        img_anns = []
        for cat_id in sampled_cats:
            if not cat_crops.get(cat_id):
                continue

            crop, mask = rng.choice(cat_crops[cat_id])
            crop_t, mask_t = random_transform(crop.copy(), mask.copy(), rng)

            x = rng.randint(0, max(1, bg_w - crop_t.shape[1]))
            y = rng.randint(0, max(1, bg_h - crop_t.shape[0]))

            bbox = paste_product(bg, crop_t, mask_t, x, y)
            if bbox is None:
                continue

            bx, by, bw, bh = bbox
            img_anns.append({
                "id": ann_id,
                "image_id": image_id,
                "category_id": int(cat_id),
                "bbox": [bx, by, bw, bh],
                "area": bw * bh,
                "iscrowd": 0,
            })
            ann_id += 1

        if not img_anns:
            continue

        # Save image
        out_name = f"synth3_{image_id:06d}.jpg"
        cv2.imwrite(str(out_images / out_name), bg, [cv2.IMWRITE_JPEG_QUALITY, 90])

        # Write YOLO label
        lines = []
        for ann in img_anns:
            bx, by, bw, bh = ann["bbox"]
            cx = max(0, min(1, (bx + bw / 2) / bg_w))
            cy = max(0, min(1, (by + bh / 2) / bg_h))
            nw = max(0, min(1, bw / bg_w))
            nh = max(0, min(1, bh / bg_h))
            lines.append(f"{ann['category_id']} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")

        label_path = out_labels / (Path(out_name).stem + ".txt")
        label_path.write_text("\n".join(lines) + "\n")

        all_images.append({
            "id": image_id,
            "file_name": out_name,
            "width": bg_w,
            "height": bg_h,
        })
        all_annotations.extend(img_anns)

        if (img_idx + 1) % 100 == 0:
            print(f"  Generated {img_idx + 1}/{NUM_IMAGES} images, {len(all_annotations)} annotations")

    # Save COCO annotations too
    coco_out = {
        "images": all_images,
        "annotations": all_annotations,
        "categories": coco["categories"],
    }
    (OUTPUT_DIR / "annotations.json").write_text(json.dumps(coco_out))

    synth_cats = Counter(a["category_id"] for a in all_annotations)
    print(f"\nDone! {len(all_images)} images, {len(all_annotations)} annotations")
    print(f"Categories covered: {len(synth_cats)}")
    print(f"Rare categories (< 10 original) covered: {sum(1 for c in synth_cats if cat_counts.get(c, 0) < 10)}")
    print(f"Output: {OUTPUT_DIR}")

    return 0


if __name__ == "__main__":
    exit(main())
