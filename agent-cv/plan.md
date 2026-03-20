# NorgesGruppen Object Detection — Plan

**Track:** CV | **Task:** Grocery Shelf Detection | **Weight:** 33.33%
**Last updated:** 2026-03-19 22:55 CET

## The Problem
Detect and classify grocery products on store shelves. 248 training images, 356 categories, COCO format. Score = 70% detection mAP + 30% classification mAP. Runs offline on L4 GPU in sandbox (ultralytics 8.1.0, onnxruntime-gpu 1.20.0).

## READ FIRST: intelligence/for-cv-agent/SOTA-UPDATE-2026.md

## Approach A (Primary): YOLO26 Fine-tune → ONNX Export

**Why YOLO26 over YOLOv8:** Released Jan 2026. NMS-free inference, Small-Target-Aware Label Assignment (STAL) — critical for dense shelf scenes with overlapping products. Better accuracy than YOLOv8/v11/v12/v13 on COCO benchmarks.

1. Install latest ultralytics locally (NOT 8.1.0)
2. Fine-tune YOLO26m on NorgesGruppen COCO dataset (nc=357)
3. Heavy augmentation: mosaic, mixup, scale jitter (NO vertical flip)
4. Export to ONNX (opset ≤ 20, FP16 quantization)
5. Write run.py using onnxruntime with CUDAExecutionProvider
6. **Time:** 3-4 hours (including export + testing)
7. **Expected:** 55-75% combined mAP

## Approach B (Alternative): RF-DETR Fine-tune → ONNX

**Why consider:** DINOv2 backbone excels at few-shot transfer learning. We have only 248 images across 356 categories — this is textbook few-shot. May converge faster and score higher than YOLO.

1. Install RF-DETR from Roboflow
2. Fine-tune on NorgesGruppen data
3. Export to ONNX
4. **Time:** 3-4 hours
5. **Expected:** 60-80% combined mAP (potentially better than YOLO26 in few-shot)

## Approach C (Baseline — SHIP FIRST): Detection-Only with Pretrained YOLO

1. Use pretrained YOLO (COCO weights) — detects generic objects
2. Set category_id=0 for all predictions (skip classification)
3. Max score: 70% (detection component only)
4. **Time:** 1 hour
5. **Expected:** 30-45% detection mAP × 0.7 = 21-32% total

## Approach D (Classification Boost): Detect + CLIP/SigLIP Classify

If detection is good but classification is weak:
1. Use YOLO26 for detection (find bounding boxes)
2. Crop detected products
3. Match crops against 327 product reference images using CLIP/SigLIP embeddings
4. No training needed for classification — reference images ARE the classifier
5. **Time:** 2-3 hours on top of Approach A
6. **Expected:** +10-15% on classification mAP

## Local Validation (MANDATORY before every submission)

Before uploading ANY zip, validate it in a Docker container that mirrors the competition sandbox. Create a Dockerfile matching the sandbox environment (Python 3.11, exact package versions, no network). Then:

1. Build: `docker build -t ng-sandbox .`
2. Unzip your submission into a test directory
3. Run: `docker run --rm -v ./test_images:/data/images -v ./output:/output ng-sandbox python run.py --input /data/images --output /output/predictions.json`
4. Verify: exit code 0, predictions.json exists, valid JSON array, correct fields

This catches blocked imports, version mismatches, and format errors BEFORE burning a submission slot. No excuses — every submission must pass local validation first.

## Submission Strategy (3/day limit!)
1. **Sub 1:** Baseline (Approach C) — verify pipeline works
2. **Sub 2:** YOLO26 or RF-DETR fine-tuned — real score
3. **Sub 3:** Improved model with classification boost

## Critical Constraints
- `os`, `subprocess`, `pickle`, `yaml` BLOCKED — use `pathlib` + `json`
- Pin ONNX opset ≤ 20
- Max 420MB weights, max 3 weight files, max 10 .py files
- run.py at ZIP root (most common submission error)
- FP16 quantization recommended (smaller + faster on L4)

## Data
- Download from competition site (login required):
  - NM_NGD_coco_dataset.zip (~864 MB) — training images + annotations
  - NM_NGD_product_images.zip (~60 MB) — reference photos per product
