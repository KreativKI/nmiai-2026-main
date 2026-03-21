# NorgesGruppen Object Detection — Plan

**Track:** CV | **Task:** Grocery Shelf Detection | **Weight:** 33.33%
**Last updated:** 2026-03-22 00:15 CET

## Current State
- **Leaderboard:** 0.6584 (YOLO11m maxdata, 854 images)
- **Val-to-leaderboard ratio:** ~0.807 (val 0.816 gave 0.6584)
- **Submissions:** 6 fresh (reset at 01:00 CET)
- **Deadline:** Sunday 15:00 CET (~15 hours remaining)
- **JC-labeled images:** 390 (4 batches completed)
- **Clean training:** RUNNING on cv-train-1 (478 images, corrected config)

## Scoring
Score = 0.7 * detection_mAP@0.5 + 0.3 * classification_mAP@0.5
- Detection recall: 93.9% (near ceiling)
- Classification: 92.2% well-known, 37% rare (the bottleneck)

## Calibrated Scoring

| # | Val mAP50 | Leaderboard | Ratio | What |
|---|-----------|-------------|-------|------|
| 2 | 0.95 (fake) | 0.5756 | - | Baseline, val=train |
| 4 | 0.767 | 0.6475 | 0.845 | Proper split + augmentation (348 imgs) |
| 5 | 0.816 | 0.6584 | 0.807 | Maxdata (854 imgs) |
| 6 | 0.802 | not submitted | - | Round 1 (100 JC + 211 real, bad augmentation) |
| 7 | 0.795 | not submitted | - | Round 2 bootstrap (auto-labels + center-crop poison) |

---

## ROOT CAUSE ANALYSIS (Audit 2, 2026-03-22 00:00 CET)

### Why scores DECLINED from 0.816 to 0.795:

**A. Center-crop fallback labels poisoned training.**
When YOLO couldn't find the target product in auto-labeled images, scripts inserted `{cat_id} 0.5 0.5 0.4 0.4` (fake center box). This teaches the model products are always centered at 40% of frame. On real shelves, this is pure noise.
**Status:** FIXED. Removed. Clean training uses only JC labels, no auto-labels.

**B. Synthetic:real ratio was uncontrolled (4.5:1).**
Model saw 4.5x more Gemini images than real images. Learned Gemini's shelf style instead of real shelves.
**Status:** FIXED. Current training: 267 synthetic + 211 real = 1.3:1 ratio.

**C. Augmentation was wrong for fine-tuning.**
- `fliplr=0.5`: flips text, kills classification (Kokmalt vs Filtermalt)
- `degrees=5`: rotates text, makes labels unreadable
- `hsv_s=0.7`: distorts brand colors
- `batch=4`: noisy gradients, half GPU capacity
**Status:** FIXED. New config: fliplr=0, degrees=0, hsv_s=0.3, batch=8, patience=10.

**D. BGR bug in build_submission.sh.**
The embedded run.py feeds BGR to an RGB-trained model. Canonical `solutions/run.py` converts correctly. Silent 1-3% mAP loss if the wrong run.py was shipped.
**Status:** TODO. Fix priority 1.
**NOTE (from audit review):** Verify whether the 0.6584 LB submission was built via build_submission.sh (BGR bug present) or assembled manually with canonical run.py (no bug). If BGR bug was in the 0.6584 submission, re-submitting maxdata weights with fixed run.py is a FREE score gain.

**E. MAX_DETECTIONS mismatch.**
`build_submission.sh` uses 300. `solutions/run.py` uses 500. On shelves with 92 products/image, 300 may truncate.
**Status:** TODO. Fix priority 1.

**F. solutions/run.py only globs *.jpg.**
Line 112 misses .jpeg and .png files. The embedded run.py handles all three. If test images include other extensions, the canonical run.py silently skips them.
**Status:** TODO. Fix in priority 1.

---

## AUTOMATION PLAN (what to build next)

### Priority 1: Fix build_submission.sh (15 min)
- Remove embedded run.py, copy canonical `solutions/run.py` instead
- Fixes BGR bug and MAX_DETECTIONS mismatch
- Every ZIP gets the correct, tested run.py

### Priority 2: Create master_pipeline.sh (45 min)
Replaces: `gcp_full_pipeline.sh`, `bootstrap_round2.sh`, `round3_199labels.sh`
One script with parameters:
```
master_pipeline.sh --round N --base-weights PATH --jc-labels DIR --output DIR
```
Steps:
1. Build dataset (real + JC-labeled, NO auto-labels, NO center-crop)
2. Retrain (fine-tune, corrected augmentation)
3. Read val mAP from results.csv, compare to score_log.json
4. If improved: export ONNX, build ZIP (using canonical run.py), validate
5. If NOT improved: log regression, do NOT build ZIP
6. Write pipeline_status.json for local_orchestrator.sh

### Priority 3: Automated score comparison (20 min)
- Create `score_log.json` with all known results
- After each training: parse val mAP from YOLO's results.csv
- Compare to previous best, only build ZIP if improved
- Append every result (good or bad) to the log

### Priority 4: Label upload automation (30 min)
- `label_uploader.sh` runs on Mac
- Polls `labeled_complete/` for new labels every 60s
- SCPs new labels to GCP VM
- Triggers master_pipeline.sh on the VM
- No human relay between Butler and CV agent

### Priority 5: VM health monitoring (20 min)
- Add to local_orchestrator.sh poll loop
- Check GPU utilization via nvidia-smi
- Alert if training process dies
- Alert if SSH fails 3x in a row

### Priority 6: Generation consolidation (30 min, LOW)
- Merge 3 generation scripts into one with `--pass` flag
- Only if planning more generation rounds

---

## TRAINING RUNS LOG

