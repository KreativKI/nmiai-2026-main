"""
Gemini 3.1 Flash multi-reference shelf generation.

Generates realistic grocery shelf images for weak product categories.
Uses ALL available reference images (studio photos + shelf crops) per product.

Priority order: seen_once (10 each) > barely_known (8) > somewhat_known (5).

Deploy to GCP VMs:
  VM1 (cv-train-1): first half of categories
  VM2 (cv-train-3): second half of categories

Usage:
  python gemini_shelf_gen.py --split 0  # first half (VM1)
  python gemini_shelf_gen.py --split 1  # second half (VM2)
  python gemini_shelf_gen.py            # all categories (single VM)
"""
import argparse
import json
import time
import io
import traceback
from pathlib import Path
from collections import Counter
from PIL import Image

# --- Paths (GCP VM) ---
ANNOTATIONS_PATH = Path.home() / "trainingdata/train/annotations.json"
IMAGES_DIR = Path.home() / "trainingdata/train/images"
PRODUCT_IMAGES_DIR = Path.home() / "trainingdata/NM_NGD_product_images"
METADATA_PATH = PRODUCT_IMAGES_DIR / "metadata.json"
OUTPUT_DIR = Path.home() / "gemini_shelf_gen"
PROGRESS_FILE = OUTPUT_DIR / "progress.json"

# --- Generation config per tier ---
TIER_CONFIG = {
    "seen_once": {"max_annotations": 1, "variations": 10},
    "barely_known": {"max_annotations": 2, "variations": 8},
    "somewhat_known": {"max_annotations": 9, "variations": 5},
}

# Shelf scene prompts (varied for diversity)
SHELF_PROMPTS = [
    "Generate a photorealistic image of this exact product ({name}) sitting on a Norwegian grocery store shelf. "
    "The product is clearly visible with its front label facing the camera. "
    "The shelf has price tags and other products nearby. Natural supermarket lighting.",

    "Show this exact product ({name}) as the last remaining item on a partially empty grocery shelf. "
    "Realistic Norwegian supermarket setting with visible shelf labels. The product is clearly identifiable.",

    "This exact product ({name}) displayed on a well-stocked Norwegian grocery store shelf, "
    "surrounded by similar products. The product stands out and its label is fully readable. "
    "Professional retail photography quality.",

    "A close-up of this product ({name}) on a grocery store shelf at eye level. "
    "Norwegian supermarket environment. Good lighting, front label visible. "
    "Some competing products visible on either side.",

    "This product ({name}) photographed from a slight angle on a Norwegian grocery shelf. "
    "The shelf is made of metal with price labels below. The product occupies about 30% of the frame. "
    "Other grocery items visible in the background.",

    "A realistic photo of this product ({name}) in a Norwegian grocery store cooler/shelf section. "
    "The product label is clearly readable. Natural fluorescent lighting. "
    "Shopping environment looks authentic.",

    "This exact product ({name}) on a bottom shelf of a Norwegian grocery store. "
    "Slightly looking down at the product. Front label visible. "
    "Other products on shelves above and beside it.",

    "This product ({name}) being restocked on a Norwegian grocery shelf. "
    "The product is placed front-facing. Clean, well-lit retail environment. "
    "Shelf is partially filled with products.",

    "A straight-on product shot of this item ({name}) on a Norwegian grocery store shelf. "
    "Product takes up about 25% of the image. Surrounding products visible. "
    "Typical supermarket fluorescent lighting.",

    "This product ({name}) displayed prominently at the front of a Norwegian grocery shelf. "
    "Price tag visible below. Label facing camera. Other items in the background. "
    "Looks like a real shopping photo.",
]


def load_progress():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {}


