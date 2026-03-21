"""
Detailed per-category analysis on val set.
Identifies which categories are hurting our score most
and whether our Gemini generation targets them.
"""
import json
from pathlib import Path
from collections import defaultdict, Counter
from ultralytics import YOLO


def box_iou(b1, b2):
    x1 = max(b1[0], b2[0])
    y1 = max(b1[1], b2[1])
    x2 = min(b1[2], b2[2])
    y2 = min(b1[3], b2[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    a1 = (b1[2] - b1[0]) * (b1[3] - b1[1])
    a2 = (b2[2] - b2[0]) * (b2[3] - b2[1])
    return inter / (a1 + a2 - inter) if (a1 + a2 - inter) > 0 else 0


def coco_xyxy(b):
    return [b[0], b[1], b[0] + b[2], b[1] + b[3]]


def main():
    ann = json.load(open(str(Path.home() / "trainingdata/train/annotations.json")))
    cats_by_id = {c["id"]: c["name"] for c in ann["categories"]}
    cat_counts = Counter(a["category_id"] for a in ann["annotations"])
    gt_by_img = defaultdict(list)
    for a in ann["annotations"]:
        gt_by_img[a["image_id"]].append(a)
    img_map = {i["file_name"]: i for i in ann["images"]}

    # Check which categories we're generating for
    gen_progress = Path.home() / "gemini_shelf_gen/progress.json"
    generating_cats = set()
    if gen_progress.exists():
        p = json.load(open(gen_progress))
        generating_cats = {int(k) for k in p.keys()}

    model = YOLO(str(Path.home() / "retrain/yolo11m_maxdata_200ep/weights/best.pt"))
    val_imgs = sorted((Path.home() / "cv-train/data/yolo_dataset/images/val").glob("*.jpg"))

    # Per-category stats
    per_cat = defaultdict(lambda: {"gt": 0, "detected": 0, "cls_correct": 0})

    for img_path in val_imgs:
        info = img_map.get(img_path.name)
        if not info:
            continue
        gt = gt_by_img[info["id"]]

        results = model(str(img_path), conf=0.25, iou=0.5, verbose=False)
        preds = []
        if results and results[0].boxes is not None:
            for b in results[0].boxes:
                preds.append({
                    "cls": int(b.cls[0]),
                    "conf": float(b.conf[0]),
                    "box": b.xyxy[0].tolist(),
                })

        matched_gt = set()
        for pred in sorted(preds, key=lambda x: -x["conf"]):
            best_val = 0
            best_idx = -1
            best_cat = -1
            for gi, g in enumerate(gt):
                if gi in matched_gt:
                    continue
                s = box_iou(pred["box"], coco_xyxy(g["bbox"]))
                if s > best_val:
                    best_val = s
                    best_idx = gi
                    best_cat = g["category_id"]
            if best_val >= 0.5:
                matched_gt.add(best_idx)
                per_cat[best_cat]["detected"] += 1
                if pred["cls"] == best_cat:
                    per_cat[best_cat]["cls_correct"] += 1

        for g in gt:
            per_cat[g["category_id"]]["gt"] += 1

    # Sort by worst classification performance
    results = []
    for cat_id, stats in per_cat.items():
        if stats["gt"] == 0:
            continue
        det_rate = stats["detected"] / stats["gt"]
        cls_rate = stats["cls_correct"] / stats["detected"] if stats["detected"] else 0
        train_count = cat_counts.get(cat_id, 0)
        being_generated = cat_id in generating_cats
        results.append({
            "cat_id": cat_id,
            "name": cats_by_id[cat_id][:35],
            "train_count": train_count,
            "val_gt": stats["gt"],
            "det_rate": det_rate,
            "cls_rate": cls_rate,
            "generating": being_generated,
        })

    # Sort by classification accuracy (worst first)
    results.sort(key=lambda x: x["cls_rate"])

    print("=== WORST CLASSIFICATION CATEGORIES (val set) ===")
    print(f"{'Cat':>4} {'Name':<36} {'Train':>5} {'ValGT':>5} {'Det%':>5} {'Cls%':>5} {'Gen?':>4}")
    print("-" * 80)
    for r in results[:30]:
        gen = "YES" if r["generating"] else ""
        print(f"{r['cat_id']:>4} {r['name']:<36} {r['train_count']:>5} {r['val_gt']:>5} "
              f"{r['det_rate']*100:>4.0f}% {r['cls_rate']*100:>4.0f}% {gen:>4}")

    # Summary
    gen_targeted = sum(1 for r in results[:30] if r["generating"])
    print(f"\nOf 30 worst categories: {gen_targeted} are being targeted by Gemini generation")

    # Categories NOT in val set (can't measure, but might be weak)
    all_cats = set(range(356))
    in_val = set(per_cat.keys())
    not_in_val = all_cats - in_val - {355}
    not_in_val_weak = [(c, cat_counts.get(c, 0)) for c in not_in_val if cat_counts.get(c, 0) <= 9]
    print(f"\nWeak categories NOT in val set (can't measure): {len(not_in_val_weak)}")
    print(f"Being generated: {sum(1 for c, _ in not_in_val_weak if c in generating_cats)}")


if __name__ == "__main__":
    main()
