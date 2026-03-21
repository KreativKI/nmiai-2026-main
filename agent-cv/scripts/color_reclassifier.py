"""
Color-based re-classifier for confused product pairs.

After YOLO detects a product, this re-examines the crop using
color histograms compared against reference product images.

The insight: products that YOLO confuses (Evergood Filtermalt vs Kokmalt,
different egg brands, etc.) often have distinct color profiles.
YOLO looks at shapes/patterns, but COLOR is a strong brand signal.

Strategy:
1. Build color "fingerprints" from reference product images (studio photos)
2. When YOLO detects a product, crop it and compute its color fingerprint
3. Compare against all candidate categories' fingerprints
4. If a better match is found with high confidence, override YOLO's classification

This targets the 30% classification component of the score.
"""
import json
import numpy as np
from pathlib import Path
from collections import defaultdict, Counter
import cv2


def compute_color_fingerprint(img, bins=32):
    """
    Compute a color histogram fingerprint for an image.
    Uses HSV color space (better for brand colors than RGB).
    Returns normalized histogram as a 1D array.
    """
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    # H: 0-180, S: 0-255, V: 0-255
    h_hist = cv2.calcHist([hsv], [0], None, [bins], [0, 180])
    s_hist = cv2.calcHist([hsv], [1], None, [bins], [0, 256])
    v_hist = cv2.calcHist([hsv], [2], None, [bins], [0, 256])

    # Concatenate and normalize
    fingerprint = np.concatenate([h_hist, s_hist, v_hist]).flatten()
    fingerprint = fingerprint / (fingerprint.sum() + 1e-8)
    return fingerprint


def compute_dominant_colors(img, k=5):
    """
    Extract k dominant colors using k-means clustering.
    Returns sorted list of (color_hsv, proportion).
    """
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    pixels = hsv.reshape(-1, 3).astype(np.float32)

    # Sample if too many pixels
    if len(pixels) > 10000:
        idx = np.random.choice(len(pixels), 10000, replace=False)
        pixels = pixels[idx]

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, labels, centers = cv2.kmeans(pixels, k, None, criteria, 3, cv2.KMEANS_PP_CENTERS)

    # Count labels
    counts = np.bincount(labels.flatten(), minlength=k)
    proportions = counts / counts.sum()

    # Sort by proportion
    order = np.argsort(-proportions)
    return [(centers[i].astype(int).tolist(), float(proportions[i])) for i in order]


def histogram_similarity(fp1, fp2):
    """Compare two fingerprints using correlation."""
    return cv2.compareHist(
        fp1.astype(np.float32).reshape(-1, 1),
        fp2.astype(np.float32).reshape(-1, 1),
        cv2.HISTCMP_CORREL
    )


def build_reference_gallery(product_images_dir, metadata_path, annotations_path):
    """
    Build color fingerprints from reference product images.
    Returns: {category_id: [fingerprint1, fingerprint2, ...]}
    """
    ann = json.load(open(annotations_path))
    cats_by_id = {c["id"]: c["name"] for c in ann["categories"]}
    meta = json.load(open(metadata_path))

    # Build name -> EAN mapping
    product_by_name = {}
    for p in meta["products"]:
        if p["has_images"]:
            product_by_name[p["product_name"].strip().upper()] = p["product_code"]

    gallery = {}
    matched = 0

    for cat_id, cat_name in cats_by_id.items():
        cn = cat_name.strip().upper()
        ean = product_by_name.get(cn)
        if not ean:
            continue

        ean_dir = Path(product_images_dir) / ean
        if not ean_dir.is_dir():
            continue

        fingerprints = []
        dominant_colors = []
        for fname in ["front.jpg", "main.jpg"]:
            fpath = ean_dir / fname
            if fpath.exists():
                img = cv2.imread(str(fpath))
                if img is not None:
                    fingerprints.append(compute_color_fingerprint(img))
                    dominant_colors.append(compute_dominant_colors(img))

        if fingerprints:
            gallery[cat_id] = {
                "fingerprints": fingerprints,
                "dominant_colors": dominant_colors,
                "name": cat_name,
            }
            matched += 1

    print(f"Built color gallery: {matched} categories with reference images")
    return gallery


def reclassify_crop(crop_img, yolo_cat_id, gallery, confused_pairs, threshold=0.15):
    """
    Given a crop and YOLO's classification, check if a confused pair
    has a better color match.

    Returns: (new_cat_id, confidence_delta) or (yolo_cat_id, 0) if no change.
    """
    if yolo_cat_id not in confused_pairs:
        return yolo_cat_id, 0.0

    crop_fp = compute_color_fingerprint(crop_img)

    # Compare against YOLO's prediction
    yolo_score = 0.0
    if yolo_cat_id in gallery:
        for ref_fp in gallery[yolo_cat_id]["fingerprints"]:
            s = histogram_similarity(crop_fp, ref_fp)
            yolo_score = max(yolo_score, s)

    # Compare against confused alternatives
    best_alt_id = yolo_cat_id
    best_alt_score = yolo_score

    for alt_cat_id in confused_pairs[yolo_cat_id]:
        if alt_cat_id not in gallery:
            continue
        for ref_fp in gallery[alt_cat_id]["fingerprints"]:
            s = histogram_similarity(crop_fp, ref_fp)
            if s > best_alt_score:
                best_alt_score = s
                best_alt_id = alt_cat_id

    delta = best_alt_score - yolo_score
    if delta > threshold:
        return best_alt_id, delta
    return yolo_cat_id, 0.0


