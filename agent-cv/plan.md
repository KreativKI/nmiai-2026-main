# NorgesGruppen Object Detection — Plan

**Track:** CV | **Task:** Grocery Shelf Detection | **Weight:** 33.33%
**Last updated:** 2026-03-20 18:40 CET

## CRITICAL: Single Source of Truth
ALL CV work happens in this worktree (`/Volumes/devdrive/github_dev/nmiai-worktree-cv/agent-cv/`).
The main repo (`nmiai-2026-main/agent-cv/`) is READ-ONLY reference for files created in earlier sessions.
Never create new work in the main repo. Always merge main -> agent-cv first to sync.

## Current State
- **Best submitted score:** 0.5756 (YOLO11m detection-only)
- **Best local pipeline:** YOLO11m detect + DINOv2 classify + enhanced gallery (355/356 cats) + SAHI
- **Submission ZIP ready:** submission.zip (143 MB), validator PASS
- **GCP VMs:** cv-train-1 and cv-train-2 IDLE (training complete, delete when done)

## What's Been Done (DO NOT REPEAT)
| Experiment | Result | Status |
|-----------|--------|--------|
| YOLO11m fine-tune (imgsz=1280, 100 epochs, GCP) | mAP50=0.945 | Done, best.onnx ready |
| YOLO26m fine-tune (GCP) | mAP50=0.890, lower than YOLO11m | Done, not used |
| RF-DETR (GCP) | mAP50=0.572, not competitive | Done, not used |
| Ensemble YOLO11m+YOLO26m | +0.000 over YOLO11m alone | Tried, no gain |
| TTA (multi-scale + flip) | +0.002 | Marginal, detection saturated |
| DINOv2 crop-and-classify (326 cat gallery) | Built, .npz bug blocked submission | Fixed now |
| Enhanced gallery (355/356 cats, studio+shelf blend) | Built on GCP | Applied, in current ZIP |
| Gemini synthetic photos (34 uncovered categories) | 68 images generated | Available, not yet in gallery |
| Copy-paste augmentation research | +6.9 mAP in low-data scenarios | Script exists, not run with latest data |
| SAHI sliced inference | +60% detections, +55% unique categories | Applied, in current ZIP |

## Proven Key Findings
- **Detection is NOT the bottleneck** (mAP50=0.945, TTA/ensemble give negligible gains)
- **Classification IS the bottleneck** (DINOv2 + reference images is the path)
- Score = 0.7 * detection_mAP + 0.3 * classification_mAP

## Priority Actions (in order)

### Phase 1: Submit current best [READY]
- submission.zip has: YOLO11m + DINOv2 + enhanced gallery (355 cats) + SAHI
- ZIP validator PASS. Docker validated.
- JC uploads when ready.

### Phase 2: Build 3-source final gallery (Gemini + studio + shelf)
- `scripts/build_final_gallery.py` exists (3-source blend)
- 68 Gemini synthetic photos already generated
- Need to run the builder to create gallery with all 3 sources blended
- Expected: better embeddings for the 34 previously uncovered categories
- Requires: running on GCP (or local Mac for gallery build only, no training)

### Phase 3: Improve classification confidence scoring
- Current: `combined_score = sqrt(det_score * max(cls_sim, 0.01))`
- Test alternatives: weighted average, softmax temperature, top-K voting
- Code-only change, no retraining

### Phase 4: Copy-paste augmentation + retrain (GCP)
- Script exists, research shows +6.9 mAP
- Generate 250-500 synthetic images with COCO annotations
- Retrain YOLO11m on combined real+synthetic dataset
- Requires GCP VM

### Phase 5: Train YOLO11l (bigger backbone, GCP)
- 25.3M params vs 20.1M (YOLO11m)
- May improve both detection and classification from YOLO head
- Requires GCP VM

## GCP VMs (DELETE WHEN DONE)
| VM | Zone | Status | Action Needed |
|---|---|---|---|
| cv-train-1 | europe-west1-c | IDLE | Has trained weights + enhanced gallery. Delete after downloading. |
| cv-train-2 | europe-west3-a | IDLE | Has RF-DETR (not competitive). Delete immediately. |

## Submission Log
| # | Time | ZIP | Score | Notes |
|---|------|-----|-------|-------|
| 1 | 04:30 CET | submission_yolo11m_v1.zip | FAILED (exit 2) | argparse rejected unknown args |
| 2 | 04:56 CET | submission_yolo11m_v2.zip | 0.5756 | YOLO11m only |
| 3 | ~15:00 CET | submission_dinov2_enhanced_v2.zip | SUBMITTED (score?) | Enhanced gallery 355 cats, may have .npz bug |
| 4 | PENDING | submission.zip | NOT YET | Enhanced gallery + SAHI + .npz fix |

## Critical Constraints
- `--images` and `--input` both accepted (parse_known_args)
- No blocked imports (os, sys, subprocess, etc.)
- Max 420 MB weights, 3 weight files, 10 .py files
- 6 submissions/day (resets 01:00 CET), 2 concurrent max
- ALLOWED extensions: .py .json .yaml .yml .cfg .pt .pth .onnx .safetensors .npy
- Docker-validate EVERY submission before upload
