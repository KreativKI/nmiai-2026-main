"""
Test auto-labeling quality by running YOLO on REAL training images
and comparing predictions to ground truth COCO annotations.

Measures: if we auto-label synthetic images, how good will labels be?
"""
import json
from pathlib import Path
from collections import defaultdict, Counter


def iou(box1, box2):
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - inter
    return inter / union if union > 0 else 0


def coco_to_xyxy(bbox):
    x, y, w, h = bbox
    return [x, y, x + w, y + h]


def main():
    # Load ground truth
    ann = json.load(open("/home/jcfrugaard/trainingdata/train/annotations.json"))
    gt_by_image = defaultdict(list)
    for a in ann["annotations"]:
        gt_by_image[a["image_id"]].append(a)
    cat_counts = Counter(a["category_id"] for a in ann["annotations"])

    # Load YOLO model
    from ultralytics import YOLO
    model_path = "/home/jcfrugaard/retrain/yolo11m_maxdata_200ep/weights/best.pt"
    print(f"Loading model: {model_path}")
    model = YOLO(model_path)

    # Use val images (honest eval) + sample of train
    val_dir = Path("/home/jcfrugaard/cv-train/data/yolo_dataset/images/val")
    val_images = sorted(val_dir.glob("*.jpg"))
    train_dir = Path("/home/jcfrugaard/cv-train/data/yolo_dataset/images/train")
    train_images = sorted(train_dir.glob("*.jpg"))[:20]
    all_images = val_images + train_images
    print(f"Testing on {len(val_images)} val + {len(train_images)} train = {len(all_images)} images")

    total_gt = 0
    total_pred = 0
    matched = 0
    cat_matched = 0
    missed_gt = 0
    false_pos = 0
    per_cat = defaultdict(lambda: {"gt": 0, "matched": 0, "cat_correct": 0})

    for img_path in all_images:
        fname = img_path.name
        img_info = None
        for img in ann["images"]:
            if img["file_name"] == fname:
                img_info = img
                break
        if not img_info:
            continue

        gt_anns = gt_by_image[img_info["id"]]
        total_gt += len(gt_anns)

        # Run YOLO
        results = model(str(img_path), conf=0.15, verbose=False)
        preds = []
        if results and len(results) > 0 and results[0].boxes is not None:
            for box in results[0].boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                preds.append({"cls": cls_id, "conf": conf, "box": [x1, y1, x2, y2]})

        total_pred += len(preds)

        # Match predictions to GT
        matched_gt = set()
        for pred in preds:
            best_iou = 0
            best_idx = -1
            best_cat = -1
            for gi, gt in enumerate(gt_anns):
                if gi in matched_gt:
                    continue
                gt_box = coco_to_xyxy(gt["bbox"])
                score = iou(pred["box"], gt_box)
                if score > best_iou:
                    best_iou = score
                    best_idx = gi
                    best_cat = gt["category_id"]

            if best_iou >= 0.5:
                matched_gt.add(best_idx)
                matched += 1
                per_cat[best_cat]["matched"] += 1
                if pred["cls"] == best_cat:
                    cat_matched += 1
                    per_cat[best_cat]["cat_correct"] += 1
            else:
                false_pos += 1

        missed_gt += len(gt_anns) - len(matched_gt)
        for gt in gt_anns:
            per_cat[gt["category_id"]]["gt"] += 1

    # Results
    print(f"\n=== AUTO-LABELING QUALITY TEST ===")
    print(f"Ground truth annotations: {total_gt}")
    print(f"YOLO predictions: {total_pred}")
    print(f"Matched (IoU >= 0.5): {matched}")
    print(f"  Category correct: {cat_matched}")
    print(f"  Category wrong: {matched - cat_matched}")
    print(f"Missed GT: {missed_gt}")
    print(f"False positives: {false_pos}")
    det_recall = matched / total_gt * 100 if total_gt else 0
    cls_acc = cat_matched / matched * 100 if matched else 0
    overall = cat_matched / total_gt * 100 if total_gt else 0
    print(f"\nDetection recall: {det_recall:.1f}%")
    print(f"Classification accuracy (of detected): {cls_acc:.1f}%")
    print(f"Overall (correctly auto-labeled / total GT): {overall:.1f}%")

    # Per-tier
    print(f"\n=== BY PRODUCT TIER ===")
    tiers = [
        ("seen_once (1 ann)", 1, 2),
        ("barely_known (2 ann)", 2, 3),
        ("somewhat_known (3-9)", 3, 10),
        ("well_known (10+)", 10, 10000),
    ]
    for name, lo, hi in tiers:
        cats = [c for c in per_cat if lo <= cat_counts.get(c, 0) < hi]
        t_gt = sum(per_cat[c]["gt"] for c in cats)
        t_match = sum(per_cat[c]["matched"] for c in cats)
        t_correct = sum(per_cat[c]["cat_correct"] for c in cats)
        if t_gt > 0:
            print(f"  {name}: {len(cats)} cats, {t_gt} GT, "
                  f"detect {t_match}/{t_gt} ({t_match/t_gt*100:.0f}%), "
                  f"classify {t_correct}/{t_match} ({t_correct/max(1,t_match)*100:.0f}%)")
        else:
            print(f"  {name}: no GT in test set")

    # Worst categories (most missed)
    print(f"\n=== WORST 10 CATEGORIES (most missed) ===")
    worst = sorted(per_cat.items(), key=lambda x: x[1]["gt"] - x[1]["matched"], reverse=True)[:10]
    cats_by_id = {c["id"]: c["name"] for c in ann["categories"]}
    for cat_id, info in worst:
        missed = info["gt"] - info["matched"]
        total = info["gt"]
        name = cats_by_id.get(cat_id, f"cat_{cat_id}")[:40]
        print(f"  cat {cat_id}: {name} -- missed {missed}/{total}")


if __name__ == "__main__":
    main()
