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

## Next Actions (execute in order)

### Action 1: Delete cv-train-2 VM [NOW, saves money]
- RF-DETR was not competitive (0.572). VM is idle, burning credits.
- `gcloud compute instances delete cv-train-2 --zone=europe-west3-a --project=ai-nm26osl-1779`

### Action 2: Improve classification scoring [code-only, local]
- Current: `combined_score = sqrt(det_score * max(cls_sim, 0.01))`
- Test A: top-K weighted voting (use top 3 gallery matches, not just best)
- Test B: softmax temperature on DINOv2 similarities before picking class
- Test C: use YOLO class as tiebreaker when DINOv2 confidence is low
- Measure: count of unique correct-looking category assignments on test images
- Docker validate each variant. Rebuild ZIP for best.

### Action 3: Build 3-source final gallery on cv-train-1 [GCP]
- `scripts/build_final_gallery.py` exists (studio 60% + shelf 20% + Gemini 20%)
- 68 Gemini synthetic photos already on local disk
- Upload Gemini photos to cv-train-1, run builder, download gallery.npy
- Expected: better embeddings for 34 categories that only had shelf crops
- Rebuild ZIP + Docker validate

### Action 4: Copy-paste augmentation + retrain YOLO11m [GCP, cv-train-1]
- Research shows +6.9 mAP in low-data scenarios
- Generate 250-500 synthetic images with COCO annotations
- Retrain YOLO11m on combined dataset (248 real + 500 synthetic)
- Export new best.onnx, rebuild full pipeline ZIP

### Action 5: Train YOLO11l bigger backbone [GCP, cv-train-1]
- 25.3M params vs 20.1M. Same pipeline as YOLO11m.
- Only if time remains and Action 4 didn't fill the schedule

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
