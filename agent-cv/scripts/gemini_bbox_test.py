"""
Test: Ask Gemini 3.1 Flash to generate shelf images AND return
bounding box coordinates for the product.

Generates 10 images from 10 different weak categories.
Saves images + bbox JSON for QC with JC.
"""
import json
import time
import io
from pathlib import Path
from collections import Counter
from PIL import Image, ImageDraw

from google import genai
from google.genai import types


def image_to_bytes(img, fmt="JPEG"):
    buf = io.BytesIO()
    if img.mode == "RGBA":
        img = img.convert("RGB")
    img.save(buf, format=fmt, quality=90)
    return buf.getvalue()


def main():
    # Paths
    annotations_path = Path.home() / "trainingdata/train/annotations.json"
    images_dir = Path.home() / "trainingdata/train/images"
    product_images_dir = Path.home() / "trainingdata/NM_NGD_product_images"
    metadata_path = product_images_dir / "metadata.json"
    output_dir = Path.home() / "gemini_bbox_test"
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
        cn = cat_name.strip().upper()
        if cn in product_by_name:
            cat_to_ean[cat_id] = product_by_name[cn]

    # Find best crop per category
    best_crops = {}
    for a in ann["annotations"]:
        cat_id = a["category_id"]
        area = a["bbox"][2] * a["bbox"][3]
        if cat_id not in best_crops or area > best_crops[cat_id]["area"]:
            best_crops[cat_id] = {
                "annotation": a,
                "area": area,
                "image": img_lookup[a["image_id"]],
            }

    # Pick 10 weak categories with reference images
    test_cats = []
    for cat_id in range(355):
        count = cat_counts.get(cat_id, 0)
        if count <= 9 and (cat_id in cat_to_ean or cat_id in best_crops):
            test_cats.append(cat_id)
        if len(test_cats) >= 10:
            break

    print(f"Testing {len(test_cats)} categories: {test_cats}")

    # Init Gemini
    client = genai.Client(vertexai=True, project="ai-nm26osl-1779", location="global")

    results = []

    for i, cat_id in enumerate(test_cats):
        product_name = cats_by_id[cat_id]
        ean = cat_to_ean.get(cat_id)
        count = cat_counts.get(cat_id, 0)
        print(f"\n[{i+1}/10] cat {cat_id}: {product_name} ({count} annotations)")

        # Collect reference images
        refs = []
        if ean:
            ean_dir = product_images_dir / ean
            if ean_dir.is_dir():
                for fname in ["front.jpg", "main.jpg"]:
                    fpath = ean_dir / fname
                    if fpath.exists():
                        img = Image.open(fpath)
                        img.thumbnail((512, 512))
                        refs.append(img)

        if cat_id in best_crops:
            crop_info = best_crops[cat_id]
            img_path = images_dir / crop_info["image"]["file_name"]
            bbox = crop_info["annotation"]["bbox"]
            x, y, w, h = bbox
            try:
                img = Image.open(img_path)
                pad_w, pad_h = w * 0.05, h * 0.05
                crop = img.crop((
                    max(0, x - pad_w), max(0, y - pad_h),
                    min(img.width, x + w + pad_w), min(img.height, y + h + pad_h),
                ))
                crop.thumbnail((512, 512))
                refs.append(crop)
            except Exception:
                pass

        if not refs:
            print("  No reference images, skipping")
            continue

        print(f"  References: {len(refs)} images")

        # Build prompt asking for image + bounding box
        contents = []
        for ref in refs:
            contents.append(types.Part.from_bytes(
                data=image_to_bytes(ref), mime_type="image/jpeg"
            ))

        contents.append(
            f"Above are reference photos of the product '{product_name}'. "
            f"Generate a photorealistic image of this EXACT product on a Norwegian grocery store shelf. "
            f"The product should be clearly visible with its front label facing the camera. "
            f"Other products should be visible on the shelf nearby. "
            f"Natural supermarket lighting.\n\n"
            f"IMPORTANT: After generating the image, also provide the bounding box coordinates "
            f"of the product '{product_name}' in the generated image. "
            f"Format the coordinates as JSON: "
            f'{{\"bbox\": [x_min, y_min, x_max, y_max]}} '
            f"where coordinates are pixel values in the generated image. "
            f"The bounding box should tightly enclose ONLY the target product."
        )

        try:
            t0 = time.time()
            response = client.models.generate_content(
                model="gemini-3.1-flash-image-preview",
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                ),
            )
            elapsed = time.time() - t0

            # Extract image and text
            gen_img = None
            text_parts = []
            for part in response.candidates[0].content.parts:
                if hasattr(part, "inline_data") and part.inline_data and part.inline_data.data:
                    gen_img = Image.open(io.BytesIO(part.inline_data.data))
                if hasattr(part, "text") and part.text:
                    text_parts.append(part.text)

            text_response = " ".join(text_parts).strip()

            if gen_img:
                gen_img = gen_img.convert("RGB")
                img_path = output_dir / f"cat_{cat_id:03d}_shelf.jpg"
                gen_img.save(img_path, quality=95)
                print(f"  Image: {gen_img.width}x{gen_img.height} ({elapsed:.1f}s)")

                # Try to parse bbox from text
                bbox_data = None
                if text_response:
                    print(f"  Text response: {text_response[:200]}")
                    # Try to extract JSON
                    import re
                    json_match = re.search(r'\{[^}]*"bbox"[^}]*\}', text_response)
                    if json_match:
                        try:
                            bbox_data = json.loads(json_match.group())
                            print(f"  Parsed bbox: {bbox_data}")
                        except json.JSONDecodeError:
                            print(f"  Could not parse bbox JSON")
                    else:
                        # Try to find any list of 4 numbers
                        nums = re.findall(r'\[(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\]', text_response)
                        if nums:
                            bbox_data = {"bbox": [int(n) for n in nums[0]]}
                            print(f"  Extracted bbox: {bbox_data}")
                        else:
                            print(f"  No bbox found in response")
                else:
                    print(f"  No text response (image only)")

                # Draw bbox on image for QC
                if bbox_data and "bbox" in bbox_data:
                    qc_img = gen_img.copy()
                    draw = ImageDraw.Draw(qc_img)
                    bx = bbox_data["bbox"]
                    draw.rectangle(bx, outline="red", width=3)
                    draw.text((bx[0], bx[1] - 15), f"cat_{cat_id}: {product_name[:30]}", fill="red")
                    qc_path = output_dir / f"cat_{cat_id:03d}_QC.jpg"
                    qc_img.save(qc_path, quality=95)
                    print(f"  QC image saved: {qc_path}")

                result = {
                    "cat_id": cat_id,
                    "product_name": product_name,
                    "annotations": count,
                    "image_size": [gen_img.width, gen_img.height],
                    "bbox": bbox_data.get("bbox") if bbox_data else None,
                    "text_response": text_response[:500],
                    "elapsed": round(elapsed, 1),
                }
                results.append(result)
            else:
                print(f"  No image generated")
                results.append({"cat_id": cat_id, "error": "no_image"})

        except Exception as e:
            print(f"  ERROR: {str(e)[:200]}")
            results.append({"cat_id": cat_id, "error": str(e)[:200]})

        time.sleep(3)

    # Save results
    results_path = output_dir / "bbox_test_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n=== SUMMARY ===")
    print(f"Total: {len(results)}")
    has_img = sum(1 for r in results if "image_size" in r)
    has_bbox = sum(1 for r in results if r.get("bbox"))
    print(f"Images generated: {has_img}/10")
    print(f"Bboxes returned: {has_bbox}/10")
    print(f"Results saved: {results_path}")
    print(f"QC images in: {output_dir}")


if __name__ == "__main__":
    main()
