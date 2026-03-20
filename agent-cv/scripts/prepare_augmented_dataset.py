#!/usr/bin/env python3
"""Prepare augmented YOLO dataset with proper train/val split.

Combines:
- 208 real images (train split from Phase 0)
- 140 existing synthetic images
- Val: 40 held-out real images (from Phase 0 split)

Creates a new dataset at ~/augmented_yolo/ with proper split.

Usage (on GCP cv-train-1):
    python3 prepare_augmented_dataset.py
"""

import json
import shutil
from pathlib import Path


# Paths on GCP
ORIGINAL_DATASET = Path("/home/jcfrugaard/cv-train/data/yolo_dataset")
SYNTHETIC_DATA = Path("/home/jcfrugaard/synthetic_data")
SPLIT_MANIFEST = ORIGINAL_DATASET / "split_manifest.json"
OUTPUT_DIR = Path("/home/jcfrugaard/augmented_yolo")


def main():
    # Load split manifest
    if not SPLIT_MANIFEST.exists():
        print("ERROR: Run create_val_split.py first")
        return 1

    manifest = json.loads(SPLIT_MANIFEST.read_text())
    train_stems = set(manifest["train_stems"])
    val_stems = set(manifest["val_stems"])
    print(f"Split: {len(train_stems)} train, {len(val_stems)} val")

    # Create output dirs
    out_train_img = OUTPUT_DIR / "images" / "train"
    out_train_lbl = OUTPUT_DIR / "labels" / "train"
    out_val_img = OUTPUT_DIR / "images" / "val"
    out_val_lbl = OUTPUT_DIR / "labels" / "val"

    for d in [out_train_img, out_train_lbl, out_val_img, out_val_lbl]:
        d.mkdir(parents=True, exist_ok=True)

    # Copy train images and labels (original 208)
    orig_images = ORIGINAL_DATASET / "images" / "train"
    orig_labels = ORIGINAL_DATASET / "labels" / "train"

    train_count = 0
    val_count = 0

    for img_path in sorted(orig_images.glob("*.jpg")):
        stem = img_path.stem
        label_path = orig_labels / f"{stem}.txt"

        if stem in train_stems:
            shutil.copy2(str(img_path), str(out_train_img / img_path.name))
            if label_path.exists():
                shutil.copy2(str(label_path), str(out_train_lbl / label_path.name))
            train_count += 1
        elif stem in val_stems:
            shutil.copy2(str(img_path), str(out_val_img / img_path.name))
            if label_path.exists():
                shutil.copy2(str(label_path), str(out_val_lbl / label_path.name))
            val_count += 1

    print(f"Original: {train_count} train, {val_count} val")

    # Add synthetic images to train only
    synth_count = 0
    synth_images = SYNTHETIC_DATA / "images"
    synth_labels = SYNTHETIC_DATA / "labels"

    synth_labels = SYNTHETIC_DATA / "labels"
    if synth_images.exists() and synth_labels.exists():
        for img_path in sorted(synth_images.glob("*.jpg")):
            stem = img_path.stem
            label_path = synth_labels / f"{stem}.txt"

            shutil.copy2(str(img_path), str(out_train_img / img_path.name))
            if label_path.exists():
                shutil.copy2(str(label_path), str(out_train_lbl / label_path.name))
            synth_count += 1
    elif synth_images.exists():
        # Convert COCO annotations to YOLO labels inline
        synth_ann = SYNTHETIC_DATA / "annotations.json"
        if synth_ann.exists():
            print("Converting synthetic COCO annotations to YOLO format...")
            with open(synth_ann) as f:
                coco = json.load(f)

            imgs = {img["id"]: img for img in coco["images"]}
            anns_by_img = {}
            for ann in coco["annotations"]:
                anns_by_img.setdefault(ann["image_id"], []).append(ann)

            for img_id, img_info in imgs.items():
                fname = img_info["file_name"]
                src = synth_images / fname
                if not src.exists():
                    continue

                w, h = img_info["width"], img_info["height"]
                shutil.copy2(str(src), str(out_train_img / fname))

                # Write YOLO label
                lines = []
                for ann in anns_by_img.get(img_id, []):
                    bx, by, bw, bh = ann["bbox"]
                    cx = max(0, min(1, (bx + bw / 2) / w))
                    cy = max(0, min(1, (by + bh / 2) / h))
                    nw = max(0, min(1, bw / w))
                    nh = max(0, min(1, bh / h))
                    lines.append(f"{ann['category_id']} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")

                label_file = out_train_lbl / (Path(fname).stem + ".txt")
                label_file.write_text("\n".join(lines) + "\n" if lines else "")
                synth_count += 1

    print(f"Synthetic: {synth_count} images added to train")

    # Count final totals
    final_train = len(list(out_train_img.glob("*.jpg")))
    final_val = len(list(out_val_img.glob("*.jpg")))
    print(f"\nFinal dataset: {final_train} train, {final_val} val")

    # Read original dataset.yaml for category names
    yaml_path = ORIGINAL_DATASET / "dataset.yaml"
    yaml_content = yaml_path.read_text()

    # Replace paths and val
    new_yaml = f"path: {OUTPUT_DIR}\ntrain: images/train\nval: images/val\n"
    # Append nc and names from original
    in_header = True
    for line in yaml_content.splitlines():
        if line.startswith("nc:") or line.startswith("names:"):
            in_header = False
        if not in_header:
            new_yaml += line + "\n"

    out_yaml = OUTPUT_DIR / "dataset.yaml"
    out_yaml.write_text(new_yaml)
    print(f"Wrote {out_yaml}")

    return 0


if __name__ == "__main__":
    exit(main())
