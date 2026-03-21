"""
Retrain YOLO11m on real images + JC-labeled Gemini shelf images.

One-click pipeline:
1. Merge real training data (COCO) + Gemini labeled data (YOLO format)
2. Build unified YOLO dataset with proper train/val split
3. Launch training on GCP with aggressive augmentation

Usage:
  python retrain_with_gemini.py \
    --real-annotations ~/trainingdata/train/annotations.json \
    --real-images ~/trainingdata/train/images \
    --gemini-images ~/gemini_shelf_gen \
    --gemini-labels ~/gemini_labels \
    --output ~/retrain_gemini \
    --epochs 200
"""
import argparse
import json
import random
import shutil
from pathlib import Path
from collections import Counter, defaultdict


def coco_to_yolo(bbox, img_w, img_h):
    """COCO [x,y,w,h] -> YOLO [cx,cy,w,h] normalized."""
    x, y, w, h = bbox
    cx = (x + w / 2) / img_w
    cy = (y + h / 2) / img_h
    nw = w / img_w
    nh = h / img_h
    return cx, cy, nw, nh


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--real-annotations", type=str, required=True)
    parser.add_argument("--real-images", type=str, required=True)
    parser.add_argument("--gemini-images", type=str, required=True,
                        help="Dir with cat_XXX/ subdirs containing shelf images")
    parser.add_argument("--gemini-labels", type=str, required=True,
                        help="Dir with YOLO .txt label files from JC + auto-label")
    parser.add_argument("--output", type=str, required=True)
    parser.add_argument("--val-ratio", type=float, default=0.15,
                        help="Fraction of real images for validation")
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--imgsz", type=int, default=1280)
    parser.add_argument("--model", type=str, default="yolo11m.pt")
    parser.add_argument("--train-only", action="store_true",
                        help="Skip dataset prep, go straight to training")
    args = parser.parse_args()

    output = Path(args.output)
    dataset_dir = output / "dataset"
    train_imgs = dataset_dir / "images" / "train"
    train_lbls = dataset_dir / "labels" / "train"
    val_imgs = dataset_dir / "images" / "val"
    val_lbls = dataset_dir / "labels" / "val"

    if not args.train_only:
        # Clean and create dirs
        for d in [train_imgs, train_lbls, val_imgs, val_lbls]:
            d.mkdir(parents=True, exist_ok=True)

        # --- Step 1: Process real images ---
        print("=== Step 1: Real training data ===")
        ann = json.load(open(args.real_annotations))
        categories = {c["id"]: c["name"] for c in ann["categories"]}
        img_lookup = {img["id"]: img for img in ann["images"]}
        anns_by_image = defaultdict(list)
        for a in ann["annotations"]:
            anns_by_image[a["image_id"]].append(a)

        # Stratified split: hold out val_ratio of images
        all_img_ids = list(anns_by_image.keys())
        random.seed(42)
        random.shuffle(all_img_ids)
        n_val = max(1, int(len(all_img_ids) * args.val_ratio))
        val_ids = set(all_img_ids[:n_val])
        train_ids = set(all_img_ids[n_val:])

        real_images_dir = Path(args.real_images)
        real_train = 0
        real_val = 0

        for img_id in all_img_ids:
            img_info = img_lookup[img_id]
            img_path = real_images_dir / img_info["file_name"]
            if not img_path.exists():
                continue

            is_val = img_id in val_ids
            dest_imgs = val_imgs if is_val else train_imgs
            dest_lbls = val_lbls if is_val else train_lbls

            # Copy image
            shutil.copy2(img_path, dest_imgs / img_info["file_name"])

            # Convert annotations to YOLO format
            label_file = dest_lbls / (img_path.stem + ".txt")
            lines = []
            for a in anns_by_image[img_id]:
                cx, cy, w, h = coco_to_yolo(
                    a["bbox"], img_info["width"], img_info["height"]
                )
                lines.append(f"{a['category_id']} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
            label_file.write_text("\n".join(lines) + "\n")

            if is_val:
                real_val += 1
            else:
                real_train += 1

        print(f"  Real images: {real_train} train, {real_val} val")

        # --- Step 2: Add Gemini images (ALL go to train, never val) ---
        print("=== Step 2: Gemini shelf images ===")
        gemini_imgs_dir = Path(args.gemini_images)
        gemini_lbls_dir = Path(args.gemini_labels)
        gemini_count = 0
        gemini_no_label = 0

        for cat_dir in sorted(gemini_imgs_dir.iterdir()):
            if not cat_dir.is_dir() or not cat_dir.name.startswith("cat_"):
                continue
            for img_path in sorted(cat_dir.glob("*.jpg")):
                label_path = gemini_lbls_dir / (img_path.stem + ".txt")
                if not label_path.exists():
                    gemini_no_label += 1
                    continue

                # Check label is not empty
                label_content = label_path.read_text().strip()
                if not label_content:
                    gemini_no_label += 1
                    continue

                # Copy image and label to train
                shutil.copy2(img_path, train_imgs / img_path.name)
                shutil.copy2(label_path, train_lbls / (img_path.stem + ".txt"))
                gemini_count += 1

        print(f"  Gemini images: {gemini_count} (skipped {gemini_no_label} without labels)")

        # --- Step 3: Write dataset.yaml ---
        print("=== Step 3: Dataset config ===")
        yaml_content = f"path: {dataset_dir}\n"
        yaml_content += "train: images/train\n"
        yaml_content += "val: images/val\n"
        yaml_content += f"nc: {len(categories)}\n"
        yaml_content += "names:\n"
        for cat_id in sorted(categories.keys()):
            yaml_content += f"  {cat_id}: {categories[cat_id]}\n"

        yaml_path = dataset_dir / "dataset.yaml"
        yaml_path.write_text(yaml_content)

        total_train = real_train + gemini_count
        print(f"\n  Total: {total_train} train ({real_train} real + {gemini_count} gemini), {real_val} val")
        print(f"  Dataset: {yaml_path}")

    else:
        yaml_path = dataset_dir / "dataset.yaml"
        print(f"Skipping dataset prep. Using existing: {yaml_path}")

    # --- Step 4: Train ---
    print(f"\n=== Step 4: Training ===")
    print(f"  Model: {args.model}")
    print(f"  Epochs: {args.epochs}")
    print(f"  Batch: {args.batch}")
    print(f"  Image size: {args.imgsz}")

    from ultralytics import YOLO
    model = YOLO(args.model)

    results = model.train(
        data=str(yaml_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device="cuda",
        optimizer="AdamW",
        lr0=0.001,
        lrf=0.01,
        warmup_epochs=5,
        mosaic=1.0,
        mixup=0.3,
        copy_paste=0.3,
        hsv_h=0.02,
        hsv_s=0.7,
        hsv_v=0.4,
        degrees=5,
        translate=0.15,
        scale=0.5,
        fliplr=0.5,
        erasing=0.3,
        project=str(output),
        name="yolo11m_gemini",
        exist_ok=True,
        verbose=True,
    )

    print(f"\n=== Training complete ===")
    best_weights = output / "yolo11m_gemini" / "weights" / "best.pt"
    print(f"Best weights: {best_weights}")

    # Export to ONNX
    print("Exporting to ONNX...")
    best_model = YOLO(str(best_weights))
    best_model.export(format="onnx", imgsz=args.imgsz, opset=17, simplify=True)
    print("Done.")


if __name__ == "__main__":
    main()
