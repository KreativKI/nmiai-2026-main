---
priority: HIGH
from: cv-agent
timestamp: 2026-03-21 15:15 CET
supersedes: LABELER-DECISION.md
---

## Labeling GUI: Updated Requirements from JC

JC confirmed the workflow. Here are the technical details:

### Core GUI (what JC interacts with)
1. Show one image at a time, full screen
2. Show which product to find: product name + small reference photo in corner
3. JC draws ONE bounding box around the target product
4. Save in YOLO format: `{category_id} {cx} {cy} {w} {h}` (normalized 0-1)
5. Next/Previous, Skip, Progress counter
6. Auto-save on Next

### YOLO Auto-Label Pass (OPTIONAL, off by default)
- Toggle or separate button: "Run YOLO auto-label on all images"
- This runs our trained YOLO model on each image to detect OTHER products on the shelf
- Appends those detections to the label file (additional lines after JC's manual box)
- Confidence threshold: 0.3 (configurable)
- This is a SECOND PASS, not part of the main labeling flow
- Can run as batch after JC finishes manual labeling

### File Structure
Input images are in subdirectories by category:
```
gemini_shelf_gen/
  cat_026/
    cat_026_shelf_v00.jpg
    cat_026_shelf_v01.jpg
    ...
  cat_057/
    cat_057_shelf_v00.jpg
    ...
  progress.json  (generation progress, has category names)
```

### Reference Images
Product studio photos are in:
```
trainingdata/NM_NGD_product_images/{EAN}/
  front.jpg
  main.jpg
  back.jpg
  ...
```

Mapping from category_id to EAN:
```
trainingdata/NM_NGD_product_images/metadata.json
  -> products[] -> {product_code, product_name, has_images}
```
Match by product_name (uppercase) against category names in:
```
trainingdata/train/annotations.json -> categories[] -> {id, name}
```

### YOLO Model for Auto-Label Pass
Path on GCP: `/home/jcfrugaard/retrain/yolo11m_maxdata_200ep/weights/best.pt`
Local: will need to be downloaded. ~40MB .pt file.
Requires: `pip install ultralytics`

### Output Format
Per image, one .txt file:
```
# Line 1: JC's manual box (target product)
{cat_id} 0.45 0.52 0.30 0.40
# Lines 2+: YOLO auto-detected products (optional second pass)
{other_cat_id} 0.12 0.23 0.15 0.20
{other_cat_id} 0.78 0.45 0.12 0.18
```

### Priority
Images are being generated RIGHT NOW on GCP. First batch (~75 images) already done.
Expected total: ~800 images by ~17:00 CET today.
JC wants to start labeling as soon as possible.
