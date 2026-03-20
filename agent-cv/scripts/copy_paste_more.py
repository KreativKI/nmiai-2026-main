#!/usr/bin/env python3
"""Generate MORE copy-paste augmented images for YOLO training.

We already have 140 synthetic images. This generates 360 more (total 500).
Targets rare categories (< 10 instances) for maximum impact.

Usage (on GCP cv-train-1):
    source ~/cv-train/venv/bin/activate
    python3 ~/copy_paste_more.py
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
OUTPUT_DIR = Path("/home/jcfrugaard/synthetic_data_v2")

NUM_IMAGES = 360
PRODUCTS_PER_IMAGE_MIN = 5
PRODUCTS_PER_IMAGE_MAX = 12
IMAGE_ID_START = 20000
ANN_ID_START = 200000
SEED = 123


def remove_white_bg(img_bgr):
    """Remove white background from product image."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    return mask


def paste_product(background, product_img, mask, x, y, scale):
    """Paste a product onto a background at (x, y) with given scale."""
    h, w = product_img.shape[:2]
    new_h, new_w = int(h * scale), int(w * scale)
    if new_h < 10 or new_w < 10:
        return None

    resized = cv2.resize(product_img, (new_w, new_h))
    resized_mask = cv2.resize(mask, (new_w, new_h))

    bg_h, bg_w = background.shape[:2]
    # Clip to background bounds
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(bg_w, x + new_w)
    y2 = min(bg_h, y + new_h)

    # Source region
    sx1 = x1 - x
    sy1 = y1 - y
    sx2 = sx1 + (x2 - x1)
    sy2 = sy1 + (y2 - y1)

    if x2 - x1 < 5 or y2 - y1 < 5:
        return None

    roi = background[y1:y2, x1:x2]
    src = resized[sy1:sy2, sx1:sx2]
    m = resized_mask[sy1:sy2, sx1:sx2]

    m3 = cv2.merge([m, m, m]).astype(np.float32) / 255.0
    blended = (src.astype(np.float32) * m3 + roi.astype(np.float32) * (1 - m3)).astype(np.uint8)
    background[y1:y2, x1:x2] = blended

    return (x1, y1, x2 - x1, y2 - y1)


def load_product_images(product_dir):
    """Load all product reference images from a product directory."""
    imgs = []
    for ext in ("*.jpg", "*.jpeg", "*.png"):
        for p in product_dir.glob(ext):
            img = cv2.imread(str(p))
            if img is not None:
                imgs.append(img)
    return imgs


