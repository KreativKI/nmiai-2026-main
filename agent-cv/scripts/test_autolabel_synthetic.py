"""
Test auto-labeling quality on existing Gemini white-bg images.
Run YOLO, see what it detects vs what category the image is for.
"""
import json
from pathlib import Path
from collections import defaultdict, Counter


def main():
    from ultralytics import YOLO

    model_path = "/home/jcfrugaard/retrain/yolo11m_maxdata_200ep/weights/best.pt"
    print(f"Loading model: {model_path}")
    model = YOLO(model_path)

    ann = json.load(open("/home/jcfrugaard/trainingdata/train/annotations.json"))
    cat_counts = Counter(a["category_id"] for a in ann["annotations"])
    cats_by_id = {c["id"]: c["name"] for c in ann["categories"]}

    synth_dir = Path("/home/jcfrugaard/synthetic_all")
    images = sorted(synth_dir.glob("cat_*_gemini_*.png"))
    print(f"Found {len(images)} Gemini images")

    total = 0
    detected_something = 0
    detected_target = 0
    target_top1 = 0
    no_detection = 0
    per_tier = defaultdict(lambda: {"total": 0, "detected": 0, "target_found": 0, "target_top1": 0})

    for img_path in images:
        name = img_path.stem
        parts = name.split("_")
        cat_id = int(parts[1])
        count = cat_counts.get(cat_id, 0)

        if count <= 1:
            tier = "seen_once"
        elif count == 2:
            tier = "barely_known"
        elif count <= 9:
            tier = "somewhat_known"
        else:
            tier = "well_known"

        total += 1
        per_tier[tier]["total"] += 1

        results = model(str(img_path), conf=0.1, verbose=False)
        if not results or len(results) == 0 or results[0].boxes is None or len(results[0].boxes) == 0:
            no_detection += 1
            continue

        detected_something += 1
        per_tier[tier]["detected"] += 1

        boxes = results[0].boxes
        detected_cats = [(int(b.cls[0]), float(b.conf[0])) for b in boxes]
        detected_cats.sort(key=lambda x: -x[1])

        found = any(c == cat_id for c, _ in detected_cats)
        if found:
            detected_target += 1
            per_tier[tier]["target_found"] += 1

        if detected_cats[0][0] == cat_id:
            target_top1 += 1
            per_tier[tier]["target_top1"] += 1

    print(f"\n=== AUTO-LABEL ON GEMINI WHITE-BG IMAGES ===")
    print(f"Total images: {total}")
    print(f"Any detection: {detected_something} ({detected_something/total*100:.0f}%)")
    print(f"Target product found: {detected_target} ({detected_target/total*100:.0f}%)")
    print(f"Target is top-1: {target_top1} ({target_top1/total*100:.0f}%)")
    print(f"No detection at all: {no_detection} ({no_detection/total*100:.0f}%)")

    print(f"\n=== BY TIER ===")
    for tier in ["seen_once", "barely_known", "somewhat_known", "well_known"]:
        t = per_tier[tier]
        if t["total"] == 0:
            continue
        print(f"  {tier}: {t['total']} imgs, "
              f"detect {t['detected']}/{t['total']} ({t['detected']/t['total']*100:.0f}%), "
              f"target found {t['target_found']}/{t['total']} ({t['target_found']/t['total']*100:.0f}%), "
              f"target top-1 {t['target_top1']}/{t['total']} ({t['target_top1']/t['total']*100:.0f}%)")


if __name__ == "__main__":
    main()
