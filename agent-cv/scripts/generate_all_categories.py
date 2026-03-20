"""
Generate Gemini synthetic product photos for ALL 357 categories.
Expands beyond the 34 shelf-crop-only categories to cover everything.

Uses shelf crops as input (largest annotation per category).
Generates 2 variants per category: front clean + angle variation.
Skips categories that already have Gemini photos in synthetic_test/.

Uses Vertex AI (project ai-nm26osl-1779, gemini-3.1-flash-image-preview).
"""
import json
import time
import traceback
from pathlib import Path
from PIL import Image
import io

ANNOTATIONS_PATH = "/Volumes/devdrive/github_dev/nmiai-2026-main/trainingdata/train/annotations.json"
IMAGES_DIR = Path("/Volumes/devdrive/github_dev/nmiai-2026-main/trainingdata/train/images")
OUTPUT_DIR = Path("/Volumes/devdrive/github_dev/nmiai-worktree-cv/agent-cv/synthetic_all")
PROGRESS_FILE = OUTPUT_DIR / "progress.json"
EXCLUDE_CATEGORIES = {355}  # unknown_product


def load_progress():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {}


def save_progress(progress):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading annotations...")
    with open(ANNOTATIONS_PATH) as f:
        coco = json.load(f)

    cat_by_id = {c["id"]: c["name"] for c in coco["categories"]}
    img_lookup = {img["id"]: img for img in coco["images"]}

    # Find largest crop per category
    best_crops = {}
    for ann in coco["annotations"]:
        cat_id = ann["category_id"]
        if cat_id in EXCLUDE_CATEGORIES:
            continue
        area = ann["bbox"][2] * ann["bbox"][3]
        if cat_id not in best_crops or area > best_crops[cat_id]["area"]:
            best_crops[cat_id] = {
                "annotation": ann,
                "area": area,
                "image": img_lookup[ann["image_id"]],
            }

    print(f"Found crops for {len(best_crops)} categories (excluding {len(EXCLUDE_CATEGORIES)} excluded)")

    # Check what's already done
    progress = load_progress()
    existing = {int(k) for k, v in progress.items()
                if v.get("v1", {}).get("status") == "OK" and v.get("v2", {}).get("status") == "OK"}

    # Also check synthetic_test/ for previously generated images
    synth_test = Path("/Volumes/devdrive/github_dev/nmiai-worktree-cv/agent-cv/synthetic_test")
    if synth_test.exists():
        for f in synth_test.glob("cat_*_gemini_v1.png"):
            cat_str = f.stem.replace("cat_", "").replace("_gemini_v1", "")
            try:
                cat_id = int(cat_str)
                v2 = synth_test / f"cat_{cat_str}_gemini_v2.png"
                if v2.exists():
                    existing.add(cat_id)
            except ValueError:
                pass

    todo = sorted(set(best_crops.keys()) - existing)
    print(f"Already done: {len(existing)}, remaining: {len(todo)}")
    print(f"Estimated time: {len(todo) * 2 * 5 / 60:.0f} minutes")

    if not todo:
        print("Nothing to generate!")
        return

    # Init Gemini
    from google import genai
    from google.genai import types
    client = genai.Client(vertexai=True, project='ai-nm26osl-1779', location='global')

    success = 0
    errors = 0

    for i, cat_id in enumerate(todo):
        info = best_crops[cat_id]
        product_name = cat_by_id.get(cat_id, f"product_{cat_id}")
        print(f"\n[{i+1}/{len(todo)}] cat {cat_id}: {product_name}")

        # Extract crop
        img_path = IMAGES_DIR / info["image"]["file_name"]
        bbox = info["annotation"]["bbox"]
        x, y, w, h = bbox

        try:
            img = Image.open(img_path)
        except Exception as e:
            print(f"  Failed to open image: {e}")
            errors += 1
            continue

        pad_w, pad_h = w * 0.05, h * 0.05
        crop = img.crop((
            max(0, x - pad_w), max(0, y - pad_h),
            min(img.width, x + w + pad_w), min(img.height, y + h + pad_h),
        ))

        # Save crop
        crop_path = OUTPUT_DIR / f"cat_{cat_id:03d}_crop.jpg"
        crop.save(crop_path, quality=95)

        # Convert to bytes
        buf = io.BytesIO()
        crop.save(buf, format="JPEG", quality=95)
        image_bytes = buf.getvalue()

        prompts = {
            "v1": (
                f"This is a photo of a grocery product on a store shelf. "
                f"Generate a clean product photo of this exact same product on a plain white background, "
                f"showing the front label clearly. The product is {product_name}."
            ),
            "v2": (
                f"Generate this same grocery product ({product_name}) "
                f"photographed from a slightly different angle on a plain white background."
            ),
        }

        cat_results = {}
        for variant, prompt in prompts.items():
            out_path = OUTPUT_DIR / f"cat_{cat_id:03d}_gemini_{variant}.png"
            print(f"  {variant}...", end=" ", flush=True)

            try:
                contents = [
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                    prompt,
                ]
                response = client.models.generate_content(
                    model="gemini-3.1-flash-image-preview",
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_modalities=["TEXT", "IMAGE"],
                    ),
                )

                saved = False
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "inline_data") and part.inline_data and part.inline_data.data:
                        gen_img = Image.open(io.BytesIO(part.inline_data.data))
                        gen_img.save(out_path)
                        print(f"OK ({gen_img.width}x{gen_img.height})")
                        saved = True
                        cat_results[variant] = {"status": "OK", "size": f"{gen_img.width}x{gen_img.height}"}
                        success += 1

                if not saved:
                    print("NO IMAGE")
                    cat_results[variant] = {"status": "NO_IMAGE"}
                    errors += 1

            except Exception as e:
                print(f"ERROR: {e}")
                cat_results[variant] = {"status": "ERROR", "error": str(e)}
                errors += 1

            time.sleep(3)

        progress[str(cat_id)] = cat_results
        save_progress(progress)

    print(f"\n=== DONE ===")
    print(f"Generated: {success}, Errors: {errors}")
    print(f"Total categories with Gemini photos: {len(existing) + len([c for c in todo if str(c) in progress and progress[str(c)].get('v1', {}).get('status') == 'OK'])}")


if __name__ == "__main__":
    main()
