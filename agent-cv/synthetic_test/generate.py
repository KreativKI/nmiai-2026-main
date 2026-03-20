"""
Extract best shelf crops for 5 target categories and test Gemini image generation.
"""
import json
import os
import sys
import time
import traceback
from pathlib import Path
from PIL import Image
import io

# Paths
ANNOTATIONS_PATH = "/Volumes/devdrive/github_dev/nmiai-2026-main/trainingdata/train/annotations.json"
IMAGES_DIR = "/Volumes/devdrive/github_dev/nmiai-2026-main/trainingdata/train/images"
OUTPUT_DIR = "/Volumes/devdrive/github_dev/nmiai-worktree-nlp/agent-cv/synthetic_test"

# Target categories (by annotation count)
TARGET_CATS = {
    12: "Leksands Rutbit",
    30: "SJOKORINGER 375G ELDORADO",
    341: "EVERGOOD CLASSIC HELE BØNNER 500G",
    141: "EVERGOOD CLASSIC PRESSMALT 250G",
    215: "BLUE FRUIT TE PYRAMIDE 20POS LIPTON",
}

def load_annotations():
    print("Loading annotations...")
    with open(ANNOTATIONS_PATH, "r") as f:
        coco = json.load(f)
    print(f"  {len(coco['annotations'])} annotations, {len(coco['images'])} images, {len(coco['categories'])} categories")
    return coco

def find_best_crops(coco):
    """Find the largest annotation (by area) for each target category."""
    # Build image lookup
    img_lookup = {img["id"]: img for img in coco["images"]}

    best = {}  # cat_id -> best annotation
    for ann in coco["annotations"]:
        cat_id = ann["category_id"]
        if cat_id not in TARGET_CATS:
            continue
        area = ann["bbox"][2] * ann["bbox"][3]  # w * h
        if cat_id not in best or area > best[cat_id]["area"]:
            best[cat_id] = {
                "annotation": ann,
                "area": area,
                "image": img_lookup[ann["image_id"]],
            }

    print(f"\nFound best crops for {len(best)} categories:")
    for cat_id, info in best.items():
        bbox = info["annotation"]["bbox"]
        print(f"  cat {cat_id}: {TARGET_CATS[cat_id]} - bbox {bbox[2]:.0f}x{bbox[3]:.0f} in {info['image']['file_name']}")

    return best

def extract_crops(best):
    """Extract and save crops from training images."""
    crop_paths = {}
    for cat_id, info in best.items():
        img_path = os.path.join(IMAGES_DIR, info["image"]["file_name"])
        bbox = info["annotation"]["bbox"]  # [x, y, w, h]
        x, y, w, h = bbox

        img = Image.open(img_path)
        # Add small padding (5%) for context
        pad_w = w * 0.05
        pad_h = h * 0.05
        crop_box = (
            max(0, x - pad_w),
            max(0, y - pad_h),
            min(img.width, x + w + pad_w),
            min(img.height, y + h + pad_h),
        )
        crop = img.crop(crop_box)

        out_path = os.path.join(OUTPUT_DIR, f"cat_{cat_id:03d}_crop.jpg")
        crop.save(out_path, quality=95)
        crop_paths[cat_id] = out_path
        print(f"  Saved crop: {out_path} ({crop.width}x{crop.height})")

    return crop_paths

