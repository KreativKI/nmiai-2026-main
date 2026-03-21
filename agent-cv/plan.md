# NorgesGruppen Object Detection — Plan

**Track:** CV | **Task:** Grocery Shelf Detection | **Weight:** 33.33%
**Last updated:** 2026-03-21 19:00 CET

## Current State
- **Leaderboard:** 0.6584 (YOLO11m maxdata, 854 images)
- **Previous:** 0.6475 (YOLO11m, 348 images)
- **Val-to-leaderboard ratio:** ~0.807 (val 0.816 gave 0.6584)
- **Submissions left today:** 4 of 6 (resets 01:00 CET)
- **Deadline:** Sunday 15:00 CET (~20 hours remaining)

## Scoring
Score = 0.7 * detection_mAP@0.5 + 0.3 * classification_mAP@0.5
- Detection recall: 93.9% (strong, near ceiling)
- Classification: 92.2% well-known, 37% rare (the bottleneck)

## Calibrated Scoring (predicted vs actual)

| # | Val mAP50 | Leaderboard | Ratio | What |
|---|-----------|-------------|-------|------|
| 2 | 0.95 (fake) | 0.5756 | - | Baseline, val=train |
| 4 | 0.767 | 0.6475 | 0.845 | Proper split + augmentation (348 imgs) |
| 5 | 0.816 | 0.6584 | 0.807 | Maxdata (854 imgs, ratio WORSE) |

---

## AUDIT FINDINGS (2026-03-21 19:00 CET)

### CRITICAL FIX 1: NMS Inconsistency (+0.01-0.03 potential)
`build_submission.sh` uses CLASS-AGNOSTIC NMS. `run_yolo_only.py` uses PER-CLASS NMS. On dense shelves (92 products/image), class-agnostic NMS suppresses valid detections of different products with overlapping boxes.
**Action:** Verify which NMS the 0.6584 submission used. Standardize all run.py files to per-class NMS. 15 min.

### CRITICAL FIX 2: Fine-tune, don't train from scratch
`retrain_with_gemini.py` loads `yolo11m.pt` (pretrained ImageNet) instead of our best existing weights. This throws away all learned grocery knowledge.
**Action:** Change retrain config:
- Start from `best_maxdata.pt` weights (not `yolo11m.pt`)
- 50 epochs (not 200)
- LR 0.0005 (not 0.001)
- copy_paste=0.0 (hurts rare-product classification)
- mosaic=0.5, mixup=0.1 (less aggressive)
**Impact:** Faster training (1.5h vs 4h), better classification preservation.

### CRITICAL FIX 3: Submit YOLO11l NOW (free potential +0.00-0.02)
`best_yolo11l.onnx` (98MB) exists, never submitted. Val 0.780 * 0.845 = estimated 0.659. Could tie or beat 0.6584 with zero additional work.
**Action:** Build ZIP with `run_yolo_only.py` + `best_yolo11l.onnx`, validate, submit. 15 min.

### EFFICIENCY FIX 4: Label only seen-once categories first
54 seen-once products get 1000% data increase from synthetic images. 62 somewhat-known get only 55% increase. Pareto: label seen-once first, skip rest unless time allows.

### RISK FIX 5: Standardize run.py
Three different conf thresholds across run.py files (0.15, 0.25, 0.28). Three different NMS strategies. Footgun waiting to happen.
**Action:** Make `run_yolo_only.py` the canonical run.py. Delete or rename the others. 10 min.

---

## Labeling Strategy (UPDATED)

### Primary: Gemini 2.5 Flash auto-detection
Use Gemini 2.5 Flash to find the target product in each shelf image and return bounding box coordinates. Butler integrating into labeling GUI.
- Gemini understands Norwegian product names (unlike Grounding DINO)
- Reference product photos provided alongside shelf image
- JC confirms/adjusts the predicted box (much faster than drawing from scratch)
- Brief sent to Butler: `intelligence/for-ops-agent/GEMINI-BBOX-DETECTION-BRIEF.md`

### Fallback: JC manual labeling
If Gemini auto-detect fails or returns low confidence, JC draws manually.
- batch_001: COMPLETE (100 images labeled, 90/100 quality)
- batch_002: READY (100 images downloaded)

### Second pass: YOLO auto-labels other shelf products
After target product is labeled, `yolo_second_pass.py` detects other products on the shelf (93% accurate on well-known). This prevents YOLO from learning to ignore correctly-detected products during training.

---

## Generation Status

### Pass 1: Front-facing shelf images (RUNNING)
| VM | Progress | ETA |
|----|----------|-----|
| cv-train-1 | 480/519 (92%) | ~19:15 CET |
| cv-train-4 | 275/275 COMPLETE | done |

### Pass 2: Varied conditions (RUNNING on cv-train-4)
Varied lighting, messy shelves, camera angles, distances. 55 categories x 3 = 165 images.

### Pass 3: Product angle variations (QUEUED on cv-train-1)
Non-frontal product orientations: turned sideways, angled, corner views, leaning. Starts when pass 1 finishes. 55 categories x 2 = 110 images.

### Total when complete: ~1070 images across 3 passes

---