def main():
    random.seed(SEED)
    np.random.seed(SEED)

    print("Loading annotations...")
    with open(ANNOTATIONS) as f:
        coco = json.load(f)

    cat_by_id = {c["id"]: c["name"] for c in coco["categories"]}
    img_lookup = {img["id"]: img for img in coco["images"]}

    # Count instances per category
    cat_counts = Counter(a["category_id"] for a in coco["annotations"])

    # Map category names to product directories via metadata
    metadata_path = PRODUCT_IMAGES_DIR / "metadata.json"
    cat_to_products = {}

    if metadata_path.exists():
        with open(metadata_path) as f:
            metadata = json.load(f)
        # Build name -> category_id mapping
        name_to_cat = {name.strip(): cid for cid, name in cat_by_id.items()}
        for entry in metadata.get("products", []):
            code = entry.get("product_code")
            name = entry.get("product_name", "").strip()
            if code and name in name_to_cat:
                cat_id = name_to_cat[name]
                prod_dir = PRODUCT_IMAGES_DIR / str(code)
                if prod_dir.exists():
                    cat_to_products.setdefault(cat_id, []).append(prod_dir)
        print(f"Mapped {len(cat_to_products)} categories to product reference images")

    # If we don't have product reference images, use annotation crops
    # Extract crops from training images for categories with few examples
    print("Extracting product crops from training annotations...")
    cat_crops = {}
    for ann in coco["annotations"]:
        cat_id = ann["category_id"]
        if cat_id in cat_crops and len(cat_crops[cat_id]) >= 3:
            continue  # Already have enough crops

        img_info = img_lookup[ann["image_id"]]
        img_path = IMAGES_DIR / img_info["file_name"]
        if not img_path.exists():
            # Try .jpeg
            img_path = IMAGES_DIR / img_info["file_name"].replace(".jpg", ".jpeg")
            if not img_path.exists():
                continue

        img = cv2.imread(str(img_path))
        if img is None:
            continue

        x, y, w, h = ann["bbox"]
        x, y, w, h = int(x), int(y), int(w), int(h)
        if w < 10 or h < 10:
            continue

        crop = img[max(0, y):y + h, max(0, x):x + w]
        if crop.size == 0:
            continue

        if cat_id not in cat_crops:
            cat_crops[cat_id] = []
        cat_crops[cat_id].append(crop)

    print(f"Extracted crops for {len(cat_crops)} categories")

    # Also load product reference images where available
    for cat_id, prod_dirs in cat_to_products.items():
        for prod_dir in prod_dirs:
            imgs = load_product_images(prod_dir)
            if imgs:
                if cat_id not in cat_crops:
                    cat_crops[cat_id] = []
                cat_crops[cat_id].extend(imgs)

    # Priority: categories with fewest examples get more synthetic images
    rare_cats = sorted(cat_counts.keys(), key=lambda c: cat_counts[c])
    # Weight: inverse frequency
    cat_weights = {}
    for c in rare_cats:
        if c in cat_crops:
            cat_weights[c] = 1.0 / max(1, cat_counts[c])

    total_weight = sum(cat_weights.values())
    cat_probs = {c: w / total_weight for c, w in cat_weights.items()}

    # Load shelf backgrounds
    shelf_images = sorted(IMAGES_DIR.glob("*.jpg")) + sorted(IMAGES_DIR.glob("*.jpeg"))
    print(f"Shelf backgrounds: {len(shelf_images)}")

    if not shelf_images:
        print("ERROR: No shelf images found")
        return 1

    # Create output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_images = OUTPUT_DIR / "images"
    out_images.mkdir(exist_ok=True)

    all_images = []
    all_annotations = []
    ann_id = ANN_ID_START

    cats_list = list(cat_probs.keys())
    probs_list = [cat_probs[c] for c in cats_list]

    for img_idx in range(NUM_IMAGES):
        image_id = IMAGE_ID_START + img_idx

        # Pick random shelf background
        bg_path = random.choice(shelf_images)
        bg = cv2.imread(str(bg_path))
        if bg is None:
            continue

        bg_h, bg_w = bg.shape[:2]

        # Apply random brightness/contrast jitter to background
        alpha = random.uniform(0.7, 1.3)  # contrast
        beta = random.uniform(-20, 20)  # brightness
        bg = np.clip(bg.astype(np.float32) * alpha + beta, 0, 255).astype(np.uint8)

        n_products = random.randint(PRODUCTS_PER_IMAGE_MIN, PRODUCTS_PER_IMAGE_MAX)

        # Sample categories weighted by rarity
        sampled_cats = random.choices(cats_list, weights=probs_list, k=n_products)

        for cat_id in sampled_cats:
            if cat_id not in cat_crops or not cat_crops[cat_id]:
                continue

            crop = random.choice(cat_crops[cat_id])
            mask = remove_white_bg(crop)

            # Random scale and position
            scale = random.uniform(0.4, 1.5)
            x = random.randint(0, max(1, bg_w - int(crop.shape[1] * scale)))
            y = random.randint(0, max(1, bg_h - int(crop.shape[0] * scale)))

            # Random color jitter on product
            hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV).astype(np.float32)
            hsv[:, :, 0] = (hsv[:, :, 0] + random.uniform(-5, 5)) % 180
            hsv[:, :, 1] = np.clip(hsv[:, :, 1] * random.uniform(0.8, 1.2), 0, 255)
            hsv[:, :, 2] = np.clip(hsv[:, :, 2] * random.uniform(0.7, 1.3), 0, 255)
            crop_jittered = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

            bbox = paste_product(bg, crop_jittered, mask, x, y, scale)
            if bbox is None:
                continue

            bx, by, bw, bh = bbox
            all_annotations.append({
                "id": ann_id,
                "image_id": image_id,
                "category_id": int(cat_id),
                "bbox": [bx, by, bw, bh],
                "area": bw * bh,
                "iscrowd": 0,
            })
            ann_id += 1

        # Save image
        out_name = f"synthetic_{image_id:05d}.jpg"
        cv2.imwrite(str(out_images / out_name), bg, [cv2.IMWRITE_JPEG_QUALITY, 90])

        all_images.append({
            "id": image_id,
            "file_name": out_name,
            "width": bg_w,
            "height": bg_h,
        })

        if (img_idx + 1) % 50 == 0:
            print(f"  Generated {img_idx + 1}/{NUM_IMAGES} images, {ann_id - ANN_ID_START} annotations")

    # Save COCO annotations
    coco_out = {
        "images": all_images,
        "annotations": all_annotations,
        "categories": coco["categories"],
    }
    ann_path = OUTPUT_DIR / "annotations.json"
    with open(ann_path, "w") as f:
        json.dump(coco_out, f)

    # Also convert to YOLO format
    out_labels = OUTPUT_DIR / "labels"
    out_labels.mkdir(exist_ok=True)

    for img_info in all_images:
        iid = img_info["id"]
        w, h = img_info["width"], img_info["height"]
        anns = [a for a in all_annotations if a["image_id"] == iid]

        lines = []
        for ann in anns:
            bx, by, bw, bh = ann["bbox"]
            cx = (bx + bw / 2) / w
            cy = (by + bh / 2) / h
            nw = bw / w
            nh = bh / h
            cx = max(0, min(1, cx))
            cy = max(0, min(1, cy))
            nw = max(0, min(1, nw))
            nh = max(0, min(1, nh))
            lines.append(f"{ann['category_id']} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")

        label_path = out_labels / (Path(img_info["file_name"]).stem + ".txt")
        label_path.write_text("\n".join(lines) + "\n" if lines else "")

    print(f"\nDone! Generated {len(all_images)} images, {len(all_annotations)} annotations")
    print(f"Output: {OUTPUT_DIR}")
    print(f"  Images: {out_images}")
    print(f"  Labels (YOLO): {out_labels}")
    print(f"  Annotations (COCO): {ann_path}")

    # Stats
    synth_cats = Counter(a["category_id"] for a in all_annotations)
    print(f"\nCategories covered: {len(synth_cats)}")
    rare_covered = sum(1 for c in synth_cats if cat_counts.get(c, 0) < 10)
    print(f"Rare categories (< 10 original instances) covered: {rare_covered}")

    return 0


if __name__ == "__main__":
    exit(main())
