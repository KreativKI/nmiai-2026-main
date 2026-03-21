"""
Gemini shelf generation PASS 2: Varied conditions.

Same products as pass 1, but with deliberately different:
- Lighting (harsh fluorescent, warm, dim, shadows)
- Shelf messiness (tilted products, gaps, overcrowded)
- Camera angles (low angle, high angle, slight tilt)
- Distance (close-up, medium, wide shot)
- Shelf fullness (nearly empty, overstocked, restocking)

This creates training diversity so the model generalizes better.

Uses images already generated in pass 1 as ADDITIONAL context
(Gemini can use up to 14 reference images).
"""
import argparse
import json
import time
import io
from pathlib import Path
from collections import Counter
from PIL import Image

from google import genai
from google.genai import types

# Varied prompts for diversity - each creates a different "look"
VARIED_PROMPTS = [
    # Lighting variations
    "Generate a photorealistic image of this product ({name}) on a Norwegian grocery store shelf. "
    "The lighting is harsh overhead fluorescent, creating slight shadows below the shelf edge. "
    "The product's front label is clearly readable. Other products nearby.",

    "This product ({name}) on a grocery shelf photographed in warm evening lighting. "
    "The store is about to close, softer yellowish light from above. "
    "Product clearly visible, label readable. Norwegian supermarket.",

    "This product ({name}) in a dimly lit section of a Norwegian grocery store. "
    "Some products are in shadow, but this product is well-lit from the shelf lighting above. "
    "Realistic, slightly moody atmosphere. Label readable.",

    # Messy/realistic shelf variations
    "This product ({name}) on a messy Norwegian grocery store shelf mid-day. "
    "Some nearby products are slightly tilted or pushed back. A gap in the shelf next to this product. "
    "Realistic shopping environment, not perfectly arranged. Label visible.",

    "This product ({name}) on an overcrowded Norwegian grocery shelf. "
    "Products are packed tightly together, some overlapping slightly. "
    "This product is squeezed between other items but its label is still readable.",

    "A Norwegian grocery shelf being restocked. This product ({name}) is placed "
    "at the front of the shelf, with empty space behind it. "
    "A few other products scattered around. Realistic restocking scene.",

    # Camera angle variations
    "This product ({name}) photographed from a low angle, looking slightly up at the shelf. "
    "Norwegian grocery store. The shelf edge is visible at the top of frame. "
    "Product label is readable from this angle. Price tag visible below.",

    "This product ({name}) seen from above, looking down at the shelf at about 45 degrees. "
    "Norwegian grocery store. Top of the product packaging visible along with the front label. "
    "Other products visible on the same shelf.",

    "A slightly tilted, candid-style photo of this product ({name}) on a Norwegian grocery shelf. "
    "As if taken quickly with a phone camera. Slight motion blur on edges but product is sharp. "
    "Natural, unposed look. Label readable.",

    # Distance variations
    "A close-up shot of this product ({name}) on a Norwegian grocery shelf. "
    "The product fills about 50% of the frame. Fine details of the label are visible. "
    "Surrounding products are slightly blurred. Shallow depth of field.",

    "A wide shot of a Norwegian grocery store shelf section featuring this product ({name}). "
    "The product takes up about 15% of the frame. Multiple shelf levels visible. "
    "The product is identifiable but surrounded by many other items. Price tags visible.",

    # Condition variations
    "This product ({name}) on a Norwegian grocery shelf, partially obscured by "
    "a customer's hand reaching for the product next to it. "
    "The product label is still mostly visible. Natural shopping moment.",

    "Two units of this product ({name}) side by side on a Norwegian grocery shelf. "
    "Both showing their front labels. Price tag below. "
    "Other competing products on either side.",

    "This product ({name}) at the very edge of a Norwegian grocery shelf, "
    "about to be the last one. Empty shelf space visible where more products used to be. "
    "Slightly lonely look. Label facing camera.",
]