def save_progress(progress):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def get_reference_images(cat_id, cat_name, ean, best_crop_info):
    """Collect ALL reference images for a product: studio photos + shelf crop."""
    refs = []

    # Studio photos (front, main, back, left, right, top, bottom)
    if ean:
        ean_dir = PRODUCT_IMAGES_DIR / ean
        if ean_dir.is_dir():
            # Prioritize front and main
            priority = ["front.jpg", "main.jpg", "back.jpg", "left.jpg", "right.jpg"]
            for fname in priority:
                fpath = ean_dir / fname
                if fpath.exists():
                    try:
                        img = Image.open(fpath)
                        img.thumbnail((512, 512))  # Keep reasonable size
                        refs.append(("studio_" + fname, img))
                    except Exception:
                        pass

    # Shelf crop from training data (largest annotation)
    if best_crop_info:
        img_path = IMAGES_DIR / best_crop_info["image"]["file_name"]
        bbox = best_crop_info["annotation"]["bbox"]
        x, y, w, h = bbox
        try:
            img = Image.open(img_path)
            pad_w, pad_h = w * 0.05, h * 0.05
            crop = img.crop((
                max(0, x - pad_w), max(0, y - pad_h),
                min(img.width, x + w + pad_w), min(img.height, y + h + pad_h),
            ))
            crop.thumbnail((512, 512))
            refs.append(("shelf_crop", crop))
        except Exception:
            pass

    return refs


def image_to_bytes(img, fmt="JPEG"):
    buf = io.BytesIO()
    if img.mode == "RGBA":
        img = img.convert("RGB")
    img.save(buf, format=fmt, quality=90)
    return buf.getvalue()


