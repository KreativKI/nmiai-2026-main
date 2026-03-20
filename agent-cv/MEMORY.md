# CV Agent Memory

## Current State
- **Training:** YOLO11m on GCP VM cv-train-1 (europe-west1-c, L4 GPU)
- **Score:** mAP50=0.688 at epoch ~18, still climbing
- **YOLO26m:** Queued to auto-start after YOLO11m finishes
- **run.py:** Fixed with --images flag, /tmp/ output path, 357 categories

## Rules (last read: 2026-03-20 01:00 CET)
- CLI: `python run.py --images /data/images/ --output /tmp/predictions.json`
- 5 submissions/day (resets 01:00 CET)
- 357 categories (IDs 0-356)
- BLOCKED: os, sys, subprocess, socket, urllib, http.client, gc, and many more
- 30+ teams banned for blocked imports

## Experiments

### Experiment 1: YOLO11m fine-tune (imgsz=1280, batch=16, AdamW)
**Date:** 2026-03-20
**Approach:** A (YOLO11m -> ONNX)
**Score progress:** mAP50: 0.016 -> 0.103 -> 0.220 -> 0.278 -> 0.332 -> 0.375 -> 0.416 -> 0.451 -> 0.505 -> 0.560 -> 0.577 -> 0.614 -> 0.611 -> 0.634 -> 0.641 -> 0.646 -> 0.667 -> 0.688
**Notes:** OOM warnings on dense batches but training continues. Batch 16 on L4 24GB is at the limit for imgsz=1280.

## GCP VM Details
- Name: cv-train-1
- Zone: europe-west1-c
- Type: g2-standard-8 (L4 GPU, 24GB VRAM)
- Training log: ~/cv-train/train.log
- Models dir: ~/cv-train/models/
- YOLO26m log: ~/cv-train/train_yolo26m.log

## Key Files
- solutions/run.py: ONNX inference with safe imports
- scripts/validate_submission.sh: Docker validation
- scripts/check_blocked_imports.py: Import safety checker
- Dockerfile: Sandbox mirror for local validation
