#!/usr/bin/env python3
"""Prepare maximum-data YOLO dataset: all real + all synthetic data.

Combines:
- 208 real images (train split)
- 140 synthetic v1 (copy-paste, already in augmented_yolo)
- 175 synthetic v2 (copy-paste, in synthetic_data_v2)
- Gemini-generated images (converted to YOLO pseudo-labels)
- Val: 40 held-out real images

Usage (on GCP cv-train-1, after Gemini generation finishes):
    source ~/cv-train/venv/bin/activate
    python3 prepare_maxdata_dataset.py
"""

import json
import shutil
from pathlib import Path


AUGMENTED_YOLO = Path("/home/jcfrugaard/augmented_yolo")
SYNTH_V2 = Path("/home/jcfrugaard/synthetic_data_v2")
GEMINI_DIR = Path("/home/jcfrugaard/synthetic_all")
COCO_ANNOTATIONS = Path("/home/jcfrugaard/trainingdata/train/annotations.json")
OUTPUT_DIR = Path("/home/jcfrugaard/maxdata_yolo")


def main():
    # Start from augmented_yolo (already has 208 real + 140 synth v1 + 40 val)
    out_train_img = OUTPUT_DIR / "images" / "train"
    out_train_lbl = OUTPUT_DIR / "labels" / "train"
    out_val_img = OUTPUT_DIR / "images" / "val"
    out_val_lbl = OUTPUT_DIR / "labels" / "val"

    for d in [out_train_img, out_train_lbl, out_val_img, out_val_lbl]:
        d.mkdir(parents=True, exist_ok=True)

    # Copy everything from augmented_yolo
    print("Copying augmented_yolo base dataset...")
    for src_dir, dst_dir in [
        (AUGMENTED_YOLO / "images" / "train", out_train_img),
        (AUGMENTED_YOLO / "labels" / "train", out_train_lbl),
        (AUGMENTED_YOLO / "images" / "val", out_val_img),
        (AUGMENTED_YOLO / "labels" / "val", out_val_lbl),
    ]:
        if src_dir.exists():
            for f in src_dir.iterdir():
                dst = dst_dir / f.name
                if not dst.exists():
                    shutil.copy2(str(f), str(dst))

    base_train = len(list(out_train_img.glob("*")))
    base_val = len(list(out_val_img.glob("*")))
    print(f"Base: {base_train} train, {base_val} val")

    # Add synthetic v2
    added_v2 = 0
    if SYNTH_V2.exists():
        for img in sorted((SYNTH_V2 / "images").glob("*.jpg")):
            dst = out_train_img / img.name
            if not dst.exists():
                shutil.copy2(str(img), str(dst))
                lbl = SYNTH_V2 / "labels" / (img.stem + ".txt")
                if lbl.exists():
                    shutil.copy2(str(lbl), str(out_train_lbl / lbl.name))
                added_v2 += 1
    print(f"Added synthetic v2: {added_v2}")

    # Add Gemini images as single-product training images
    # Each Gemini image is one product on white background
    # Create YOLO label: full-image bbox with the category ID
    added_gemini = 0
    if GEMINI_DIR.exists():
        # Load COCO annotations to get category names
        with open(COCO_ANNOTATIONS) as f:
            coco = json.load(f)
        cat_by_id = {c["id"]: c["name"] for c in coco["categories"]}

        for png_path in sorted(GEMINI_DIR.glob("cat_*_gemini_*.png")):
            # Parse category ID from filename: cat_XXX_gemini_v1.png
            parts = png_path.stem.split("_")
            try:
                cat_id = int(parts[1])
            except (IndexError, ValueError):
                continue

            if cat_id not in cat_by_id:
                continue

            # Convert PNG to JPG for YOLO
            import cv2
            img = cv2.imread(str(png_path))
            if img is None:
                continue

            h, w = img.shape[:2]
            if h < 50 or w < 50:
                continue

            out_name = f"gemini_{cat_id:03d}_{parts[-1]}.jpg"
            dst = out_train_img / out_name
            if dst.exists():
                continue

            cv2.imwrite(str(dst), img, [cv2.IMWRITE_JPEG_QUALITY, 90])

            # YOLO label: full image is the product (with some padding)
            # Use 80% of image as bbox (product centered, white border)
            cx, cy = 0.5, 0.5
            bw, bh = 0.8, 0.8
            label_path = out_train_lbl / f"gemini_{cat_id:03d}_{parts[-1]}.txt"
            label_path.write_text(f"{cat_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
            added_gemini += 1

    print(f"Added Gemini: {added_gemini}")

    final_train = len(list(out_train_img.glob("*")))
    final_val = len(list(out_val_img.glob("*")))
    print(f"\nFinal dataset: {final_train} train, {final_val} val")

    # Write dataset.yaml
    yaml_src = AUGMENTED_YOLO / "dataset.yaml"
    yaml_content = yaml_src.read_text()
    new_yaml = yaml_content.replace(str(AUGMENTED_YOLO), str(OUTPUT_DIR))
    (OUTPUT_DIR / "dataset.yaml").write_text(new_yaml)
    print(f"Wrote {OUTPUT_DIR / 'dataset.yaml'}")

    return 0


if __name__ == "__main__":
    exit(main())
