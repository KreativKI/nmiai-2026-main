# NorgesGruppen Object Detection — Plan

**Track:** CV | **Task:** Grocery Shelf Detection | **Weight:** 33.33%
**Last updated:** 2026-03-21 01:10 CET

## CRITICAL: Single Source of Truth
ALL CV work happens in this worktree (`/Volumes/devdrive/github_dev/nmiai-worktree-cv/agent-cv/`).

## Current State
- **Best submitted score:** 0.5756 (YOLO11m detection-only, submission #2)
- **Root cause of gap:** 248 images on 356 categories = extreme overfitting. Local 0.95 was fiction (val=train).
- **Submission ready for JC:** `submission_augmented.zip` (YOLO-only, prior retrained model)
- **GCP VM:** cv-train-1 (europe-west1-c, RUNNING)
  - Aggressive retrain: 348 train (208 real + 140 synthetic) / 40 val, 120 epochs, ~90 min remaining
  - Gemini generation: 64/350 categories done, running in background

## Battle Plan Status
| Phase | Status | Notes |
|-------|--------|-------|
| 0: Fix Evaluation | DONE | 80/20 split created. Category IDs verified (0-355, no off-by-one). |
| 1: Copy-Paste Augmentation | DONE (minimal) | 140 existing synthetic images integrated. Could generate more. |
| 2: Gemini as Training Data | IN PROGRESS | 64/350 categories generating. Will use as YOLO training data when done. |
| 3: Retrain Aggressive | RUNNING on GCP | YOLO11m, 120 epochs, mosaic=1.0, mixup=0.3, copy_paste=0.3, scale=0.5 |
| 4: Honest Eval + Submit | NEXT | When retrain finishes: honest eval, export ONNX, build ZIP, submit. |

## What's Been Proven (DO NOT REPEAT)
| Experiment | Result | Status |
|-----------|--------|--------|
| YOLO11m fine-tune (all 248 images, val=train) | mAP50=0.945 (FAKE, overfitting) | Done |
| YOLO11m leaderboard | 0.5756 | Current best |
| SAHI sliced inference | -0.039 vs baseline | HURTS, don't revisit |
| DINOv2 crop-and-classify | -0.039 vs baseline | HURTS, don't revisit |
| TTA (multi-scale + flip) | +0.002 | Negligible |
| Ensemble YOLO11m+YOLO26m | +0.000 | No gain |
| Retrain on 248+140 images (old augmentation) | Completed, not yet submitted | In submission_augmented.zip |

## Key Findings
- **Detection is NOT the bottleneck** (detection mAP ~0.82+ even on unseen data)
- **Classification IS the bottleneck** (YOLO memorizes 1-2 examples per category, fails on variation)
- Score = 0.7 * detection_mAP + 0.3 * classification_mAP
- Category IDs: 0-355, match between YOLO and COCO annotations (no off-by-one)
- Category 355 = "unknown_product"
- 54 categories have <= 2 training instances, 110 have < 10

## Next Actions (after retrain)
1. Download best.onnx from retrain
2. Run honest eval on proper val set (40 images the model hasn't seen)
3. Compare honest eval to leaderboard score to calibrate
4. If improved: build YOLO-only ZIP, run cv_pipeline.sh + canary, submit
5. If Gemini generation finished: incorporate as YOLO training data, retrain again

## Submission Log
| # | Time | ZIP | Score | Notes |
|---|------|-----|-------|-------|
| 1 | Fri 04:30 | submission_yolo11m_v1.zip | FAILED | argparse rejected unknown args |
| 2 | Fri 04:56 | submission_yolo11m_v2.zip | 0.5756 | YOLO11m only (current best) |
| 3 | Fri ~15:00 | submission_dinov2_enhanced_v2.zip | ? | Enhanced gallery, may have had .npz bug |
| 4 | READY | submission_augmented.zip | NOT YET | Old retrain, pipeline PASS, JC uploads manually |

## Critical Constraints
- BLOCKED IMPORTS: os, sys, subprocess, socket, pickle, yaml, etc. (instant ban)
- Max 420 MB weights, 3 weight files, 10 .py files, 300s timeout on L4 GPU
- 6 submissions/day (resets 01:00 CET), 2 concurrent max
- ALLOWED extensions: .py .json .yaml .yml .cfg .pt .pth .onnx .safetensors .npy
- ALL compute on GCP, never local Mac
