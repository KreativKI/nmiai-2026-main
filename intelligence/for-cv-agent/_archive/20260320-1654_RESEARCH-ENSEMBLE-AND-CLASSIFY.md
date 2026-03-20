---
priority: CRITICAL
from: overseer
timestamp: 2026-03-20 05:30 CET
self-destruct: after incorporating into plan.md, delete
---

## Research Results: Ensemble + Classification Boost

Our score is 0.5735. Score = 0.7 * detection_mAP + 0.3 * classification_mAP.
Classification is likely our weak point (356 classes, 248 images). Here's how to fix it.

---

### 1. BIGGEST WIN: Crop-and-Classify with DINOv2 kNN

**Why:** We have 327 product reference images sitting unused. DINOv2 scores 70% on iNaturalist (10K categories) vs CLIP's 15%. Perfect for fine-grained grocery products.

**Pipeline:**
1. YOLO detects bounding boxes (detection component)
2. Crop each detected product from original image
3. Embed crop with DINOv2 ViT-S from timm 0.9.12 (pre-installed in sandbox!)
4. Compare against pre-computed embeddings of 327 reference images
5. Assign category_id of nearest reference image

**How to implement:**
- Use timm to load: `timm.create_model('vit_small_patch14_dinov2.lvd142m', pretrained=True, num_classes=0)`
- Pre-compute reference gallery embeddings (shape: [356, 384]), save as .npy file
- At inference: embed each crop, cosine similarity against gallery, argmax = category_id

**Model size:** DINOv2 ViT-S FP16 = ~42MB. Fits easily in 420MB budget.
**Expected impact:** +5-15% on classification mAP. This is the single biggest score boost available.

**Multi-crop reference averaging:** For each reference product, embed 8 crops (center + 4 corners + 3 augmented), average the embeddings. Stabilizes against lighting/angle variation.

---

### 2. Weighted Boxes Fusion (WBF) Ensemble

**ensemble-boxes 1.0.9 is pre-installed.** Use `weighted_boxes_fusion`.

**Key parameters (competition-proven):**
- `iou_thr=0.55` (from Kaggle Global Wheat 9th place)
- `skip_box_thr=0.001` (aggressive, keep all boxes)
- Normalize all box coords to [0,1] range before calling (CRITICAL - most common mistake)

**Score calibration:** Different architectures produce different confidence scales. Normalize with rank-based scaling before fusion:
```python
from scipy.stats import rankdata
normalized_scores = 0.5 * (rankdata(scores) / len(scores)) + 0.5
```

**Expected impact:** +1.5-2% detection mAP from diverse ensemble.

---

### 3. Test-Time Augmentation (TTA)

**Free +1-2% mAP, no retraining needed.**

Augmentations: horizontal flip + multi-scale (original + 130% size).
Run model on each augmented image, reverse augmentations on boxes, WBF-fuse.

**CRITICAL:** Reverse augmentations on boxes before fusion. Horizontal flip = mirror x coordinates.

For ultralytics YOLO: `model.predict(image, augment=True)` does this automatically.

---

### 4. Model Budget for 420MB (3 weight files max)

| Model | FP16 ONNX Size |
|-------|---------------|
| YOLO11m | ~20 MB |
| YOLO26m | ~20 MB (est) |
| RF-DETR Nano INT8 | ~92 MB |
| DINOv2 ViT-S FP16 | ~42 MB |
| Reference embeddings .npy | <1 MB |

**Best 3-file combo:** YOLO-best (20MB) + RF-DETR (92MB) + DINOv2 (42MB) = 154MB. Plenty of room.

Or: YOLO11m (20MB) + YOLO26m (20MB) + DINOv2 (42MB) = 82MB. Even more room.

**FP16 export:** `model.export(format="onnx", half=True)` -- less than 1% accuracy loss.

---

### 5. Updated run.py Architecture

```
run.py:
1. Load 2-3 detection ONNX models
2. For each image:
   a. Run each detection model (with TTA: original + hflip)
   b. WBF-fuse all detections
   c. Crop each fused detection from original image
   d. Embed crop with DINOv2
   e. kNN match against reference gallery -> category_id
   f. Output: {image_id, category_id, bbox, score}
```

This attacks both the 70% detection AND 30% classification components.

---

### Priority Order
1. **DINOv2 crop-and-classify** (biggest gain, build NOW)
2. **WBF ensemble** when 2+ detection models are ready
3. **TTA** (free improvement, add to run.py)
4. **FP16 export** all models to fit budget
