"""
Copy-Paste Data Augmentation for YOLO Retraining.

Generates synthetic training images by pasting product reference photos
onto real shelf backgrounds. Based on CVPR 2021 copy-paste augmentation
research (+6.9 mAP in low-data regimes).

Usage (on GCP VM):
    python3 -m venv .venv && source .venv/bin/activate
    pip install opencv-python-headless numpy Pillow
    python3 copy_paste_augment.py

Inputs:
    - Product reference images: NM_NGD_product_images/ (clean white backgrounds)
    - Product metadata: NM_NGD_product_images/metadata.json
    - Real shelf images: train/images/
    - COCO annotations: train/annotations.json (for category mapping)

Outputs:
    - synthetic_data/images/synthetic_*.jpg
    - synthetic_data/annotations.json (COCO format)
"""

import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
NUM_IMAGES = 250
PRODUCTS_PER_IMAGE_MIN = 5
PRODUCTS_PER_IMAGE_MAX = 15
SCALE_MIN = 0.5
SCALE_MAX = 1.2
ROTATION_MIN = -5
ROTATION_MAX = 5
BRIGHTNESS_RANGE = (0.7, 1.3)
CONTRAST_RANGE = (0.7, 1.3)
IMAGE_ID_START = 10000
ANNOTATION_ID_START = 100000
RANDOM_SEED = 42
PROGRESS_INTERVAL = 25

# Paths -- adjust these if directory layout differs on GCP
SCRIPT_DIR = Path(__file__).resolve().parent
AGENT_CV_DIR = SCRIPT_DIR.parent
# Training data is expected to be at the same level as the agent-cv worktree
# On GCP, adjust TRAININGDATA_DIR to wherever you upload the data
TRAININGDATA_DIR = AGENT_CV_DIR.parent.parent / "nmiai-2026-main" / "trainingdata"

PRODUCT_IMAGES_DIR = TRAININGDATA_DIR / "NM_NGD_product_images"
METADATA_JSON = PRODUCT_IMAGES_DIR / "metadata.json"
SHELF_IMAGES_DIR = TRAININGDATA_DIR / "train" / "images"
ANNOTATIONS_JSON = TRAININGDATA_DIR / "train" / "annotations.json"

OUTPUT_DIR = AGENT_CV_DIR / "synthetic_data"
OUTPUT_IMAGES_DIR = OUTPUT_DIR / "images"
OUTPUT_ANNOTATIONS = OUTPUT_DIR / "annotations.json"


