---
priority: CRITICAL
from: overseer
timestamp: 2026-03-20 22:20 CET
---

# CV Battle Plan: Close the Generalization Gap

## The Problem
Local score: 0.9524. Leaderboard: 0.5756. Gap: 0.38.
We spent hours optimizing SAHI and DINOv2 which move scores by 0.04. The gap is 10x bigger.

**Root cause:** 248 images for 356 categories = extreme overfitting. Train/val split uses training data for both. Local 0.95 is a fiction.

## Execution Pipeline (autonomous, no waiting)

### Phase 0: Fix Evaluation (30 min, GCP)
1. Create proper 80/20 stratified train/val split
2. Re-evaluate YOLO11m on held-out val set
3. This gives our first honest local score
4. ALSO: verify category IDs match competition spec exactly (off-by-one would explain everything)

### Phase 1: Copy-Paste Augmentation (2h, GCP cv-train-1)
1. Extract product instances from COCO annotations
2. Paste onto shelf backgrounds with cv2.seamlessClone
3. Generate 500 synthetic images with auto-generated COCO annotations
4. Target: 3+ examples per category (most currently have 0-1)

### Phase 2: Gemini Images as Training Data (1h, GCP)
Gemini generation is RUNNING on cv-train-1 (43/350 categories done).
When finished: use as YOLO training data, NOT for DINOv2 gallery.
Generate YOLO-format pseudo-labels. Add to training set.

### Phase 3: Retrain YOLO11m on Augmented Data (3h, GCP)
```python
# Aggressive augmentation config
imgsz=1280, epochs=120, batch=4
mosaic=1.0, mixup=0.3, copy_paste=0.3
hsv_h=0.02, hsv_s=0.7, hsv_v=0.4
degrees=5, translate=0.15, scale=0.5
fliplr=0.5, erasing=0.3
```
Dataset: 248 real + 500 copy-paste + Gemini images = 800+ images
Also try YOLO11l (25.3M params) if time permits.

### Phase 4: Honest Evaluation + Submit
1. Evaluate on held-out 20% val set (from Phase 0)
2. Blind audit: original vs augmented
3. cv_pipeline.sh + canary subagent
4. Submit if better. If not, investigate category mapping.

## Rules
- ALL compute on GCP. Nothing heavy on local Mac.
- Boris workflow on every code change.
- Report results to /Volumes/devdrive/github_dev/nmiai-2026-main/intelligence/for-overseer/cv-status.md
- Oslo = CET = UTC+1 for all timestamps.

## What NOT to Do
- No more SAHI experiments (proven: hurts)
- No DINOv2 at inference time (proven: hurts with one-shot gallery)
- No local Docker runs (GCP only)
- No optimizing local scores (they're fake without proper val split)
