"""
Organize generated images into labeling batches of 100.

Downloads from GCP VM, creates batch folders with:
  batch_001/
    images/       <- 100 shelf images
    labels/       <- empty, JC fills these
    manifest.json <- {filename: {category_id, product_name}}

Weakest products first (seen_once before somewhat_known).
"""
import json
import shutil
from pathlib import Path
from collections import Counter


def main():
    # Paths
    gen_dir = Path.home() / "gemini_shelf_gen"
    ann_path = Path.home() / "trainingdata/train/annotations.json"
    output_dir = Path.home() / "label_batches"
    output_dir.mkdir(exist_ok=True)

    # Load category info
    ann = json.load(open(ann_path))
    cats_by_id = {c["id"]: c["name"] for c in ann["categories"]}
    cat_counts = Counter(a["category_id"] for a in ann["annotations"])

    # Collect all generated images
    all_images = []
    for cat_dir in sorted(gen_dir.iterdir()):
        if not cat_dir.is_dir() or not cat_dir.name.startswith("cat_"):
            continue
        cat_id = int(cat_dir.name.split("_")[1])
        count = cat_counts.get(cat_id, 0)
        for img_path in sorted(cat_dir.glob("*.jpg")):
            all_images.append({
                "path": img_path,
                "cat_id": cat_id,
                "name": cats_by_id.get(cat_id, f"product_{cat_id}"),
                "train_count": count,
            })

    # Sort: weakest first
    all_images.sort(key=lambda x: (x["train_count"], x["cat_id"]))

    print(f"Total generated images: {len(all_images)}")

    # Split into batches of 100
    batch_size = 100
    batch_num = 0

    for i in range(0, len(all_images), batch_size):
        batch_num += 1
        batch = all_images[i:i + batch_size]
        batch_dir = output_dir / f"batch_{batch_num:03d}"
        img_dir = batch_dir / "images"
        lbl_dir = batch_dir / "labels"
        img_dir.mkdir(parents=True, exist_ok=True)
        lbl_dir.mkdir(parents=True, exist_ok=True)

        manifest = {}
        for item in batch:
            fname = item["path"].name
            shutil.copy2(item["path"], img_dir / fname)
            manifest[fname] = {
                "category_id": item["cat_id"],
                "product_name": item["name"],
                "train_count": item["train_count"],
            }

        with open(batch_dir / "manifest.json", "w") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        # Summary for this batch
        cat_ids = set(item["cat_id"] for item in batch)
        min_count = min(item["train_count"] for item in batch)
        max_count = max(item["train_count"] for item in batch)
        print(f"  batch_{batch_num:03d}: {len(batch)} images, "
              f"{len(cat_ids)} categories, "
              f"train_count {min_count}-{max_count}")

    print(f"\nCreated {batch_num} batches in {output_dir}")
    print("Each batch has images/, labels/ (empty), manifest.json")


if __name__ == "__main__":
    main()