def image_to_bytes(img, fmt="JPEG"):
    buf = io.BytesIO()
    if img.mode == "RGBA":
        img = img.convert("RGB")
    img.save(buf, format=fmt, quality=90)
    return buf.getvalue()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variations", type=int, default=3,
                        help="Number of varied images per category")
    parser.add_argument("--split", type=int, default=-1,
                        help="0=first half, 1=second half, -1=all")
    args = parser.parse_args()

    annotations_path = Path.home() / "trainingdata/train/annotations.json"
    images_dir = Path.home() / "trainingdata/train/images"
    product_images_dir = Path.home() / "trainingdata/NM_NGD_product_images"
    metadata_path = product_images_dir / "metadata.json"
    pass1_dir = Path.home() / "gemini_shelf_gen"
    output_dir = Path.home() / "gemini_shelf_gen_v2"
    progress_file = output_dir / "progress.json"
    output_dir.mkdir(exist_ok=True)

    # Load data
    print("Loading data...")
    ann = json.load(open(annotations_path))
    meta = json.load(open(metadata_path))
    cats_by_id = {c["id"]: c["name"] for c in ann["categories"]}
    cat_counts = Counter(a["category_id"] for a in ann["annotations"])
    img_lookup = {img["id"]: img for img in ann["images"]}

    # Build name -> EAN
    product_by_name = {}
    for p in meta["products"]:
        if p["has_images"]:
            product_by_name[p["product_name"].strip().upper()] = p["product_code"]

    cat_to_ean = {}
    for cat_id, cat_name in cats_by_id.items():
        if cat_name.strip().upper() in product_by_name:
            cat_to_ean[cat_id] = product_by_name[cat_name.strip().upper()]

    # Best crops
    best_crops = {}
    for a in ann["annotations"]:
        cat_id = a["category_id"]
        area = a["bbox"][2] * a["bbox"][3]
        if cat_id not in best_crops or area > best_crops[cat_id]["area"]:
            best_crops[cat_id] = {
                "annotation": a, "area": area,
                "image": img_lookup[a["image_id"]],
            }

    # Build queue: same categories as pass 1
    queue = []
    for cat_dir in sorted(pass1_dir.iterdir()):
        if not cat_dir.is_dir() or not cat_dir.name.startswith("cat_"):
            continue
        cat_id = int(cat_dir.name.split("_")[1])
        if cat_id not in cats_by_id:
            continue
        # Get pass 1 images as additional references
        pass1_images = sorted(cat_dir.glob("*.jpg"))[:2]
        queue.append({
            "cat_id": cat_id,
            "name": cats_by_id[cat_id],
            "ean": cat_to_ean.get(cat_id),
            "crop_info": best_crops.get(cat_id),
            "pass1_images": pass1_images,
        })

    # Sort weakest first
    queue.sort(key=lambda x: cat_counts.get(x["cat_id"], 0))

    if args.split == 0:
        queue = queue[:len(queue) // 2]
    elif args.split == 1:
        queue = queue[len(queue) // 2:]

    total_images = len(queue) * args.variations
    print(f"Pass 2: {len(queue)} categories x {args.variations} variations = {total_images} images")
    print(f"Estimated time: {total_images * 36 / 3600:.1f}h")

    # Load progress
    progress = {}
    if progress_file.exists():
        progress = json.load(open(progress_file))

    # Init Gemini
    print("Initializing Gemini...")
    client = genai.Client(vertexai=True, project="ai-nm26osl-1779", location="global")

    success = 0
    errors = 0

    for qi, item in enumerate(queue):
        cat_id = item["cat_id"]
        cat_key = str(cat_id)

        # Check progress
        done = sum(1 for v in progress.get(cat_key, {}).get("variants", {}).values()
                   if v.get("status") == "OK")
        if done >= args.variations:
            continue

        # Collect references: studio photos + shelf crop + pass 1 images
        refs = []
        if item["ean"]:
            ean_dir = product_images_dir / item["ean"]
            if ean_dir.is_dir():
                for fname in ["front.jpg", "main.jpg", "back.jpg"]:
                    fpath = ean_dir / fname
                    if fpath.exists():
                        img = Image.open(fpath)
                        img.thumbnail((512, 512))
                        refs.append(img)

        if item["crop_info"]:
            try:
                img_path = images_dir / item["crop_info"]["image"]["file_name"]
                bbox = item["crop_info"]["annotation"]["bbox"]
                x, y, w, h = bbox
                img = Image.open(img_path)
                crop = img.crop((max(0, x - w * 0.05), max(0, y - h * 0.05),
                                 min(img.width, x + w * 1.05), min(img.height, y + h * 1.05)))
                crop.thumbnail((512, 512))
                refs.append(crop)
            except Exception:
                pass

        # Add pass 1 images as reference
        for p1 in item["pass1_images"]:
            try:
                img = Image.open(p1)
                img.thumbnail((512, 512))
                refs.append(img)
            except Exception:
                pass

        if not refs:
            continue

        print(f"\n[{qi+1}/{len(queue)}] cat {cat_id}: {item['name']} ({len(refs)} refs)")

        if cat_key not in progress:
            progress[cat_key] = {"name": item["name"], "variants": {}}

        cat_dir = output_dir / f"cat_{cat_id:03d}"
        cat_dir.mkdir(exist_ok=True)

        for v in range(args.variations):
            v_key = f"v{v}"
            if progress[cat_key]["variants"].get(v_key, {}).get("status") == "OK":
                continue

            # Pick a varied prompt (cycle through them)
            prompt_idx = (cat_id * 7 + v * 3) % len(VARIED_PROMPTS)
            prompt = VARIED_PROMPTS[prompt_idx].format(name=item["name"])

            out_path = cat_dir / f"cat_{cat_id:03d}_v2_{v:02d}.jpg"
            print(f"  v2_{v} (prompt {prompt_idx})...", end=" ", flush=True)

            try:
                contents = []
                for ref in refs:
                    contents.append(types.Part.from_bytes(
                        data=image_to_bytes(ref), mime_type="image/jpeg"
                    ))
                contents.append(
                    f"Above are reference photos of '{item['name']}'. {prompt}"
                )

                response = client.models.generate_content(
                    model="gemini-3.1-flash-image-preview",
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_modalities=["TEXT", "IMAGE"],
                    ),
                )

                gen_img = None
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "inline_data") and part.inline_data and part.inline_data.data:
                        gen_img = Image.open(io.BytesIO(part.inline_data.data))

                if gen_img:
                    gen_img = gen_img.convert("RGB")
                    gen_img.save(out_path, quality=95)
                    print(f"OK ({gen_img.width}x{gen_img.height})")
                    progress[cat_key]["variants"][v_key] = {
                        "status": "OK", "path": str(out_path),
                        "prompt_idx": prompt_idx,
                    }
                    success += 1
                else:
                    print("NO IMAGE")
                    progress[cat_key]["variants"][v_key] = {"status": "NO_IMAGE"}
                    errors += 1

            except Exception as e:
                err = str(e)[:200]
                print(f"ERROR: {err}")
                progress[cat_key]["variants"][v_key] = {"status": "ERROR", "error": err}
                errors += 1
                if "429" in err or "quota" in err.lower():
                    time.sleep(60)

            time.sleep(3)

        # Save progress after each category
        with open(progress_file, "w") as f:
            json.dump(progress, f, indent=2)

    print(f"\n=== PASS 2 DONE ===")
    print(f"Generated: {success}, Errors: {errors}")


if __name__ == "__main__":
    main()