def generate_with_gemini(crop_paths):
    """Send crops to Gemini and generate clean product photos."""
    from google import genai
    from google.genai import types

    client = genai.Client(vertexai=True, project='ai-nm26osl-1779', location='global')

    results = {}

    for cat_id, crop_path in crop_paths.items():
        product_name = TARGET_CATS[cat_id]
        print(f"\n--- Generating for cat {cat_id}: {product_name} ---")

        with open(crop_path, "rb") as f:
            image_bytes = f.read()

        # Variation 1: Clean product photo
        prompt_v1 = (
            f"This is a photo of a grocery product on a store shelf. "
            f"Generate a clean product photo of this exact same product on a plain white background, "
            f"showing the front label clearly. The product is {product_name}."
        )

        # Variation 2: Different angle
        prompt_v2 = (
            f"Generate this same grocery product ({product_name}) "
            f"photographed from a slightly different angle on a plain white background."
        )

        for variant, prompt in [("v1", prompt_v1), ("v2", prompt_v2)]:
            out_path = os.path.join(OUTPUT_DIR, f"cat_{cat_id:03d}_gemini_{variant}.png")
            print(f"  Generating {variant}...")

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

                # Check for image in response
                saved = False
                text_response = ""
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "inline_data") and part.inline_data and part.inline_data.data:
                        img = Image.open(io.BytesIO(part.inline_data.data))
                        img.save(out_path)
                        print(f"  Saved: {out_path} ({img.width}x{img.height})")
                        saved = True
                        results.setdefault(cat_id, {})[variant] = {
                            "path": out_path,
                            "size": f"{img.width}x{img.height}",
                            "status": "OK",
                        }
                    elif hasattr(part, "text") and part.text:
                        text_response += part.text

                if not saved:
                    print(f"  WARNING: No image in response. Text: {text_response[:200]}")
                    results.setdefault(cat_id, {})[variant] = {
                        "status": "NO_IMAGE",
                        "text": text_response[:500],
                    }

            except Exception as e:
                print(f"  ERROR: {e}")
                traceback.print_exc()
                results.setdefault(cat_id, {})[variant] = {
                    "status": "ERROR",
                    "error": str(e),
                }

            # Rate limiting
            time.sleep(2)

    return results

def write_report(results, crop_paths):
    """Write quality report."""
    report_path = os.path.join(OUTPUT_DIR, "QUALITY_REPORT.md")

    lines = [
        "# Gemini Synthetic Product Photo Quality Report",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M')}",
        f"Model: gemini-3.1-flash-image-preview",
        "",
        "## Results Per Category",
        "",
    ]

    success_count = 0
    total_count = 0

    for cat_id in sorted(TARGET_CATS.keys()):
        product_name = TARGET_CATS[cat_id]
        lines.append(f"### Cat {cat_id}: {product_name}")
        lines.append("")

        cat_results = results.get(cat_id, {})

        for variant in ["v1", "v2"]:
            total_count += 1
            vr = cat_results.get(variant, {"status": "NOT_RUN"})
            status = vr.get("status", "UNKNOWN")

            if status == "OK":
                success_count += 1
                lines.append(f"- **{variant}**: Generated successfully ({vr['size']})")
            elif status == "NO_IMAGE":
                lines.append(f"- **{variant}**: No image returned. Text: {vr.get('text', 'N/A')[:200]}")
            elif status == "ERROR":
                lines.append(f"- **{variant}**: Error: {vr.get('error', 'unknown')[:200]}")
            else:
                lines.append(f"- **{variant}**: {status}")

        lines.append("")

    lines.extend([
        "## Summary",
        "",
        f"- Images generated: {success_count}/{total_count}",
        f"- Success rate: {success_count/total_count*100:.0f}%" if total_count > 0 else "- No attempts",
        "",
        "## Visual Quality Assessment",
        "",
        "(Review the generated images manually by comparing cat_XXX_crop.jpg with cat_XXX_gemini_v1.png and v2.png)",
        "",
        "## Verdict",
        "",
    ])

    if success_count == 0:
        lines.append("**USELESS** - Gemini could not generate any product images. Image generation may not be supported for this model/configuration.")
    elif success_count < total_count * 0.5:
        lines.append("**MARGINAL** - Some images generated but inconsistent. May need different prompting strategy.")
    else:
        lines.append("**Pending manual review** - Images generated successfully. Review visual quality to determine USEFUL vs MARGINAL.")

    lines.append("")

    with open(report_path, "w") as f:
        f.write("\n".join(lines))

    print(f"\nReport saved to {report_path}")

def main():
    coco = load_annotations()
    best = find_best_crops(coco)
    crop_paths = extract_crops(best)

    print("\n=== Generating with Gemini ===")
    results = generate_with_gemini(crop_paths)

    write_report(results, crop_paths)

    # Print summary
    print("\n=== SUMMARY ===")
    for cat_id in sorted(TARGET_CATS.keys()):
        cat_results = results.get(cat_id, {})
        statuses = [cat_results.get(v, {}).get("status", "N/A") for v in ["v1", "v2"]]
        print(f"  cat {cat_id:3d}: v1={statuses[0]}, v2={statuses[1]}")

if __name__ == "__main__":
    main()