def generate_one(client, types, refs, product_name, prompt_idx):
    """Generate one shelf image using multi-reference input."""
    prompt = SHELF_PROMPTS[prompt_idx % len(SHELF_PROMPTS)].format(name=product_name)

    # Build content: all reference images + prompt
    contents = []
    for ref_name, ref_img in refs:
        img_bytes = image_to_bytes(ref_img)
        contents.append(types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"))

    contents.append(
        f"Above are reference photos of the product '{product_name}'. "
        f"Using these as reference for what the product looks like, {prompt}"
    )

    response = client.models.generate_content(
        model="gemini-3.1-flash-image-preview",
        contents=contents,
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
        ),
    )

    # Extract generated image
    for part in response.candidates[0].content.parts:
        if hasattr(part, "inline_data") and part.inline_data and part.inline_data.data:
            return Image.open(io.BytesIO(part.inline_data.data))

    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", type=int, default=-1,
                        help="0=first half, 1=second half, -1=all")
    parser.add_argument("--weak-only", action="store_true", default=True,
                        help="Only generate for weak categories (<=9 annotations)")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading annotations...")
    with open(ANNOTATIONS_PATH) as f:
        coco = json.load(f)

    print("Loading product metadata...")
    with open(METADATA_PATH) as f:
        meta = json.load(f)

    cats = {c["id"]: c["name"] for c in coco["categories"]}
    img_lookup = {img["id"]: img for img in coco["images"]}
    cat_counts = Counter(a["category_id"] for a in coco["annotations"])

    # Build name -> EAN mapping
    product_by_name = {}
    for p in meta["products"]:
        if p["has_images"]:
            product_by_name[p["product_name"].strip().upper()] = p["product_code"]

    cat_to_ean = {}
    for cat_id, cat_name in cats.items():
        cn = cat_name.strip().upper()
        if cn in product_by_name:
            cat_to_ean[cat_id] = product_by_name[cn]

    # Find best crop per category
    best_crops = {}
    for ann_entry in coco["annotations"]:
        cat_id = ann_entry["category_id"]
        area = ann_entry["bbox"][2] * ann_entry["bbox"][3]
        if cat_id not in best_crops or area > best_crops[cat_id]["area"]:
            best_crops[cat_id] = {
                "annotation": ann_entry,
                "area": area,
                "image": img_lookup[ann_entry["image_id"]],
            }

    # Build generation queue: weak categories with reference images
    queue = []
    for cat_id in range(355):  # Skip 355 (unknown_product)
        count = cat_counts.get(cat_id, 0)
        has_ean = cat_id in cat_to_ean
        has_crop = cat_id in best_crops

        if not (has_ean or has_crop):
            continue  # No reference images at all

        if count <= 1:
            tier = "seen_once"
        elif count == 2:
            tier = "barely_known"
        elif count <= 9:
            tier = "somewhat_known"
        else:
            if args.weak_only:
                continue  # Skip well-known
            tier = "well_known"

        variations = TIER_CONFIG.get(tier, {}).get("variations", 3)
        queue.append({
            "cat_id": cat_id,
            "name": cats[cat_id],
            "ean": cat_to_ean.get(cat_id),
            "tier": tier,
            "count": count,
            "variations": variations,
            "crop_info": best_crops.get(cat_id),
        })

    # Sort: weakest first
    tier_order = {"seen_once": 0, "barely_known": 1, "somewhat_known": 2, "well_known": 3}
    queue.sort(key=lambda x: (tier_order[x["tier"]], x["count"]))

    # Apply split
    if args.split == 0:
        queue = queue[:len(queue) // 2]
        print(f"SPLIT 0: Taking first half ({len(queue)} categories)")
    elif args.split == 1:
        queue = queue[len(queue) // 2:]
        print(f"SPLIT 1: Taking second half ({len(queue)} categories)")

    total_images = sum(q["variations"] for q in queue)
    print(f"\nGeneration plan:")
    for tier in ["seen_once", "barely_known", "somewhat_known"]:
        tier_items = [q for q in queue if q["tier"] == tier]
        tier_imgs = sum(q["variations"] for q in tier_items)
        print(f"  {tier}: {len(tier_items)} categories, {tier_imgs} images")
    print(f"  TOTAL: {len(queue)} categories, {total_images} images")
    print(f"  Estimated time: {total_images * 36 / 3600:.1f}h at 36s/image")

    # Load progress (resume support)
    progress = load_progress()

    # Init Gemini
    print("\nInitializing Gemini...")
    from google import genai
    from google.genai import types
    client = genai.Client(vertexai=True, project="ai-nm26osl-1779", location="global")

    success = 0
    errors = 0
    skipped = 0

    for qi, item in enumerate(queue):
        cat_id = item["cat_id"]
        cat_key = str(cat_id)
        product_name = item["name"]
        variations = item["variations"]

        # Check progress
        done_count = 0
        if cat_key in progress:
            done_count = sum(1 for v in progress[cat_key].get("variants", {}).values()
                            if v.get("status") == "OK")

        if done_count >= variations:
            skipped += 1
            continue

        # Collect reference images
        refs = get_reference_images(cat_id, product_name, item["ean"], item["crop_info"])
        if not refs:
            print(f"[{qi+1}/{len(queue)}] cat {cat_id}: {product_name} -- NO REFERENCES, skipping")
            continue

        print(f"\n[{qi+1}/{len(queue)}] cat {cat_id} ({item['tier']}): {product_name}")
        print(f"  References: {len(refs)} images ({', '.join(r[0] for r in refs)})")
        print(f"  Generating {variations} shelf images (done: {done_count})...")

        if cat_key not in progress:
            progress[cat_key] = {"name": product_name, "tier": item["tier"], "variants": {}}

        cat_dir = OUTPUT_DIR / f"cat_{cat_id:03d}"
        cat_dir.mkdir(exist_ok=True)

        for v in range(variations):
            v_key = f"v{v}"
            if progress[cat_key]["variants"].get(v_key, {}).get("status") == "OK":
                continue  # Already done

            out_path = cat_dir / f"cat_{cat_id:03d}_shelf_v{v:02d}.jpg"
            print(f"  v{v}...", end=" ", flush=True)

            try:
                gen_img = generate_one(client, types, refs, product_name, v)
                if gen_img:
                    gen_img = gen_img.convert("RGB")
                    gen_img.save(out_path, quality=95)
                    print(f"OK ({gen_img.width}x{gen_img.height})")
                    progress[cat_key]["variants"][v_key] = {
                        "status": "OK",
                        "size": f"{gen_img.width}x{gen_img.height}",
                        "path": str(out_path),
                    }
                    success += 1
                else:
                    print("NO IMAGE")
                    progress[cat_key]["variants"][v_key] = {"status": "NO_IMAGE"}
                    errors += 1
            except Exception as e:
                err_msg = str(e)[:200]
                print(f"ERROR: {err_msg}")
                progress[cat_key]["variants"][v_key] = {"status": "ERROR", "error": err_msg}
                errors += 1

                # If rate limited, wait longer
                if "429" in err_msg or "quota" in err_msg.lower():
                    print("  Rate limited! Waiting 60s...")
                    time.sleep(60)

            time.sleep(3)  # Normal delay between requests

        save_progress(progress)

    if skipped:
        print(f"\nSkipped (already done): {skipped}")
    print(f"\n=== DONE ===")
    print(f"Generated: {success}, Errors: {errors}")

    # Summary
    total_ok = sum(
        sum(1 for v in cat.get("variants", {}).values() if v.get("status") == "OK")
        for cat in progress.values()
    )
    print(f"Total images generated so far: {total_ok}")


if __name__ == "__main__":
    main()
