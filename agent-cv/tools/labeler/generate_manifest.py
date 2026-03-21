#!/usr/bin/env python3
"""
Generate manifest.json from image filenames or a CSV mapping.

Usage:
  python3 generate_manifest.py                    # Parse from filenames
  python3 generate_manifest.py mapping.csv        # From CSV (filename,category_id,product_name)

Filename patterns supported:
  categoryid_productname_NNN.jpg   (e.g., 42_melk_001.jpg)
  productname_categoryid.jpg       (e.g., melk_42.jpg)

Edit parse_filename() for other naming conventions.
"""

import csv
import json
import sys
from pathlib import Path

SYNTHETIC = Path(__file__).resolve().parent.parent.parent / "synthetic_shelf"
IMAGES_DIR = SYNTHETIC / "images"
MANIFEST_PATH = SYNTHETIC / "manifest.json"

EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def parse_filename(filename):
    stem = Path(filename).stem
    parts = stem.split("_")

    if len(parts) >= 2 and parts[0].isdigit():
        cat_id = int(parts[0])
        name = " ".join(parts[1:-1]) if len(parts) > 2 else parts[1]
        return cat_id, name

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
    for img in sorted(IMAGES_DIR.iterdir()):
        if img.suffix.lower() in EXTENSIONS:
            cat_id, name = parse_filename(img.name)
            if cat_id is not None:
                manifest[img.name] = {"category_id": cat_id, "product_name": name}
            else:
                print(f"SKIPPED (no category parsed): {img.name}")
    return manifest


def main():
    if len(sys.argv) > 1:
        print(f"Reading CSV: {sys.argv[1]}")
        manifest = from_csv(sys.argv[1])
    else:
        print(f"Parsing filenames in: {IMAGES_DIR}")
        manifest = from_filenames()

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(manifest)} entries to {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
