# CV Track — 2026 SOTA Update

**Date:** 2026-03-19 22:45 CET
**From:** Gunnar
**Priority:** READ BEFORE CHOOSING YOUR MODEL

---

## Stop. Don't default to YOLOv8.

The sandbox has ultralytics 8.1.0 pre-installed, but that doesn't mean you should train with it. You can train with ANY model and export to ONNX for sandbox inference (onnxruntime-gpu 1.20.0 with CUDAExecutionProvider is pre-installed).

## What's new in 2026

### YOLO26 (Released January 2026) ⭐
- **Paper:** arxiv.org/abs/2601.12882 (4 days ago: arxiv.org/abs/2509.25164)
- **Key advances:** NMS-free inference, ProgLoss, Small-Target-Aware Label Assignment (STAL)
- **Why it matters for us:** STAL improves detection of small/partially occluded products on dense shelves. NMS-free = cleaner predictions on overlapping products.
- **Install:** `pip install ultralytics` (latest version, NOT 8.1.0)
- **Train locally, export to ONNX (opset ≤ 20), submit ONNX weights**
- **Benchmark:** Better accuracy-latency profile than YOLOv8/v11/v12/v13 on COCO

### RF-DETR (Roboflow, 2025-2026)
- **Architecture:** DINOv2 backbone + transformer decoder
- **Why it matters for us:** "Measurable advantages in convergence speed and final accuracy" for custom domains with limited training data. We have 248 images and 356 categories — this is exactly the few-shot transfer learning scenario RF-DETR excels at.
- **Trade-off:** Slightly slower inference than YOLO26, but accuracy may be higher
- **Export to ONNX for sandbox**

### Florence-2 / Grounding DINO 2 (Zero-shot/few-shot)
- Can use our product reference images (327 products, multi-angle) as visual prompts
- Zero-shot detection = no training needed for new categories
- Risk: may be too large for 420MB weight limit. Check after quantization.

### Two-stage: Detect + CLIP Classify
- Use YOLO26 for detection (find all products on shelf)
- Use CLIP/SigLIP embeddings to match detected crops against reference images
- Decouples detection from classification — handles the 356-category long-tail problem
- Reference images become your classification "training data" without actual training

## Recommended Exploration Order
1. **YOLO26 fine-tune** → ONNX export → test locally → submit
2. **RF-DETR fine-tune** → ONNX export → compare with YOLO26
3. **YOLO26 detect + CLIP classify** (if classification score is weak)
4. **Florence-2 zero-shot** (experimental, check weight size)

## Constraint Reminder
- Sandbox: Python 3.11, ultralytics 8.1.0, onnxruntime-gpu 1.20.0
- Train with latest locally, export ONNX with opset ≤ 20
- Max 420MB weights, max 3 weight files
- 3 submissions/day — don't waste them on untested approaches
