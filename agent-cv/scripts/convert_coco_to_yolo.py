"""Convert COCO annotations to YOLO format for training."""
import json
from pathlib import Path
import shutil

def convert(coco_json: Path, images_dir: Path, output_dir: Path):
    """Convert COCO format annotations to YOLO format.

    YOLO expects per-image .txt files with:
    class_id center_x center_y width height (all normalized 0-1)
    """
    with open(coco_json) as f:
        coco = json.load(f)

    # Build image lookup
    images = {img["id"]: img for img in coco["images"]}

    # Group annotations by image_id
    anns_by_image = {}
    for ann in coco["annotations"]:
        anns_by_image.setdefault(ann["image_id"], []).append(ann)

    # Create output dirs
    out_images = output_dir / "images" / "train"
    out_labels = output_dir / "labels" / "train"
    out_images.mkdir(parents=True, exist_ok=True)
    out_labels.mkdir(parents=True, exist_ok=True)

    converted = 0
    for img_id, img_info in images.items():
        fname = img_info["file_name"]
        w, h = img_info["width"], img_info["height"]

        # Copy image
        src = images_dir / fname
        if src.exists():
            shutil.copy2(src, out_images / fname)

        # Write YOLO labels
        label_file = out_labels / (Path(fname).stem + ".txt")
        lines = []
        for ann in anns_by_image.get(img_id, []):
            # COCO bbox: [x, y, width, height] (top-left corner)
            bx, by, bw, bh = ann["bbox"]
            # Convert to YOLO: center_x, center_y, width, height (normalized)
            cx = (bx + bw / 2) / w
            cy = (by + bh / 2) / h
            nw = bw / w
            nh = bh / h
            # Clamp to [0, 1]
            cx = max(0, min(1, cx))
            cy = max(0, min(1, cy))
            nw = max(0, min(1, nw))
            nh = max(0, min(1, nh))
            lines.append(f"{ann['category_id']} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")

        label_file.write_text("\n".join(lines) + "\n" if lines else "")
        converted += 1

    # Create dataset YAML
    yaml_content = f"""path: {output_dir.resolve()}
train: images/train
val: images/train

nc: 356
names:
"""
    # Add category names
    for cat in sorted(coco["categories"], key=lambda c: c["id"]):
        yaml_content += f"  {cat['id']}: '{cat['name']}'\n"

    yaml_path = output_dir / "dataset.yaml"
    yaml_path.write_text(yaml_content)

    print(f"Converted {converted} images")
    print(f"Output: {output_dir}")
    print(f"Dataset YAML: {yaml_path}")

    # Stats
    total_anns = sum(len(v) for v in anns_by_image.values())
    print(f"Total annotations: {total_anns}")
    print(f"Avg per image: {total_anns/converted:.1f}")


if __name__ == "__main__":
    base = Path(__file__).parent.parent.parent / "trainingdata"
    convert(
        coco_json=base / "train" / "annotations.json",
        images_dir=base / "train" / "images",
        output_dir=Path(__file__).parent.parent / "data" / "yolo_dataset",
    )