# ---------------------------------------------------------------------------
# Helper: remove white background from product image
# ---------------------------------------------------------------------------
def remove_white_background(img_bgr):
    """Remove white/light background from a product image.

    The reference images have clean white backgrounds. We threshold
    on brightness to create a binary foreground mask, then clean it
    up with morphological operations.

    Returns (img_bgra, mask) where mask is 255=foreground, 0=background.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    # Pixels brighter than 240 are considered background
    _, mask = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)

    # Clean up the mask
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    # Build BGRA image (4-channel with alpha)
    img_bgra = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2BGRA)
    img_bgra[:, :, 3] = mask

    return img_bgra, mask


# ---------------------------------------------------------------------------
# Helper: apply random lighting jitter to a product cutout
# ---------------------------------------------------------------------------
def apply_lighting_jitter(img_bgr, rng):
    """Apply random brightness and contrast jitter.

    This helps the pasted product match varied shelf lighting conditions.
    """
    brightness_factor = rng.uniform(*BRIGHTNESS_RANGE)
    contrast_factor = rng.uniform(*CONTRAST_RANGE)

    img_float = img_bgr.astype(np.float32)

    # Contrast: scale around mean
    mean = img_float.mean()
    img_float = (img_float - mean) * contrast_factor + mean

    # Brightness: multiplicative
    img_float = img_float * brightness_factor

    return np.clip(img_float, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# Helper: rotate image with alpha channel
# ---------------------------------------------------------------------------
def rotate_with_alpha(img_bgra, angle):
    """Rotate an BGRA image by angle degrees, expanding the canvas as needed."""
    h, w = img_bgra.shape[:2]
    center = (w / 2, h / 2)

    # Compute rotation matrix
    M = cv2.getRotationMatrix2D(center, angle, 1.0)

    # Compute new bounding box size
    cos_a = abs(M[0, 0])
    sin_a = abs(M[0, 1])
    new_w = int(h * sin_a + w * cos_a)
    new_h = int(h * cos_a + w * sin_a)

    # Adjust the rotation matrix for the new center
    M[0, 2] += (new_w / 2) - center[0]
    M[1, 2] += (new_h / 2) - center[1]

    rotated = cv2.warpAffine(
        img_bgra, M, (new_w, new_h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )
    return rotated


# ---------------------------------------------------------------------------
# Helper: paste product onto background using alpha blending
# ---------------------------------------------------------------------------
def paste_product(background, product_bgra, x, y):
    """Alpha-blend a product cutout onto the background at position (x, y).

    x, y is the top-left corner. Products that extend beyond the background
    are clipped. Returns the actual bounding box (x, y, w, h) of what was
    pasted, or None if the paste is completely off-canvas.
    """
    bg_h, bg_w = background.shape[:2]
    pr_h, pr_w = product_bgra.shape[:2]

    # Compute the region of the product that falls within the background
    x1_bg = max(0, x)
    y1_bg = max(0, y)
    x2_bg = min(bg_w, x + pr_w)
    y2_bg = min(bg_h, y + pr_h)

    if x1_bg >= x2_bg or y1_bg >= y2_bg:
        return None  # Completely off-canvas

    # Corresponding region in the product image
    x1_pr = x1_bg - x
    y1_pr = y1_bg - y
    x2_pr = x1_pr + (x2_bg - x1_bg)
    y2_pr = y1_pr + (y2_bg - y1_bg)

    # Extract alpha channel and create float masks
    alpha = product_bgra[y1_pr:y2_pr, x1_pr:x2_pr, 3].astype(np.float32) / 255.0
    alpha_3ch = alpha[:, :, np.newaxis]

    # Blend
    bg_region = background[y1_bg:y2_bg, x1_bg:x2_bg].astype(np.float32)
    pr_region = product_bgra[y1_pr:y2_pr, x1_pr:x2_pr, :3].astype(np.float32)

    blended = pr_region * alpha_3ch + bg_region * (1.0 - alpha_3ch)
    background[y1_bg:y2_bg, x1_bg:x2_bg] = blended.astype(np.uint8)

    # Return the visible bounding box (COCO format: x, y, w, h)
    visible_w = x2_bg - x1_bg
    visible_h = y2_bg - y1_bg

    # Only count as valid if at least 20% of the product is visible
    original_area = pr_w * pr_h
    visible_area = visible_w * visible_h
    if visible_area < 0.2 * original_area:
        return None

    return (x1_bg, y1_bg, visible_w, visible_h)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def main():
    rng = np.random.RandomState(RANDOM_SEED)

    # ------------------------------------------------------------------
    # 1. Load metadata and build product_code -> category_id mapping
    # ------------------------------------------------------------------
    print("Loading metadata and annotations...")

    with open(METADATA_JSON) as f:
        metadata = json.load(f)

    with open(ANNOTATIONS_JSON) as f:
        coco_data = json.load(f)

    # Build name -> category_id lookup from COCO annotations
    cat_name_to_id = {cat["name"]: cat["id"] for cat in coco_data["categories"]}

    # Build list of available products: (product_code, category_id, image_path)
    products = []
    for p in metadata["products"]:
        if not p["has_images"]:
            continue
        name = p["product_name"]
        cat_id = cat_name_to_id.get(name)
        if cat_id is None:
            continue  # Product not in annotation categories

        product_dir = PRODUCT_IMAGES_DIR / p["product_code"]

        # Prefer main.jpg, fall back to front.jpg
        if "main" in p["image_types"]:
            img_path = product_dir / "main.jpg"
        elif "front" in p["image_types"]:
            img_path = product_dir / "front.jpg"
        else:
            continue  # No usable image

        if img_path.exists():
            products.append({
                "product_code": p["product_code"],
                "product_name": name,
                "category_id": cat_id,
                "image_path": str(img_path),
            })

    print(f"Loaded {len(products)} products with images and valid category IDs")

    # ------------------------------------------------------------------
    # 2. Load list of shelf background images
    # ------------------------------------------------------------------
    shelf_images = sorted(SHELF_IMAGES_DIR.glob("*.jpg"))
    print(f"Loaded {len(shelf_images)} shelf background images")

    if not shelf_images:
        print("ERROR: No shelf images found. Check SHELF_IMAGES_DIR path.")
        return
    if not products:
        print("ERROR: No valid products found. Check paths and metadata.")
        return

    # ------------------------------------------------------------------
    # 3. Pre-load and process all product cutouts (with background removal)
    # ------------------------------------------------------------------
    print("Pre-processing product images (background removal)...")
    product_cutouts = []  # List of (category_id, bgra_image, original_h, original_w)
    failed = 0

    for i, prod in enumerate(products):
        img_bgr = cv2.imread(prod["image_path"])
        if img_bgr is None:
            failed += 1
            continue

        img_bgra, mask = remove_white_background(img_bgr)

        # Skip if mask is mostly empty (failed background removal)
        foreground_ratio = np.count_nonzero(mask) / mask.size
        if foreground_ratio < 0.05:
            failed += 1
            continue

        product_cutouts.append({
            "category_id": prod["category_id"],
            "product_name": prod["product_name"],
            "bgra": img_bgra,
            "h": img_bgra.shape[0],
            "w": img_bgra.shape[1],
        })

        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{len(products)} products...")

    print(f"Successfully processed {len(product_cutouts)} product cutouts ({failed} failed)")

    # ------------------------------------------------------------------
    # 4. Generate synthetic images
    # ------------------------------------------------------------------
    print(f"\nGenerating {NUM_IMAGES} synthetic images...")

    OUTPUT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    coco_images = []
    coco_annotations = []
    annotation_id = ANNOTATION_ID_START
    categories_used = set()

    for img_idx in range(NUM_IMAGES):
        image_id = IMAGE_ID_START + img_idx

        # A. Pick random shelf background
        bg_path = shelf_images[rng.randint(0, len(shelf_images))]
        background = cv2.imread(str(bg_path))
        if background is None:
            print(f"  WARNING: Could not read {bg_path}, skipping")
            continue

        bg_h, bg_w = background.shape[:2]

        # B. Pick 5-15 random products
        num_products = rng.randint(PRODUCTS_PER_IMAGE_MIN, PRODUCTS_PER_IMAGE_MAX + 1)
        selected_indices = rng.choice(len(product_cutouts), size=num_products, replace=True)

        # C. Paste each product
        for prod_idx in selected_indices:
            cutout = product_cutouts[prod_idx]
            orig_h, orig_w = cutout["h"], cutout["w"]
            bgra = cutout["bgra"].copy()

            # Random scale
            scale = rng.uniform(SCALE_MIN, SCALE_MAX)

            # Scale product relative to background height for realism
            # Target product height: 5-20% of background height
            target_height_ratio = rng.uniform(0.05, 0.20)
            base_scale = (bg_h * target_height_ratio) / orig_h
            final_scale = base_scale * scale

            new_w = max(10, int(orig_w * final_scale))
            new_h = max(10, int(orig_h * final_scale))

            # Resize
            bgra_resized = cv2.resize(bgra, (new_w, new_h), interpolation=cv2.INTER_AREA)

            # Apply lighting jitter to BGR channels only
            bgr_jittered = apply_lighting_jitter(bgra_resized[:, :, :3], rng)
            bgra_resized[:, :, :3] = bgr_jittered

            # Random rotation (-5 to +5 degrees)
            angle = rng.uniform(ROTATION_MIN, ROTATION_MAX)
            if abs(angle) > 0.5:  # Only rotate if meaningful
                bgra_resized = rotate_with_alpha(bgra_resized, angle)

            # Random position
            pr_h, pr_w = bgra_resized.shape[:2]
            # Allow slight overflow at edges (products can be partially off-shelf)
            margin = 0.1
            x = rng.randint(int(-pr_w * margin), max(1, bg_w - int(pr_w * (1 - margin))))
            y = rng.randint(int(-pr_h * margin), max(1, bg_h - int(pr_h * (1 - margin))))

            # Paste with alpha blending
            bbox = paste_product(background, bgra_resized, x, y)

            if bbox is not None:
                bx, by, bw, bh = bbox
                coco_annotations.append({
                    "id": annotation_id,
                    "image_id": image_id,
                    "category_id": cutout["category_id"],
                    "bbox": [int(bx), int(by), int(bw), int(bh)],
                    "area": int(bw * bh),
                    "iscrowd": 0,
                })
                annotation_id += 1
                categories_used.add(cutout["category_id"])

        # D. Save the synthetic image
        out_filename = f"synthetic_{img_idx + 1:04d}.jpg"
        out_path = OUTPUT_IMAGES_DIR / out_filename
        cv2.imwrite(str(out_path), background, [cv2.IMWRITE_JPEG_QUALITY, 92])

        coco_images.append({
            "id": image_id,
            "file_name": out_filename,
            "width": bg_w,
            "height": bg_h,
        })

        # Progress
        if (img_idx + 1) % PROGRESS_INTERVAL == 0 or (img_idx + 1) == NUM_IMAGES:
            print(f"  Generated {img_idx + 1}/{NUM_IMAGES} images "
                  f"({len(coco_annotations)} annotations so far)")

    # ------------------------------------------------------------------
    # 5. Write COCO annotations file
    # ------------------------------------------------------------------
    coco_output = {
        "images": coco_images,
        "categories": coco_data["categories"],  # Same categories as real data
        "annotations": coco_annotations,
    }

    with open(OUTPUT_ANNOTATIONS, "w") as f:
        json.dump(coco_output, f, indent=2)

    # ------------------------------------------------------------------
    # 6. Print statistics
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("COPY-PASTE AUGMENTATION COMPLETE")
    print("=" * 60)
    print(f"Total synthetic images:   {len(coco_images)}")
    print(f"Total annotations:        {len(coco_annotations)}")
    print(f"Unique categories used:   {len(categories_used)} / {len(coco_data['categories'])}")
    print(f"Avg annotations/image:    {len(coco_annotations) / max(1, len(coco_images)):.1f}")
    print(f"Output images:            {OUTPUT_IMAGES_DIR}")
    print(f"Output annotations:       {OUTPUT_ANNOTATIONS}")
    print(f"Image ID range:           {IMAGE_ID_START} - {IMAGE_ID_START + len(coco_images) - 1}")
    print(f"Annotation ID range:      {ANNOTATION_ID_START} - {annotation_id - 1}")
    print("=" * 60)


if __name__ == "__main__":
    main()
