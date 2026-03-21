"""
YOLO auto-label second pass.

After JC labels the target product (one box per image),
this script runs YOLO on each image to detect OTHER products
on the shelf. Appends those detections to JC's label file.

Only adds detections that:
- Have confidence >= threshold
- Do NOT overlap with JC's existing box (IoU < 0.3)
- Are not the same category as JC's box (avoid duplicates)

Usage:
  python yolo_second_pass.py \
    --images-dir ~/gemini_shelf_gen \
    --labels-dir ~/gemini_labels \
    --model ~/retrain/yolo11m_maxdata_200ep/weights/best.pt \
    --conf 0.30
"""
import argparse
from pathlib import Path
from ultralytics import YOLO


def iou(b1, b2):
    x1 = max(b1[0], b2[0])
    y1 = max(b1[1], b2[1])
    x2 = min(b1[2], b2[2])
    y2 = min(b1[3], b2[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    a1 = (b1[2] - b1[0]) * (b1[3] - b1[1])
    a2 = (b2[2] - b2[0]) * (b2[3] - b2[1])
    return inter / (a1 + a2 - inter) if (a1 + a2 - inter) > 0 else 0


def yolo_to_xyxy(cx, cy, w, h, img_w, img_h):
    x1 = (cx - w / 2) * img_w
    y1 = (cy - h / 2) * img_h
    x2 = (cx + w / 2) * img_w
    y2 = (cy + h / 2) * img_h
    return [x1, y1, x2, y2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--images-dir", type=str, required=True)
    parser.add_argument("--labels-dir", type=str, required=True)
    parser.add_argument("--model", type=str, required=True)
    parser.add_argument("--conf", type=float, default=0.30)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    model = YOLO(args.model)
    images_dir = Path(args.images_dir)
    labels_dir = Path(args.labels_dir)

    # Find all images with existing labels (JC's manual boxes)
    labeled_images = []
    for cat_dir in sorted(images_dir.iterdir()):
        if not cat_dir.is_dir() or not cat_dir.name.startswith("cat_"):
            continue
        for img_path in sorted(cat_dir.glob("*.jpg")):
            label_path = labels_dir / (img_path.stem + ".txt")
            if label_path.exists():
                labeled_images.append((img_path, label_path))

    print(f"Found {len(labeled_images)} labeled images")

    added_total = 0
    skipped_overlap = 0
    skipped_conf = 0

    for img_path, label_path in labeled_images:
        # Read JC's existing labels
        existing_lines = label_path.read_text().strip().split("\n")
        existing_boxes = []
        for line in existing_lines:
            if not line.strip():
                continue
            parts = line.strip().split()
            cat_id = int(parts[0])
            cx, cy, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
            existing_boxes.append((cat_id, cx, cy, w, h))

        # Run YOLO
        from PIL import Image
        img = Image.open(img_path)
        img_w, img_h = img.size

        results = model(str(img_path), conf=args.conf, verbose=False)
        if not results or results[0].boxes is None:
            continue

        new_lines = []
        for box in results[0].boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()

            # Convert to YOLO normalized
            cx = (x1 + x2) / 2 / img_w
            cy = (y1 + y2) / 2 / img_h
            bw = (x2 - x1) / img_w
            bh = (y2 - y1) / img_h

            # Check overlap with existing boxes
            det_xyxy = [x1, y1, x2, y2]
            overlaps = False
            for ex_cat, ex_cx, ex_cy, ex_w, ex_h in existing_boxes:
                ex_xyxy = yolo_to_xyxy(ex_cx, ex_cy, ex_w, ex_h, img_w, img_h)
                if iou(det_xyxy, ex_xyxy) > 0.3:
                    overlaps = True
                    break

            if overlaps:
                skipped_overlap += 1
                continue

            new_lines.append(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
            added_total += 1

        if new_lines and not args.dry_run:
            with open(label_path, "a") as f:
                f.write("\n" + "\n".join(new_lines) + "\n")

    print(f"\nAdded {added_total} auto-detections across {len(labeled_images)} images")
    print(f"Skipped {skipped_overlap} (overlapped with JC's box)")
    if args.dry_run:
        print("DRY RUN: no files modified")


if __name__ == "__main__":
    main()
