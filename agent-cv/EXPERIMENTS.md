# CV Agent Experiments Log

Persistent record across sessions. Add new experiments at the bottom. Never delete entries.

---

### Experiment 1: YOLO11m fine-tune baseline
**Date:** 2026-03-20 ~04:00 CET
**Approach:** A (YOLO11m -> ONNX)
**Change:** Fine-tuned YOLO11m on 248 images, imgsz=1280, batch=16, AdamW, 18+ epochs on GCP L4
**Hypothesis:** Fine-tuned YOLO11m should detect grocery products accurately
**Score before:** 0 (no submission)
**Score after:** 0.5735 (submission_yolo11m_v1.zip)
**Delta:** +0.5735
**Kept/Reverted:** Kept (baseline)
**Time spent:** ~4h (GCP training)
**Notes:** Training mAP50 reached 0.688. Detection works well but classification limited to YOLO's 357-class head.

### Experiment 2: YOLO11m + TTA (test-time augmentation)
**Date:** 2026-03-20 ~05:00 CET
**Approach:** A variant
**Change:** Added horizontal flip TTA, lowered conf threshold to 0.05
**Hypothesis:** TTA should catch products at different orientations
**Score before:** 0.5735
**Score after:** 0.5756 (submission_yolo11m_v3_tta.zip)
**Delta:** +0.0021
**Kept/Reverted:** Marginal improvement
**Time spent:** 1h
**Notes:** TTA barely helps. Detection is NOT the bottleneck.

### Experiment 3: Ensemble YOLO11m + YOLO26m (WBF)
**Date:** 2026-03-20 ~05:30 CET
**Approach:** Ensemble
**Change:** Weighted Box Fusion between YOLO11m and YOLO26m detections
**Hypothesis:** Two models should find products that one misses
**Score before:** 0.5756
**Score after:** 0.5756 (submission_ensemble_v1.zip)
**Delta:** 0
**Kept/Reverted:** No improvement
**Time spent:** 1h
**Notes:** More detection models don't help. Confirmed: classification IS the bottleneck.

### Experiment 4: DINOv2 Crop-and-Classify
**Date:** 2026-03-20 ~13:00 CET
**Approach:** B (YOLO detect + DINOv2 classify)
**Change:** Two-stage: YOLO11m detects bboxes, DINOv2 ViT-S embeds crops, kNN matches against 327 reference images
**Hypothesis:** DINOv2 gallery matching should produce better category IDs than YOLO's trained head
**Score before:** 0.5756 (YOLO-only best)
**Score after:** PENDING SUBMISSION
**Delta:** TBD
**Kept/Reverted:** TBD
**Time spent:** ~3h
**Notes:** Pre-submission toolchain all PASS. 114 predictions (vs 107 YOLO-only). Different category distribution: 32 unique cats (vs 45 YOLO), 15 new categories, 28 lost. Lower mean confidence (0.58 vs 0.77) due to detection*classification score blending. Submission ZIP: submission_dinov2_classify_v1.zip (143MB).
