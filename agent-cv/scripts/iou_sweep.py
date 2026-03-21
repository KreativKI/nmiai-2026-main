"""
NMS IoU threshold sweep on val set.
Find optimal iou_threshold for run.py.
"""
import json
from pathlib import Path
from collections import defaultdict
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


def evaluate(model, val_imgs, img_map, gt_by_img, conf_t, iou_t):
    tp = 0
    fp = 0
    fn = 0
    cls_correct = 0

    for img_path in val_imgs:
        info = img_map.get(img_path.name)
        if not info:
            continue
        gt = gt_by_img[info["id"]]

        results = model(str(img_path), conf=conf_t, iou=iou_t, verbose=False)
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
                tp += 1
                if pred["cls"] == best_cat:
                    cls_correct += 1
            else:
                fp += 1
        fn += len(gt) - len(matched_gt)

    prec = tp / (tp + fp) if (tp + fp) else 0
    rec = tp / (tp + fn) if (tp + fn) else 0
    cls_acc = cls_correct / tp if tp else 0
    score = 0.7 * rec * prec + 0.3 * rec * cls_acc
    return rec, prec, cls_acc, score, tp + fp


def main():
    ann = json.load(open(str(Path.home() / "trainingdata/train/annotations.json")))
    gt_by_img = defaultdict(list)
    for a in ann["annotations"]:
        gt_by_img[a["image_id"]].append(a)
    img_map = {i["file_name"]: i for i in ann["images"]}

    model = YOLO(str(Path.home() / "retrain/yolo11m_maxdata_200ep/weights/best.pt"))
    val_imgs = sorted((Path.home() / "cv-train/data/yolo_dataset/images/val").glob("*.jpg"))
    print(f"Val images: {len(val_imgs)}")

    # Best conf from previous sweep
    conf_t = 0.28

    header = f"{'IoU_NMS':>8} {'Recall':>8} {'Prec':>8} {'ClsAcc':>8} {'Score':>8} {'Dets':>8}"
    print(f"\nConf={conf_t}\n{header}")
    print("-" * len(header))

    best_score = 0
    best_iou = 0.5

    for iou_t in [0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.8]:
        rec, prec, cls_acc, score, dets = evaluate(
            model, val_imgs, img_map, gt_by_img, conf_t, iou_t
        )
        marker = " <--" if score > best_score else ""
        if score > best_score:
            best_score = score
            best_iou = iou_t
        print(f"{iou_t:>8.2f} {rec:>8.3f} {prec:>8.3f} {cls_acc:>8.3f} {score:>8.3f} {dets:>8d}{marker}")

    print(f"\nBest score: {best_score:.4f} at iou_nms={best_iou}")
    print(f"Current run.py uses iou=0.5")


if __name__ == "__main__":
    main()
