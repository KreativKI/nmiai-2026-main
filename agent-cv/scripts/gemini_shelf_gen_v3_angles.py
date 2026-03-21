"""
Gemini shelf generation PASS 3: Product orientation/angle variations.

JC noticed all pass 1 images show front-facing products. Real shelves have
products turned sideways, at angles, showing corners, partially rotated.

This pass specifically targets non-frontal product orientations.
3 variations per category, focusing on weakest products first.
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


ANGLE_PROMPTS = [
    # Product orientation variations
    "Generate a photorealistic image of this product ({name}) on a Norwegian grocery store shelf, "
    "but the product is TURNED SLIGHTLY TO THE SIDE, showing about 30 degrees of the side panel. "
    "Not perfectly front-facing. As if a customer picked it up and put it back slightly rotated. "
    "Label still partially visible. Natural supermarket lighting.",

    "This product ({name}) on a Norwegian grocery store shelf, placed at an angle. "
    "The product is showing its CORNER, where the front meets the side. About 45 degree angle. "
    "You can see parts of both the front label and the side of the packaging. "
    "Other products around it are front-facing.",

    "A Norwegian grocery shelf where this product ({name}) has been placed SIDEWAYS, "
    "showing primarily the SIDE of the packaging rather than the front. "
    "The product brand/name is still somewhat visible on the side text. "
    "It looks like a customer placed it back carelessly. Other products face forward normally.",

    "This product ({name}) on a Norwegian grocery shelf, LEANING against the product next to it "
    "at about a 15 degree tilt. Not standing perfectly upright. "
    "Front label is visible but at a slight angle. Realistic messy shelf look.",

    "Two of this product ({name}) on a Norwegian grocery shelf. "
    "One faces FORWARD, the other is turned showing its BACK panel. "
    "Both are the same product but from different angles. Natural lighting.",

    "This product ({name}) on a Norwegian grocery shelf, photographed from the SIDE. "
    "The camera is positioned to the left of the product, so you see mostly the left side panel "
    "with the front label visible at an angle. Depth perspective visible.",
]


def image_to_bytes(img, fmt="JPEG"):
    buf = io.BytesIO()
    if img.mode == "RGBA":
        img = img.convert("RGB")
    img.save(buf, format=fmt, quality=90)
    return buf.getvalue()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variations", type=int, default=2)
    parser.add_argument("--max-categories", type=int, default=55,
                        help="Limit number of categories")
    args = parser.parse_args()

    annotations_path = Path.home() / "trainingdata/train/annotations.json"
    images_dir = Path.home() / "trainingdata/train/images"
    product_images_dir = Path.home() / "trainingdata/NM_NGD_product_images"
    metadata_path = product_images_dir / "metadata.json"
    pass1_dir = Path.home() / "gemini_shelf_gen"
    output_dir = Path.home() / "gemini_shelf_gen_v3"
    progress_file = output_dir / "progress.json"
    output_dir.mkdir(exist_ok=True)

    print("Loading data...")
    ann = json.load(open(annotations_path))
    meta = json.load(open(metadata_path))
    cats_by_id = {c["id"]: c["name"] for c in ann["categories"]}
    cat_counts = Counter(a["category_id"] for a in ann["annotations"])
    img_lookup = {img["id"]: img for img in ann["images"]}

    product_by_name = {}
    for p in meta["products"]:
        if p["has_images"]:
            product_by_name[p["product_name"].strip().upper()] = p["product_code"]

    cat_to_ean = {}
    for cat_id, cat_name in cats_by_id.items():
        if cat_name.strip().upper() in product_by_name:
            cat_to_ean[cat_id] = product_by_name[cat_name.strip().upper()]

    best_crops = {}
    for a in ann["annotations"]:
        cat_id = a["category_id"]
        area = a["bbox"][2] * a["bbox"][3]
        if cat_id not in best_crops or area > best_crops[cat_id]["area"]:
            best_crops[cat_id] = {
                "annotation": a, "area": area,
                "image": img_lookup[a["image_id"]],
            }

    # Use pass 1 categories, weakest first
    queue = []
    for cat_dir in sorted(pass1_dir.iterdir()):
        if not cat_dir.is_dir() or not cat_dir.name.startswith("cat_"):
            continue
        cat_id = int(cat_dir.name.split("_")[1])
        if cat_id not in cats_by_id:
            continue
        pass1_imgs = sorted(cat_dir.glob("*.jpg"))[:1]
        queue.append({
            "cat_id": cat_id,
            "name": cats_by_id[cat_id],
            "ean": cat_to_ean.get(cat_id),
            "crop_info": best_crops.get(cat_id),
            "pass1_images": pass1_imgs,
        })

    queue.sort(key=lambda x: cat_counts.get(x["cat_id"], 0))
    queue = queue[:args.max_categories]

    total = len(queue) * args.variations
    print(f"Pass 3 (angles): {len(queue)} categories x {args.variations} = {total} images")
    print(f"Estimated: {total * 36 / 3600:.1f}h")

    progress = {}
    if progress_file.exists():
        progress = json.load(open(progress_file))

    print("Initializing Gemini...")
    client = genai.Client(vertexai=True, project="ai-nm26osl-1779", location="global")

    success = 0
    errors = 0

    for qi, item in enumerate(queue):
        cat_id = item["cat_id"]
        cat_key = str(cat_id)

        done = sum(1 for v in progress.get(cat_key, {}).get("variants", {}).values()
                   if v.get("status") == "OK")
        if done >= args.variations:
            continue

        # Collect references - importantly include SIDE and BACK views
        refs = []
        if item["ean"]:
            ean_dir = product_images_dir / item["ean"]
            if ean_dir.is_dir():
                # Include ALL angles for this pass
                for fname in ["front.jpg", "main.jpg", "back.jpg", "left.jpg", "right.jpg"]:
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

            prompt_idx = (cat_id * 3 + v * 2) % len(ANGLE_PROMPTS)
            prompt = ANGLE_PROMPTS[prompt_idx].format(name=item["name"])

            out_path = cat_dir / f"cat_{cat_id:03d}_angle_v{v:02d}.jpg"
            print(f"  angle_v{v} (prompt {prompt_idx})...", end=" ", flush=True)

            try:
                contents = []
                for ref in refs:
                    contents.append(types.Part.from_bytes(
                        data=image_to_bytes(ref), mime_type="image/jpeg"
                    ))
                contents.append(
                    f"Above are reference photos of '{item['name']}' from multiple angles "
                    f"(front, back, sides). {prompt}"
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

        with open(progress_file, "w") as f:
            json.dump(progress, f, indent=2)

    print(f"\n=== PASS 3 (ANGLES) DONE ===")
    print(f"Generated: {success}, Errors: {errors}")


if __name__ == "__main__":
    main()
