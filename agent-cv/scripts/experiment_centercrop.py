"""
Experiment: Train YOLO11m with center-crop heuristic labels on Gemini shelf images.

Tests whether realistic shelf images help even with approximate bounding boxes.
The target product is typically centered/prominent in generated images.

Creates labels with a 40% center crop for the target product only.
Merges with real training data and trains.
"""
import json
import shutil
from pathlib import Path
from collections import Counter
from ultralytics import YOLO


def main():
    gen_dir = Path.home() / "gemini_shelf_gen"
    ann_path = Path.home() / "trainingdata/train/annotations.json"
    real_images = Path.home() / "trainingdata/train/images"
    output = Path.home() / "experiment_centercrop"
    dataset = output / "dataset"

    train_imgs = dataset / "images" / "train"
    train_lbls = dataset / "labels" / "train"
    val_imgs = dataset / "images" / "val"
    val_lbls = dataset / "labels" / "val"

    for d in [train_imgs, train_lbls, val_imgs, val_lbls]:
        d.mkdir(parents=True, exist_ok=True)

    # Load annotations
    ann = json.load(open(ann_path))
    cats = {c["id"]: c["name"] for c in ann["categories"]}
    img_lookup = {img["id"]: img for img in ann["images"]}
    from collections import defaultdict
    anns_by_image = defaultdict(list)
    for a in ann["annotations"]:
        anns_by_image[a["image_id"]].append(a)

    # Step 1: Copy real images with proper split
    print("=== Real training data ===")
    import random
    random.seed(42)
    all_img_ids = list(anns_by_image.keys())
    random.shuffle(all_img_ids)
    n_val = max(1, int(len(all_img_ids) * 0.15))
    val_ids = set(all_img_ids[:n_val])

    real_train_count = 0
    real_val_count = 0
    for img_id in all_img_ids:
        img_info = img_lookup[img_id]
        src = real_images / img_info["file_name"]
        if not src.exists():
            continue

        is_val = img_id in val_ids
        dest_i = val_imgs if is_val else train_imgs
        dest_l = val_lbls if is_val else train_lbls

        shutil.copy2(src, dest_i / img_info["file_name"])

        lines = []
        for a in anns_by_image[img_id]:
            x, y, w, h = a["bbox"]
            iw, ih = img_info["width"], img_info["height"]
            cx = (x + w / 2) / iw
            cy = (y + h / 2) / ih
            nw = w / iw
            nh = h / ih
            lines.append(f"{a['category_id']} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")
        (dest_l / (Path(img_info["file_name"]).stem + ".txt")).write_text("\n".join(lines) + "\n")

        if is_val:
            real_val_count += 1
        else:
            real_train_count += 1

    print(f"  Real: {real_train_count} train, {real_val_count} val")

    # Step 2: Add Gemini images with center-crop labels (train only)
    print("=== Gemini images (center-crop labels) ===")
    gemini_count = 0
    for cat_dir in sorted(gen_dir.iterdir()):
        if not cat_dir.is_dir() or not cat_dir.name.startswith("cat_"):
            continue
        cat_id = int(cat_dir.name.split("_")[1])
        for img_path in sorted(cat_dir.glob("*.jpg")):
            shutil.copy2(img_path, train_imgs / img_path.name)
            # Center crop label: product at center, 40% of image
            label = f"{cat_id} 0.500000 0.500000 0.400000 0.400000"
            (train_lbls / (img_path.stem + ".txt")).write_text(label + "\n")
            gemini_count += 1

    print(f"  Gemini: {gemini_count} images with center-crop labels")
    print(f"  Total train: {real_train_count + gemini_count}")

    # Step 3: Write dataset.yaml
    yaml = f"path: {dataset}\ntrain: images/train\nval: images/val\nnc: {len(cats)}\nnames:\n"
    for cid in sorted(cats.keys()):
        yaml += f"  {cid}: {cats[cid]}\n"
    (dataset / "dataset.yaml").write_text(yaml)

    # Step 4: Train
    print(f"\n=== Training YOLO11m (center-crop experiment) ===")
    model = YOLO("yolo11m.pt")
    model.train(
        data=str(dataset / "dataset.yaml"),
        epochs=150,
        imgsz=1280,
        batch=4,
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
        name="yolo11m_centercrop",
        exist_ok=True,
        verbose=True,
    )

    print("\n=== Experiment complete ===")
    best = output / "yolo11m_centercrop" / "weights" / "best.pt"
    print(f"Best weights: {best}")
    print("Compare val mAP against maxdata model (0.816) to measure impact.")


if __name__ == "__main__":
    main()
