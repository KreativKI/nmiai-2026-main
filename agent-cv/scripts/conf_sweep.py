"""
Confidence threshold sweep on val set.
Find optimal conf_threshold for run.py without retraining.
"""
import json
from pathlib import Path
from collections import defaultdict
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


def coco_xyxy(b):
    return [b[0], b[1], b[0] + b[2], b[1] + b[3]]


def main():
    ann = json.load(open(str(Path.home() / "trainingdata/train/annotations.json")))
    gt_by_img = defaultdict(list)
    for a in ann["annotations"]:
        gt_by_img[a["image_id"]].append(a)
    img_map = {i["file_name"]: i for i in ann["images"]}

    model = YOLO(str(Path.home() / "retrain/yolo11m_maxdata_200ep/weights/best.pt"))
    val_imgs = sorted((Path.home() / "cv-train/data/yolo_dataset/images/val").glob("*.jpg"))
    print(f"Val images: {len(val_imgs)}")

    # Run inference ONCE at very low conf
    print("Running inference at conf=0.01...")
    all_preds = {}
    for img_path in val_imgs:
        results = model(str(img_path), conf=0.01, iou=0.5, verbose=False)
        preds = []
        if results and results[0].boxes is not None:
            for b in results[0].boxes:
                preds.append({
                    "cls": int(b.cls[0]),
                    "conf": float(b.conf[0]),
                    "box": b.xyxy[0].tolist(),
                })
        all_preds[img_path.name] = preds

    total_preds = sum(len(p) for p in all_preds.values())
    print(f"Total predictions at conf=0.01: {total_preds}")

    # Sweep
    header = f"{'Conf':>6} {'Recall':>8} {'Prec':>8} {'ClsAcc':>8} {'F1':>8} {'Score*':>8} {'Dets':>8}"
    print(f"\n{header}")
    print("-" * len(header))

    best_score = 0
    best_conf = 0.25

    for conf_t in [0.01, 0.03, 0.05, 0.08, 0.10, 0.12, 0.15, 0.18, 0.20, 0.22, 0.25, 0.28, 0.30, 0.35, 0.40, 0.50]:
        tp = 0
        fp = 0
        fn = 0
        cls_correct = 0
        total_dets = 0

        for img_path in val_imgs:
            info = img_map.get(img_path.name)
            if not info:
                continue
            gt = gt_by_img[info["id"]]
            preds = [p for p in all_preds[img_path.name] if p["conf"] >= conf_t]
            total_dets += len(preds)

            matched_gt = set()
            for pred in sorted(preds, key=lambda x: -x["conf"]):
                best_iou_val = 0
                best_idx = -1
                best_cat = -1
                for gi, g in enumerate(gt):
                    if gi in matched_gt:
                        continue
                    s = iou(pred["box"], coco_xyxy(g["bbox"]))
                    if s > best_iou_val:
                        best_iou_val = s
                        best_idx = gi
                        best_cat = g["category_id"]
                if best_iou_val >= 0.5:
                    matched_gt.add(best_idx)
                    tp += 1
                    if pred["cls"] == best_cat:
                        cls_correct += 1
                else:
                    fp += 1
            fn += len(gt) - len(matched_gt)

        prec = tp / (tp + fp) if (tp + fp) else 0
        rec = tp / (tp + fn) if (tp + fn) else 0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0
        cls_acc = cls_correct / tp if tp else 0
        # Competition score proxy: 0.7 * detection_mAP + 0.3 * classification_mAP
        # Approximation: detection ~ recall*precision, classification ~ recall*cls_acc
        score = 0.7 * rec * prec + 0.3 * rec * cls_acc

        if score > best_score:
            best_score = score
            best_conf = conf_t

        marker = " <--" if conf_t == best_conf else ""
        print(f"{conf_t:>6.2f} {rec:>8.3f} {prec:>8.3f} {cls_acc:>8.3f} {f1:>8.3f} {score:>8.3f} {total_dets:>8d}{marker}")

    print(f"\nBest score proxy: {best_score:.4f} at conf={best_conf}")
    print(f"Current run.py uses conf=0.25")
    print(f"Recommendation: {'CHANGE to ' + str(best_conf) if best_conf != 0.25 else 'KEEP 0.25'}")


if __name__ == "__main__":
    main()
