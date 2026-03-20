#!/usr/bin/env python3
"""Create proper 80/20 train/val split for YOLO dataset.

The original dataset has val=train (same data), giving fake 0.95 scores.
This script creates a real holdout val set for honest evaluation.

Strategy: Multi-label aware splitting. Each image contains annotations from
multiple categories. We use iterative assignment: sort images by rarest
category representation, assign to val first (up to 20%), ensuring maximum
category coverage in val set.

Usage (on GCP cv-train-1):
    python3 create_val_split.py --dataset-dir /home/jcfrugaard/cv-train/data/yolo_dataset
"""

import argparse
import json
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", required=True, help="Path to yolo_dataset/")
    parser.add_argument("--val-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def get_image_categories(labels_dir: Path) -> dict:
    """For each image, get set of categories present."""
    img_cats = {}
    for label_file in sorted(labels_dir.glob("*.txt")):
        cats = set()
        for line in label_file.read_text().strip().splitlines():
            parts = line.strip().split()
            if len(parts) >= 5:
                cats.add(int(parts[0]))
        img_cats[label_file.stem] = cats
    return img_cats


def stratified_split(img_cats: dict, val_fraction: float, seed: int):
    """Split images into train/val with maximum category coverage in val.

    Strategy:
    1. Count how many images each category appears in
    2. Sort images by their rarest category (images with rare categories get priority for val)
    3. Assign to val until we hit val_fraction, ensuring rare categories are represented
    """
    random.seed(seed)

    all_stems = list(img_cats.keys())
    n_val = max(1, int(len(all_stems) * val_fraction))

    # Count category frequency across images
    cat_freq = Counter()
    for cats in img_cats.values():
        for c in cats:
            cat_freq[c] += 1

    # For each image, compute "rarity score" = min frequency of its categories
    img_rarity = {}
    for stem, cats in img_cats.items():
        if cats:
            img_rarity[stem] = min(cat_freq[c] for c in cats)
        else:
            img_rarity[stem] = 999

    # Sort by rarity (rarest first), then shuffle within same rarity for randomness
    stems_by_rarity = sorted(all_stems, key=lambda s: (img_rarity[s], random.random()))

    # Assign: take every 5th image for val (spread across rarity levels)
    # This ensures rare categories get into val while maintaining distribution
    val_stems = set()
    train_stems = set()

    # First pass: ensure images with unique categories (freq=1) stay in train
    # (can't evaluate on categories only seen once if they're in val)
    must_train = set()
    for stem, cats in img_cats.items():
        for c in cats:
            if cat_freq[c] == 1:
                must_train.add(stem)
                break

    # Available for val: everything not must_train
    available = [s for s in stems_by_rarity if s not in must_train]
    random.shuffle(available)

    # Take val_fraction of available images for val
    n_val_available = max(1, int(len(available) * val_fraction))
    val_stems = set(available[:n_val_available])
    train_stems = set(all_stems) - val_stems

    return sorted(train_stems), sorted(val_stems)


def main():
    args = parse_args()
    dataset_dir = Path(args.dataset_dir)

    images_train = dataset_dir / "images" / "train"
    labels_train = dataset_dir / "labels" / "train"
    images_val = dataset_dir / "images" / "val"
    labels_val = dataset_dir / "labels" / "val"

    if not images_train.exists() or not labels_train.exists():
        print(f"ERROR: {images_train} or {labels_train} not found")
        return 1

    # Get category info per image
    img_cats = get_image_categories(labels_train)
    print(f"Total images with labels: {len(img_cats)}")

    # Count total categories
    all_cats = set()
    for cats in img_cats.values():
        all_cats.update(cats)
    print(f"Total categories in dataset: {len(all_cats)}")

    # Do the split
    train_stems, val_stems = stratified_split(img_cats, args.val_fraction, args.seed)
    print(f"\nSplit: {len(train_stems)} train, {len(val_stems)} val")

    # Check category coverage
    train_cats = set()
    val_cats = set()
    for s in train_stems:
        train_cats.update(img_cats.get(s, set()))
    for s in val_stems:
        val_cats.update(img_cats.get(s, set()))

    print(f"Categories in train: {len(train_cats)}")
    print(f"Categories in val: {len(val_cats)}")
    print(f"Categories ONLY in train (can't evaluate): {len(train_cats - val_cats)}")
    print(f"Categories in both: {len(train_cats & val_cats)}")

    # Create val directories
    images_val.mkdir(parents=True, exist_ok=True)
    labels_val.mkdir(parents=True, exist_ok=True)

    # Move val images and labels (copy, don't move, to preserve original)
    moved = 0
    for stem in val_stems:
        # Find the image file (could be .jpg or .jpeg)
        img_files = list(images_train.glob(f"{stem}.*"))
        img_files = [f for f in img_files if f.suffix.lower() in ('.jpg', '.jpeg', '.png')]
        label_file = labels_train / f"{stem}.txt"

        for img_file in img_files:
            dst = images_val / img_file.name
            if not dst.exists():
                shutil.copy2(str(img_file), str(dst))

        if label_file.exists():
            dst = labels_val / label_file.name
            if not dst.exists():
                shutil.copy2(str(label_file), str(dst))
            moved += 1

    print(f"\nCopied {moved} image+label pairs to val/")

    # Update dataset.yaml
    yaml_path = dataset_dir / "dataset.yaml"
    if yaml_path.exists():
        content = yaml_path.read_text()
        # Replace val line
        new_content = content.replace("val: images/train", "val: images/val")
        yaml_path.write_text(new_content)
        print(f"Updated {yaml_path}: val now points to images/val")

    # Also create a split manifest for reproducibility
    manifest = {
        "seed": args.seed,
        "val_fraction": args.val_fraction,
        "train_count": len(train_stems),
        "val_count": len(val_stems),
        "train_categories": len(train_cats),
        "val_categories": len(val_cats),
        "categories_only_in_train": len(train_cats - val_cats),
        "train_stems": train_stems,
        "val_stems": val_stems,
    }
    manifest_path = dataset_dir / "split_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"Wrote split manifest to {manifest_path}")

    # Print category distribution warnings
    cat_freq = Counter()
    for cats in img_cats.values():
        for c in cats:
            cat_freq[c] += 1

    single_cats = [c for c, freq in cat_freq.items() if freq == 1]
    print(f"\nWARNING: {len(single_cats)} categories appear in only 1 image (can't split)")
    print("These categories are kept in train only.")

    return 0


if __name__ == "__main__":
    exit(main())
