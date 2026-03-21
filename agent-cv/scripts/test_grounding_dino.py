"""
Test Grounding DINO 1.5 for auto-labeling grocery shelf images.

Compares: given a product name, can DINO find it on a shelf image
where our YOLO model fails (37% on rare products)?

Run on GCP VM with L4 GPU.
"""
import json
import time
from pathlib import Path
from collections import defaultdict, Counter
from PIL import Image
import torch


def test_on_real_images(model, processor, annotations_path, images_dir):
    """Test DINO on real training images where we have ground truth."""
    ann = json.load(open(annotations_path))
    cats_by_id = {c["id"]: c["name"] for c in ann["categories"]}
    cat_counts = Counter(a["category_id"] for a in ann["annotations"])
    gt_by_image = defaultdict(list)
    for a in ann["annotations"]:
        gt_by_image[a["image_id"]].append(a)
    img_lookup = {img["id"]: img for img in ann["images"]}

    # Test on a subset of images
    test_images = sorted(Path(images_dir).glob("*.jpg"))[:10]
    print(f"\nTesting on {len(test_images)} real images...")

    for img_path in test_images:
        img_info = None
        for img in ann["images"]:
            if img["file_name"] == img_path.name:
                img_info = img
                break
        if not img_info:
            continue

        gt_anns = gt_by_image[img_info["id"]]
        image = Image.open(img_path)

        # Pick a few GT categories to search for
        seen_cats = set()
        for gt in gt_anns[:5]:
            cat_id = gt["category_id"]
            if cat_id in seen_cats:
                continue
            seen_cats.add(cat_id)
            product_name = cats_by_id[cat_id]

            # Run DINO with product name as prompt
            text_prompt = product_name
            inputs = processor(images=image, text=text_prompt, return_tensors="pt").to("cuda")

            with torch.no_grad():
                outputs = model(**inputs)

            target_sizes = torch.tensor([image.size[::-1]]).to("cuda")
            raw_results = processor.post_process_grounded_object_detection(
                outputs,
                target_sizes=target_sizes,
                input_ids=inputs["input_ids"],
            )

            # Filter by threshold
            all_boxes = raw_results[0]["boxes"]
            all_scores = raw_results[0]["scores"]
            mask = all_scores >= 0.2
            boxes = all_boxes[mask]
            scores = all_scores[mask]

            # Check if any detection overlaps with GT
            gt_box = gt["bbox"]  # COCO: [x, y, w, h]
            gt_x1, gt_y1 = gt_box[0], gt_box[1]
            gt_x2, gt_y2 = gt_box[0] + gt_box[2], gt_box[1] + gt_box[3]

            found = False
            best_iou = 0
            for box, score in zip(boxes, scores):
                bx1, by1, bx2, by2 = box.cpu().numpy()
                # IoU
                ix1 = max(gt_x1, bx1)
                iy1 = max(gt_y1, by1)
                ix2 = min(gt_x2, bx2)
                iy2 = min(gt_y2, by2)
                inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
                area1 = (gt_x2 - gt_x1) * (gt_y2 - gt_y1)
                area2 = (bx2 - bx1) * (by2 - by1)
                union = area1 + area2 - inter
                iou = inter / union if union > 0 else 0
                if iou > best_iou:
                    best_iou = iou
                if iou >= 0.3:
                    found = True

            tier = "rare" if cat_counts[cat_id] <= 9 else "common"
            status = "FOUND" if found else "MISSED"
            print(f"  [{status}] cat {cat_id} ({tier}): {product_name[:40]} "
                  f"| dets={len(boxes)}, best_iou={best_iou:.2f}")


def test_on_gemini_shelf(model, processor, gen_dir, annotations_path):
    """Test DINO on our new Gemini shelf images."""
    ann = json.load(open(annotations_path))
    cats_by_id = {c["id"]: c["name"] for c in ann["categories"]}
    cat_counts = Counter(a["category_id"] for a in ann["annotations"])

    gen_path = Path(gen_dir)
    cat_dirs = sorted([d for d in gen_path.iterdir() if d.is_dir() and d.name.startswith("cat_")])

    if not cat_dirs:
        print(f"No generated images found in {gen_dir}")
        return

    print(f"\nTesting on {len(cat_dirs)} generated categories...")

    found_total = 0
    missed_total = 0
    per_tier = defaultdict(lambda: {"found": 0, "missed": 0})

    for cat_dir in cat_dirs[:15]:  # Test first 15 categories
        cat_id = int(cat_dir.name.split("_")[1])
        product_name = cats_by_id.get(cat_id, f"product_{cat_id}")
        count = cat_counts.get(cat_id, 0)
        tier = "seen_once" if count <= 1 else "barely_known" if count == 2 else "somewhat_known" if count <= 9 else "well_known"

        # Test first image
        imgs = sorted(cat_dir.glob("*.jpg"))
        if not imgs:
            continue
        img_path = imgs[0]
        image = Image.open(img_path)

        # Run DINO
        text_prompt = product_name
        inputs = processor(images=image, text=text_prompt, return_tensors="pt").to("cuda")

        with torch.no_grad():
            outputs = model(**inputs)

        target_sizes = torch.tensor([image.size[::-1]]).to("cuda")
        raw_results = processor.post_process_grounded_object_detection(
            outputs,
            target_sizes=target_sizes,
            input_ids=inputs["input_ids"],
        )

        all_boxes = raw_results[0]["boxes"]
        all_scores = raw_results[0]["scores"]
        mask = all_scores >= 0.2
        boxes = all_boxes[mask]
        scores = all_scores[mask]
        best_score = float(scores[0]) if len(scores) > 0 else 0

        has_detection = len(boxes) > 0
        if has_detection:
            found_total += 1
            per_tier[tier]["found"] += 1
        else:
            missed_total += 1
            per_tier[tier]["missed"] += 1

        status = "FOUND" if has_detection else "MISSED"
        print(f"  [{status}] cat {cat_id} ({tier}, {count} ann): {product_name[:40]} "
              f"| dets={len(boxes)}, best_conf={best_score:.2f}")

    print(f"\n=== DINO on Gemini shelf images ===")
    print(f"Found: {found_total}, Missed: {missed_total}")
    if found_total + missed_total > 0:
        print(f"Detection rate: {found_total / (found_total + missed_total) * 100:.0f}%")
    for tier in ["seen_once", "barely_known", "somewhat_known", "well_known"]:
        t = per_tier[tier]
        total = t["found"] + t["missed"]
        if total > 0:
            print(f"  {tier}: {t['found']}/{total} ({t['found']/total*100:.0f}%)")


def main():
    print("Loading Grounding DINO...")
    from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection

    model_id = "IDEA-Research/grounding-dino-tiny"
    processor = AutoProcessor.from_pretrained(model_id)
    model = AutoModelForZeroShotObjectDetection.from_pretrained(model_id).to("cuda")
    print("Model loaded.")

    annotations_path = str(Path.home() / "trainingdata/train/annotations.json")
    images_dir = str(Path.home() / "trainingdata/train/images")
    gen_dir = str(Path.home() / "gemini_shelf_gen")

    # Test 1: Real images (ground truth available)
    test_on_real_images(model, processor, annotations_path, images_dir)

    # Test 2: New Gemini shelf images
    test_on_gemini_shelf(model, processor, gen_dir, annotations_path)


if __name__ == "__main__":
    main()
