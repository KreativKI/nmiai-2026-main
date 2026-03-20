# NorgesGruppen Object Detection — Plan

**Track:** CV | **Task:** Grocery Shelf Detection | **Weight:** 33.33%
**Last updated:** 2026-03-20 05:00 CET

## The Problem
Detect and classify grocery products on store shelves. 248 training images, 356 categories, COCO format. Score = 70% detection mAP + 30% classification mAP. Runs offline on L4 GPU in sandbox (ultralytics 8.1.0, onnxruntime-gpu 1.20.0).

## Current State
- **YOLO11m v2 SUBMITTED** at 04:56 CET. Score pending.
  - mAP50=0.945 (val), mAP50-95=0.727. ONNX 78MB.
  - v1 failed exit code 2 (argparse). v2 fixed with parse_known_args + --input alias.
- **YOLO26m training:** cv-train-1, epoch 73/100, mAP50=0.890. Below YOLO11m.
- **RF-DETR training:** cv-train-2, epoch 24/80, mAP50=0.425. Slow convergence, not competitive.

## Phased Work Plan

### Phase 1: Monitor Training + Score (NOW)
- Monitor YOLO26m on cv-train-1 (should finish in ~30 min)
- Monitor RF-DETR on cv-train-2 (will take ~1 hour more)
- Check leaderboard for v2 submission score
- **Commit:** status.json + MEMORY.md updates

### Phase 2: Export Best Alternative Model
- When YOLO26m finishes: export to ONNX, Docker-validate, prepare ZIP
- When RF-DETR finishes: export to ONNX, write run_rfdetr.py, Docker-validate
- Compare all three: YOLO11m vs YOLO26m vs RF-DETR
- **Commit:** export scripts + submission ZIPs

### Phase 3: Submit Best Model (requires JC)
- If YOLO26m or RF-DETR beats v2 score, prepare submission
- JC uploads manually
- **Commit:** status update

### Phase 4: Ensemble (if time permits)
- If YOLO11m + YOLO26m both produce decent predictions
- Average predictions from both models (ensemble-boxes library is in sandbox)
- Write ensemble run.py that loads both ONNX models
- Must fit in 420MB total (78MB + ~80MB = ~160MB, fits)
- **Commit:** ensemble code + submission ZIP

### Phase 5: TTA (Test-Time Augmentation)
- Add horizontal flip + multi-scale inference to run.py
- Free accuracy boost, no retraining needed
- Must stay under 300s timeout
- **Commit:** TTA-enhanced run.py

## GCP VMs
| VM | Zone | Purpose | Status |
|----|------|---------|--------|
| cv-train-1 | europe-west1-c | YOLO26m training | Running, epoch 73 |
| cv-train-2 | europe-west3-a | RF-DETR training | Running, epoch 24 |

**DELETE VMs when training done to avoid charges.**

## Submission Log
| # | Time | ZIP | Score | Notes |
|---|------|-----|-------|-------|
| 1 | 04:30 CET | submission_yolo11m_v1.zip | FAILED (exit 2) | argparse rejected unknown args |
| 2 | 04:56 CET | submission_yolo11m_v2.zip | PENDING | parse_known_args fix |

## Critical Constraints
- `--images` and `--input` both accepted (sandbox may use either)
- `parse_known_args()` to accept any extra sandbox flags
- No blocked imports (os, sys, subprocess, etc.)
- Max 420MB weights, 3 weight files, 10 .py files
- 5 submissions/day (resets 01:00 CET)
- Docker-validate EVERY submission (QC-LOOP-RULE)