def test_on_val(gallery, confused_pairs, annotations_path, images_dir, model_path):
    """Test color reclassifier on val set."""
    from ultralytics import YOLO

    ann = json.load(open(annotations_path))
    cats_by_id = {c["id"]: c["name"] for c in ann["categories"]}
    gt_by_img = defaultdict(list)
    for a in ann["annotations"]:
        gt_by_img[a["image_id"]].append(a)
    img_map = {i["file_name"]: i for i in ann["images"]}

    model = YOLO(model_path)
    val_imgs = sorted(Path(images_dir).glob("*.jpg"))

    yolo_correct = 0
    reclass_correct = 0
    reclass_changes = 0
    reclass_improved = 0
    reclass_hurt = 0
    total_matched = 0

    for img_path in val_imgs:
        info = img_map.get(img_path.name)
        if not info:
            continue

        gt = gt_by_img[info["id"]]
        full_img = cv2.imread(str(img_path))
        if full_img is None:
            continue

        results = model(str(img_path), conf=0.25, verbose=False)
        if not results or results[0].boxes is None:
            continue

        for box in results[0].boxes:
            yolo_cls = int(box.cls[0])
            x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]

            # Find matching GT
            best_iou = 0
            gt_cat = -1
            for g in gt:
                gx, gy, gw, gh = g["bbox"]
                gx2, gy2 = gx + gw, gy + gh
                ix1 = max(x1, gx)
                iy1 = max(y1, gy)
                ix2 = min(x2, gx2)
                iy2 = min(y2, gy2)
                inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
                a1 = (x2 - x1) * (y2 - y1)
                a2 = gw * gh
                iou = inter / (a1 + a2 - inter) if (a1 + a2 - inter) > 0 else 0
                if iou > best_iou:
                    best_iou = iou
                    gt_cat = g["category_id"]

            if best_iou < 0.5 or gt_cat < 0:
                continue

            total_matched += 1
            yolo_was_correct = (yolo_cls == gt_cat)
            if yolo_was_correct:
                yolo_correct += 1

            # Crop and reclassify
            crop = full_img[max(0, y1):y2, max(0, x1):x2]
            if crop.size == 0:
                if yolo_was_correct:
                    reclass_correct += 1
                continue

            new_cls, delta = reclassify_crop(crop, yolo_cls, gallery, confused_pairs)

            if new_cls != yolo_cls:
                reclass_changes += 1
                if new_cls == gt_cat:
                    reclass_improved += 1
                elif yolo_was_correct:
                    reclass_hurt += 1

            new_correct = (new_cls == gt_cat)
            if new_correct:
                reclass_correct += 1

    print(f"\n=== COLOR RECLASSIFIER RESULTS ===")
    print(f"Total matched detections: {total_matched}")
    print(f"YOLO correct: {yolo_correct} ({yolo_correct/total_matched*100:.1f}%)")
    print(f"After reclass: {reclass_correct} ({reclass_correct/total_matched*100:.1f}%)")
    print(f"Changes made: {reclass_changes}")
    print(f"  Improved: {reclass_improved}")
    print(f"  Hurt: {reclass_hurt}")
    print(f"Net gain: {reclass_improved - reclass_hurt} correct classifications")


def main():
    product_images_dir = str(Path.home() / "trainingdata/NM_NGD_product_images")
    metadata_path = str(Path.home() / "trainingdata/NM_NGD_product_images/metadata.json")
    annotations_path = str(Path.home() / "trainingdata/train/annotations.json")
    val_images_dir = str(Path.home() / "cv-train/data/yolo_dataset/images/val")
    model_path = str(Path.home() / "retrain/yolo11m_maxdata_200ep/weights/best.pt")

    # Build gallery
    print("Building color reference gallery...")
    gallery = build_reference_gallery(product_images_dir, metadata_path, annotations_path)

    # Define confused pairs (from our confusion analysis)
    confused_pairs = {
        100: [304],  # EVERGOOD CLASSIC FILTERMALT -> KOKMALT
        304: [100],
        92: [345],   # KNEKKEBRØD GODT FOR DEG -> URTER&HAVSALT
        345: [92, 212],
        105: [283],  # EGG ØKOLOGISK -> GÅRDSEGG
        283: [105],
        351: [110],  # BREMYKT MYKERE -> BREMYKT
        110: [351],
        240: [47],   # SUPERGRANOLA -> GRANOLA EPLE
        47: [240],
        186: [268],  # SUPERGRØT SKOGSBÆR -> SUPERGRØT KANEL
        268: [186],
        160: [171],  # ALI ORIGINAL KOKMALT -> FILTERMALT
        171: [160],
        341: [304],  # EVERGOOD HELE BØNNER -> KOKMALT
        347: [49],   # EVERGOOD DARK ROAST PRESSMALT -> FILTERMALT
        49: [347],
        315: [201],  # 4-KORN -> MUSLI FRUKT
        201: [315],
        209: [296],  # DELIKATESS SESAM -> FIBER BALANCE
        296: [209],
        292: [137],  # NESCAFE AZERA AMERICANO -> ESPRESSO
        137: [292],
        128: [48],   # SMØREMYK LETT -> SMØREMYK
        48: [128],
        59: [61],    # MÜSLI BLÅBÆR -> MUSLI BLÅBÆR (likely encoding diff)
        61: [59],
        212: [345],  # KNEKKEBRØD -> URTER&HAVSALT
    }

    print(f"Confused pairs: {len(confused_pairs)} categories")

    # Test
    test_on_val(gallery, confused_pairs, annotations_path, val_images_dir, model_path)


if __name__ == "__main__":
    main()