| Round | Train Images | Real | JC-labeled | Auto-labeled | Config | Val mAP50 | Notes |
|-------|-------------|------|------------|-------------|--------|-----------|-------|
| maxdata | 854 | 211 | 0 | 643 (copy-paste+gemini-whitebg) | from scratch, 200ep | **0.816** | Current best |
| R1 | 311 | 211 | 100 | 0 | fine-tune, bad augment | 0.802 | fliplr/degrees hurt |
| R2 bootstrap | ~1100 | 211 | 100 | ~800 (center-crop fallback) | fine-tune from R1 | 0.795 | center-crop poisoned |
| R3 (killed) | 728 | 211 | 366 | ~150 (center-crop fallback) | fine-tune from R2 | killed | same poison |
| **R4 CLEAN** | **478** | **211** | **267** | **0** | **fine-tune, FIXED augment** | **RUNNING** | No poison, correct config |

---

## Action Plan (next 15 hours)

### NOW (00:15-01:00 CET)
1. R4 clean training finishes (~00:45 CET)
2. Fix build_submission.sh (BGR bug, MAX_DETECTIONS, use canonical run.py)
3. Fix solutions/run.py to also glob *.jpeg and *.png (not just *.jpg)
4. Investigate: are all 390 JC labels being used? R4 only has 267 Gemini -- where are the other 123?
5. Build ZIP with canonical run.py
6. Compare val mAP to 0.816

### EARLY MORNING (01:00-09:00 CET)
7. FIRST SUBMISSION: Re-submit maxdata weights through fixed build_submission.sh (tests BGR fix, zero training risk)
8. If R4 > 0.816: submit R4 as second submission
9. If R4 < 0.816: investigate, add remaining JC-labeled data (batches 005-006), retrain
7. Build master_pipeline.sh + score comparison
8. Build label_uploader.sh for autonomous labeling loop
9. If JC labels more batches: auto-upload + retrain

### SUNDAY MORNING (09:00-15:00 CET)
10. Feature freeze 09:00
11. Submit best model
12. Test conf threshold variants on remaining slots
13. Repo public by 14:45
14. DEADLINE 15:00

---

## Top Confusions (from confusion analysis)
- 10x: Evergood Filtermalt (100) -> Kokmalt (304)
- 9x: Knekkebrод Godt for Deg (92) -> Urter&Havsalt (345)
- 8x: Egg Okologisk (105) -> Gardsegg (283)
- 6x: Bremykt Mykere 500G (351) -> Bremykt 250G (110)
- 6x: Supergranola (240) -> Granola Eple (47)
Root cause: similar packaging, model can't read distinguishing text.
Fix: fliplr=0 and degrees=0 preserves text features.

---

## Experiments Completed

| Experiment | Result | Status |
|-----------|--------|--------|
| YOLO11m maxdata (854 imgs) | LB 0.6584 | **CURRENT BEST** |
| R4 clean (478 imgs, fixed augment) | RUNNING | Pending |
| Center-crop labels | val 0.790 (worse) | REJECT |
| Auto-label bootstrap | val 0.795 (worse) | REJECT (center-crop poison) |
| Color histogram reclassifier | -10 net | REJECT |
| Grounding DINO auto-label | 40% accuracy | REJECT |
| Gemini 2.5 Flash bbox | Too slow for batch | REJECT |
| Conf sweep | +0.001 | MARGINAL |
| IOU sweep | ~0.000 | NEGLIGIBLE |
| SAHI | hurt | REJECT |
| DINOv2 classify | hurt | REJECT |
| Ensemble YOLO11m+26m | +0.000 | REJECT |
| TTA | +0.002 | NEGLIGIBLE |
| Crop-based regeneration | works (tested 1 image) | AVAILABLE |

---

## Scripts

### Active
- `retrain_with_gemini.py` -- FIXED augmentation config
- `solutions/run.py` -- canonical, per-class NMS, RGB, conf=0.25
- `gcp_full_pipeline.sh` -- current pipeline (to be replaced by master_pipeline.sh)
- `local_orchestrator.sh` -- polls GCP, downloads ZIP
- `gen_watcher.sh` -- monitors generation

### To Build
- `master_pipeline.sh` -- unified pipeline replacing 3 scripts
- `score_log.json` -- append-only results tracker
- `label_uploader.sh` -- auto-detect + upload labels to GCP

### To Fix
- `build_submission.sh` -- remove embedded run.py, use canonical

### Archived
- `bootstrap_round2.sh` -- replaced by master_pipeline.sh
- `round3_199labels.sh` -- replaced by master_pipeline.sh
- `solutions/run_DEPRECATED_dinov2.py` -- deprecated
- `color_reclassifier.py` -- tested, rejected

## GCP VMs
| VM | Zone | Status |
|----|------|--------|
| cv-train-1 | europe-west1-c | TRAINING R4 clean |
| cv-train-4 | europe-west3-a | Pass 3 generation (angles) |
| ml-churn | europe-west1-b | ML agent |

## What NOT to Do
- No auto-labels with center-crop fallback (proven: poisons training)
- No uncontrolled synthetic:real ratio (cap at 2:1)
- No fliplr or rotation (destroys text features for classification)
- No DINOv2, SAHI, Grounding DINO at inference (all proven: hurt)
- No class-agnostic NMS (suppresses valid detections)
- No embedded run.py in build scripts (use canonical solutions/run.py)
- Don't trust val scores alone. Use calibration ratio ~0.80-0.85.

## Critical Constraints
- BLOCKED IMPORTS: os, sys, subprocess, etc. = instant ban
- Max 420 MB weights, 3 weight files, 10 .py files, 300s timeout
- 6 submissions/day, resets 01:00 CET
- ALL compute on GCP, never local Mac
- Oslo = CET = UTC+1
