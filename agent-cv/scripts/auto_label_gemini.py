"""
Auto-label Gemini-generated shelf images using existing YOLO model.

For each generated image:
1. Run YOLO inference to detect products
2. Match detections to the KNOWN category (from filename)
3. Keep detections where:
   - The detected category matches the expected product, OR
   - We create a center-crop pseudo-label for the expected product

Output: YOLO-format label files ready for training.

This is "circular" (model predicts its own training labels), but:
- The SHELF CONTEXT is novel (model never saw these shelf scenes)
- We only keep high-confidence matches
- For unmatched products, we add a center-crop heuristic label

Usage:
  python auto_label_gemini.py --images-dir ~/gemini_shelf_gen \
    --model ~/retrain/yolo11m_maxdata_200ep/weights/best.pt \
    --output-dir ~/gemini_labeled
"""
import argparse
import json
from pathlib import Path
from collections import defaultdict

# Will be imported on GCP where ultralytics is installed
# from ultralytics import YOLO


def get_expected_category(image_path):
    """Extract expected category_id from filename like cat_026_shelf_v03.jpg"""
    name = image_path.stem
    parts = name.split("_")
    for i, part in enumerate(parts):
        if part == "cat" and i + 1 < len(parts):
            try:
                return int(parts[i + 1])
            except ValueError:
                pass
    return None


def center_crop_label(img_w, img_h, cat_id, crop_fraction=0.4):
    """Create a center-crop pseudo-label (YOLO format: class cx cy w h)."""
    cx = 0.5
    cy = 0.5
    w = crop_fraction
    h = crop_fraction
    return f"{cat_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--images-dir", type=str, required=True,
                        help="Directory with gemini_shelf_gen output (has cat_XXX/ subdirs)")
    parser.add_argument("--model", type=str, required=True,
                        help="Path to YOLO .pt model for inference")
    parser.add_argument("--output-dir", type=str, required=True,
                        help="Output directory for labeled dataset (images/ + labels/)")
    parser.add_argument("--conf", type=float, default=0.3,
                        help="Confidence threshold for YOLO detections")
    parser.add_argument("--match-bonus", action="store_true", default=True,
                        help="Lower threshold for detections matching expected category")
    parser.add_argument("--add-center-crop", action="store_true", default=True,
                        help="Add center-crop pseudo-label if expected product not detected")
    args = parser.parse_args()

    from ultralytics import YOLO
    from PIL import Image

    images_dir = Path(args.images_dir)
    output_dir = Path(args.output_dir)
    output_images = output_dir / "images" / "train"
    output_labels = output_dir / "labels" / "train"
    output_images.mkdir(parents=True, exist_ok=True)
    output_labels.mkdir(parents=True, exist_ok=True)

    # Load model
    print(f"Loading model: {args.model}")
    model = YOLO(args.model)

    # Find all generated images
    all_images = []
    for cat_dir in sorted(images_dir.iterdir()):
        if cat_dir.is_dir() and cat_dir.name.startswith("cat_"):
            for img_path in sorted(cat_dir.glob("*.jpg")):
                all_images.append(img_path)

    print(f"Found {len(all_images)} generated images")

    stats = defaultdict(int)
    matched_cats = defaultdict(int)

    for i, img_path in enumerate(all_images):
        expected_cat = get_expected_category(img_path)
        if expected_cat is None:
            stats["no_expected_cat"] += 1
            continue

        # Run YOLO inference
        results = model(str(img_path), conf=0.1, verbose=False)  # Low conf, filter later

        # Get image dimensions
        img = Image.open(img_path)
        img_w, img_h = img.size

        # Process detections
        labels = []
        found_expected = False

        if results and len(results) > 0:
            boxes = results[0].boxes
            if boxes is not None and len(boxes) > 0:
                for box in boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    x1, y1, x2, y2 = box.xyxy[0].tolist()

                    # Convert to YOLO format (normalized center + wh)
                    cx = (x1 + x2) / 2 / img_w
                    cy = (y1 + y2) / 2 / img_h
                    bw = (x2 - x1) / img_w
                    bh = (y2 - y1) / img_h

                    # Match logic
                    if cls_id == expected_cat:
                        # Expected product: lower threshold
                        if conf >= 0.15:
                            labels.append(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
                            found_expected = True
                            matched_cats[expected_cat] += 1
                            stats["matched_detections"] += 1
                    else:
                        # Other products on shelf: normal threshold
                        if conf >= args.conf:
                            labels.append(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
                            stats["other_detections"] += 1

        # If expected product not detected, add center-crop pseudo-label
        if not found_expected and args.add_center_crop:
            labels.append(center_crop_label(img_w, img_h, expected_cat))
            stats["center_crop_fallback"] += 1

        # Save image and label
        out_img = output_images / img_path.name
        out_lbl = output_labels / (img_path.stem + ".txt")

        # Copy/link image
        import shutil
        shutil.copy2(img_path, out_img)

        # Write labels
        with open(out_lbl, "w") as f:
            f.write("\n".join(labels) + "\n" if labels else "")

        stats["total_images"] += 1
        if labels:
            stats["images_with_labels"] += 1

        if (i + 1) % 50 == 0:
            print(f"  [{i+1}/{len(all_images)}] "
                  f"matched: {stats['matched_detections']}, "
                  f"other: {stats['other_detections']}, "
                  f"fallback: {stats['center_crop_fallback']}")

    print(f"\n=== LABELING COMPLETE ===")
    print(f"Total images: {stats['total_images']}")
    print(f"Images with labels: {stats['images_with_labels']}")
    print(f"Matched detections (expected product found): {stats['matched_detections']}")
    print(f"Other product detections: {stats['other_detections']}")
    print(f"Center-crop fallbacks: {stats['center_crop_fallback']}")
    print(f"Unique categories matched: {len(matched_cats)}")

    # Save stats
    stats_path = output_dir / "labeling_stats.json"
    with open(stats_path, "w") as f:
        json.dump(dict(stats), f, indent=2)

    # Save per-category match counts
    cat_stats_path = output_dir / "category_match_counts.json"
    with open(cat_stats_path, "w") as f:
        json.dump(dict(matched_cats), f, indent=2)

    print(f"\nStats saved to {stats_path}")
    print(f"Category matches saved to {cat_stats_path}")
    print(f"\nOutput directory: {output_dir}")
    print(f"Ready for YOLO training: use images/train and labels/train")


if __name__ == "__main__":
    main()
