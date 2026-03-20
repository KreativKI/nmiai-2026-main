---
priority: CRITICAL
from: overseer
timestamp: 2026-03-20 05:40 CET
self-destruct: after incorporating into plan.md and starting work, delete
---

## Complete Research Results: How to Beat 0.5735

Three parallel research agents completed. Here's the definitive action plan.
Replace your current plan.md phases with these. Work top-down, commit after each.

---

## PHASE 1: TTA on YOLO11m (NO RETRAINING, submit as v3)
**Expected: +2-5% score. Time: 1-2 hours.**

Add Test-Time Augmentation to current run.py:
- Run inference at 3 scales: 1024, 1280, 1536
- Add horizontal flip at each scale
- Merge all predictions with `weighted_boxes_fusion` from ensemble-boxes (pre-installed!)
- CRITICAL: reverse flip augmentation on boxes before fusion (mirror x coords)

Alternatively, for ONNX inference, implement manually:
```
For each image:
  preds_orig = infer(image, 1280)
  preds_flip = infer(hflip(image), 1280)  # then mirror boxes back
  preds_large = infer(image, 1536)
  fused = weighted_boxes_fusion([preds_orig, preds_flip, preds_large], weights=[1.0, 1.0, 0.8])
```

Must stay under 300s total timeout. Test locally first.
**Docker validate. Build ZIP. JC will submit when awake.**
**Commit: "Phase 1: TTA v3 submission"**

---

## PHASE 2: SAHI-Style Sliced Inference (NO RETRAINING)
**Expected: +3-8% for small products. Time: 2-3 hours.**

Grocery shelf images are high-res with many small products. Tile the image:
1. Slice image into overlapping tiles (e.g., 640x640 with 20% overlap)
2. Run detection on each tile
3. Map tile-local coordinates back to full-image coordinates
4. Merge all detections with WBF (handles overlap region duplicates)

Implement in pure numpy/cv2 in run.py. The SAHI library is NOT installed but the logic is simple.

Can combine with TTA from Phase 1 for maximum effect.
**Docker validate. Build ZIP.**
**Commit: "Phase 2: SAHI sliced inference"**

---

## PHASE 3: DINOv2 Crop-and-Classify (BIGGEST CLASSIFICATION BOOST)
**Expected: +5-15% on classification mAP (the 30% component). Time: 3-4 hours.**

Our 0.5735 likely breaks down as: ~0.75 detection * 0.7 weight + weak classification * 0.3 weight. Classification is where the score ceiling is.

**Pipeline:**
1. Use YOLO for detection (bbox only)
2. Crop each detected product from the original image
3. Embed with DINOv2 ViT-S from timm 0.9.12 (PRE-INSTALLED in sandbox!)
4. kNN match against pre-computed embeddings of 327 reference product images
5. Assign category_id of nearest reference

**To build:**
A. Download/extract NM_NGD_product_images.zip (327 reference images)
B. Write a script to embed all references with DINOv2 ViT-S, save as gallery.npy
C. Export DINOv2 ViT-S to ONNX FP16 (~42MB)
D. Update run.py: after YOLO detection, crop each box, embed with DINOv2 ONNX, cosine similarity against gallery, assign best match category_id

**Model:** `timm.create_model('vit_small_patch14_dinov2.lvd142m', pretrained=True, num_classes=0)`
**Reference averaging:** For each product, embed 8 crops (center + corners + augmented), average embeddings. Stabilizes against angle/lighting.

**Weight budget:** YOLO11m ONNX (78MB) + DINOv2 ViT-S FP16 (42MB) + gallery.npy (<1MB) = ~121MB. Well within 420MB. Counts as 2 of 3 weight files.

**Commit: "Phase 3: DINOv2 crop-and-classify pipeline"**

---

## PHASE 4: Train YOLOv12m on GCP (New VM)
**Expected: +1-2% from architecture diversity. Time: ~10h training (runs in background).**

Create cv-train-3:
```
gcloud compute instances create cv-train-3 \
  --zone=europe-west2-a \
  --machine-type=g2-standard-8 \
  --accelerator=type=nvidia-l4,count=1 \
  --image-family=pytorch-latest-gpu \
  --image-project=deeplearning-platform-release \
  --boot-disk-size=100GB \
  --maintenance-policy=TERMINATE \
  --project=ai-nm26osl-1779
```

Train with enhanced augmentation:
```python
from ultralytics import YOLO
model = YOLO("yolov12m.pt")
model.train(
    data="norgesgruppen.yaml", imgsz=1280, epochs=150,
    batch=8, mosaic=1.0, mixup=0.15, copy_paste=0.1,
    close_mosaic=15, scale=0.9, hsv_h=0.015, hsv_s=0.7,
    hsv_v=0.4, degrees=5.0, patience=30
)
```

Same ONNX output format as YOLO11m, so run.py postprocessing works as-is.
**Commit: "Phase 4: YOLOv12m training started on cv-train-3"**

---

## PHASE 5: WBF Ensemble (when 2+ models ready)
**Expected: +1.5-2% detection mAP. Time: 2 hours.**

Build ensemble run.py:
1. Load best YOLO (11m or 12m) + DINOv2 classifier
2. Or load 2 YOLOs + DINOv2 (if 3 weights fit in 420MB)
3. Run each detector with TTA + SAHI
4. WBF-fuse all detections: `iou_thr=0.55, skip_box_thr=0.001`
5. Score calibration: rank-based normalization across models before fusion
6. Crop-and-classify with DINOv2

**Commit: "Phase 5: WBF ensemble submission"**

---

## PHASE 6: Retrain YOLO11m with Better Augmentation
**Expected: +2-4% from augmentation alone. Time: ~8h training.**

Current YOLO11m likely used default augmentation. Retrain on cv-train-1 (after YOLO26m finishes) with the enhanced settings from Phase 4.

**Commit: "Phase 6: YOLO11m v2 retrain with augmentation"**

---

## DO NOT PURSUE
- **YOLO26m:** At epoch 73, mAP50=0.890 vs YOLO11m's 0.945. Let it finish but don't expect it to beat YOLO11m on this dataset.
- **Florence-2, Grounding DINO:** Too large for 420MB / 300s constraints.
- **RT-DETRv4:** High effort, moderate reward. Only if everything else plateaus.

---

## SCORING MATH
Current: 0.5735
Phase 1 (TTA): 0.60-0.62
Phase 2 (SAHI): 0.63-0.67
Phase 3 (DINOv2 classify): 0.70-0.78
Phase 5 (ensemble): 0.72-0.80
Target: 0.75+