## Top Confusions (from confusion analysis)
These are the product pairs the model mixes up most:
- 10x: Evergood Filtermalt (100) -> Kokmalt (304)
- 9x: Knekkebrод Godt for Deg (92) -> Urter&Havsalt (345)
- 8x: Egg Okologisk (105) -> Gardsegg (283)
- 6x: Bremykt Mykere 500G (351) -> Bremykt 250G (110)
- 6x: Supergranola (240) -> Granola Eple (47)
- 5x: Ali Original Kokmalt (160) -> Filtermalt (171)

Root cause: similar packaging, model can't read distinguishing text.

---

## Experiments Completed

| Experiment | Result | Keep/Reject |
|-----------|--------|-------------|
| YOLO11m maxdata (854 imgs) | 0.6584 LB | **CURRENT BEST** |
| Center-crop heuristic labels | val 0.790 (worse than 0.816) | REJECT |
| Color histogram reclassifier | -10 net (hurt) | REJECT |
| Grounding DINO auto-label | 40% on Norwegian products | REJECT |
| Gemini bbox in generation | 50% return, 30% usable | REJECT (for generation) |
| Gemini 2.5 Flash for detection | IN PROGRESS (Butler integrating) | TESTING |
| Conf sweep | optimal 0.28 (+0.001) | MARGINAL |
| IOU sweep | optimal 0.45 (~0.000) | NEGLIGIBLE |
| SAHI sliced inference | hurt score | REJECT |
| DINOv2 crop-and-classify | hurt score | REJECT |
| Ensemble YOLO11m+YOLO26m | +0.000 | REJECT |
| TTA | +0.002 | NEGLIGIBLE |

---

## Action Plan (audit-based, status as of 19:15 CET Saturday)

### IMMEDIATE — DONE
1. ~~Fix retrain config~~ DONE
2. ~~Verify NMS in 0.6584 submission~~ DONE (per-class confirmed)
3. ~~Build YOLO11l ZIP~~ Built, not submitting (JC: won't improve)
4. ~~Standardize run.py~~ DONE

### TONIGHT (19:00-01:00 CET)
5. ~~JC labels with Gemini 2.5 Flash auto-detect~~ ABANDONED (API too slow)
6. ~~Pass 3 angles generation~~ KILLED (freed GPU for training)
7. Round 1 retrain: RUNNING (100 JC-labeled + 211 real, 50 epochs, fine-tune)
8. Round 2 bootstrap: QUEUED (auto-label ~800 with round 1 model, retrain again)
9. NEW: Crop-based regeneration tested and confirmed working (for potential round 3)

### OVERNIGHT (01:00-09:00 CET)
10. Round 2 finishes, ZIP ready (~20:05 CET estimate)
11. If JC wakes up and labels more: round 3 with JC labels + crop-based regeneration

### SUNDAY MORNING (09:00-15:00 CET)
12. Feature freeze 09:00
13. Submit best model from round 1 or round 2 (whichever has better val)
14. Test conf/IOU variants on remaining slots if time
15. Repo public by 14:45
16. DEADLINE 15:00

---

## Scripts Ready
- `gemini_shelf_gen.py` (pass 1, RUNNING)
- `gemini_shelf_gen_v2.py` (pass 2 varied conditions, RUNNING)
- `gemini_shelf_gen_v3_angles.py` (pass 3 angles, QUEUED)
- `prepare_label_batches.py` (organize for JC)
- `yolo_second_pass.py` (auto-label other products)
- `retrain_with_gemini.py` (NEEDS CONFIG FIX per audit)
- `build_submission.sh` (NEEDS NMS FIX per audit)
- `conf_sweep.py`, `iou_sweep.py`, `category_analysis.py`
- `color_reclassifier.py` (tested, rejected)

## GCP VMs
| VM | Zone | Status |
|----|------|--------|
| cv-train-1 | europe-west1-c | GENERATING pass 1 (480/519), then pass 3 |
| cv-train-4 | europe-west3-a | GENERATING pass 2 (varied conditions) |
| ml-churn | europe-west1-b | ML agent |

## Validated ZIPs
- `submission_maxdata.zip` -- YOLO11m, 854 imgs, val 0.816, **LB 0.6584**
- `submission_yolo11l.zip` -- YOLO11l, 348 imgs, val 0.780, **UNTESTED (submit NOW)**
- `submission_aggressive_v2_final.zip` -- YOLO11m, 348 imgs, LB 0.6475

## What NOT to Do
- No DINOv2 at inference (proven: hurts)
- No Grounding DINO (fails on Norwegian)
- No SAHI (proven: hurts)
- No class-agnostic NMS (suppresses valid detections on dense shelves)
- No training from scratch (fine-tune from best weights)
- No copy-paste augmentation in retrain (hurts rare-product classification)
- No rotation augmentation (makes labels unreadable)
- Don't trust val scores alone. Use calibration ratio ~0.80-0.85.

## Critical Constraints
- BLOCKED IMPORTS: os, sys, subprocess, etc. = instant ban
- Max 420 MB weights, 3 weight files, 10 .py files, 300s timeout
- 6 submissions/day, resets 01:00 CET
- ALL compute on GCP, never local Mac
- Oslo = CET = UTC+1
