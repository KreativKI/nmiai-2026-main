#!/usr/bin/env python3
"""
Generate manifest.json from image filenames in synthetic_shelf/images/.

Expected filename format (adapt the parsing below to your actual naming):
  Option A: category_id_productname_NNN.jpg  (e.g., 42_melk_001.jpg)
  Option B: productname_category_id.jpg       (e.g., melk_42.jpg)

If filenames don't match either pattern, edit the parse_filename() function.
You can also provide a CSV mapping file as argument:
  python3 generate_manifest.py mapping.csv

CSV format: filename,category_id,product_name
"""

import json
import sys
import csv
from pathlib import Path

IMAGES_DIR = Path(__file__).resolve().parent.parent.parent / "synthetic_shelf" / "images"
MANIFEST_PATH = Path(__file__).resolve().parent.parent.parent / "synthetic_shelf" / "manifest.json"


def parse_filename(filename):
    """Try to extract category_id and product_name from filename.
    Adapt this to your actual naming convention."""
    stem = Path(filename).stem

    # Pattern: categoryid_productname_NNN
    parts = stem.split("_")
    if len(parts) >= 2 and parts[0].isdigit():
        cat_id = int(parts[0])
        name = " ".join(parts[1:-1]) if len(parts) > 2 else parts[1]
        return cat_id, name

    # Pattern: productname_categoryid
    if len(parts) >= 2 and parts[-1].isdigit():
        cat_id = int(parts[-1])
        name = " ".join(parts[:-1])
        return cat_id, name

    return None, stem


def from_csv(csv_path):
    manifest = {}
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            manifest[row["filename"]] = {
                "category_id": int(row["category_id"]),
                "product_name": row["product_name"],
            }
    return manifest


def from_filenames():
    manifest = {}
    extensions = {".jpg", ".jpeg", ".png", ".webp"}
    for img in sorted(IMAGES_DIR.iterdir()):
        if img.suffix.lower() in extensions:
            cat_id, name = parse_filename(img.name)
            if cat_id is not None:
                manifest[img.name] = {
                    "category_id": cat_id,
                    "product_name": name,
                }
            else:
                print(f"WARNING: Could not parse category from: {img.name}")
                manifest[img.name] = {
                    "category_id": 0,
                    "product_name": name,
                }
    return manifest


def main():
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
        print(f"Generating manifest from CSV: {csv_path}")
        manifest = from_csv(csv_path)
    else:
        print(f"Generating manifest from filenames in: {IMAGES_DIR}")
        manifest = from_filenames()

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(manifest)} entries to {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
