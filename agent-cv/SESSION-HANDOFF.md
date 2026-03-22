# CV Session Handoff — 2026-03-22 00:45 CET

## Leaderboard: 0.6584 | ~14 hours to deadline (Sun 15:00 CET)

## CRITICAL: R5 Training is RUNNING on cv-train-1
- **What:** YOLO11m fine-tuning from maxdata best weights (val 0.816)
- **Data:** 577 images (211 real + 366 JC-labeled Gemini shelf images)
- **Config:** batch=8, lr=0.0003, fliplr=0, degrees=0, hsv_s=0.3, patience=10, close_mosaic=10
- **Log:** `~/retrain_r5.log` on cv-train-1
- **ETA:** ~01:15 CET (50 epochs, patience may stop early)
- **Check:** `gcloud compute ssh cv-train-1 --zone=europe-west1-c --project=ai-nm26osl-1779 --command='grep "all " ~/retrain_r5.log | tail -5'`

## When R5 finishes:
1. Check val mAP50 (target: beat 0.816)
2. If improved: export ONNX, build ZIP with canonical `solutions/run.py`, validate with cv_pipeline.sh
3. Submit as first slot (6 available after 01:00 reset)
4. If NOT improved: investigate, consider more JC labels or config changes

## Key Files on GCP (cv-train-1, europe-west1-c)
- Best existing weights: `~/retrain/yolo11m_maxdata_200ep/weights/best.pt` (val 0.816)
- R5 training output: `~/retrain_r5/yolo11m_gemini/`
- JC labels: `~/gemini_labels/` (366 files)
- Generated images: `~/gemini_shelf_gen/` (616 images)
- Canonical run.py: `~/run_canonical.py`
- Retrain script: `~/scripts/retrain_with_gemini.py` (FIXED augmentation)
- Build script: `~/scripts/build_submission.sh`
- Validation: `~/shared/tools/cv_pipeline.sh`

## Key Files Local
- Plan: `agent-cv/plan.md` (fully updated with audit findings)
- Canonical run.py: `agent-cv/solutions/run.py` (RGB, *.jpeg glob, per-class NMS)
- Labeled batches: `agent-cv/labeled_complete/batch_001-004/` (390 labels total, 366 on VM)
- Pending batches: `agent-cv/label_batches/batch_005/ (100), batch_006/ (17)`

## Why Previous Rounds Failed (Root Cause)
- R1 (val 0.802): only 100 JC labels, bad augmentation (fliplr=0.5, degrees=5)
- R2 (val 0.795): center-crop fallback labels poisoned auto-labeled data
- R3 (killed): same poison, only 267 of 390 labels used (99 images on wrong VM)
- R4 (val 0.796): corrected augmentation but still only 267 labels (missing 99 fixed now)
- **R5 (RUNNING): ALL 366 labels, corrected augmentation, full dataset**

## Audit Findings Still TODO
1. Fix build_submission.sh: remove embedded run.py, copy canonical instead (BGR bug + MAX_DETECTIONS)
2. Build master_pipeline.sh (unified pipeline replacing 3 scripts)
3. Automated score comparison (score_log.json)
4. Label upload automation (label_uploader.sh)
5. First submission at 01:00: rebuild maxdata ZIP with fixed canonical run.py (tests BGR fix)

## GCP VMs
| VM | Zone | Status |
|----|------|--------|
| cv-train-1 | europe-west1-c | R5 TRAINING |
| cv-train-4 | europe-west3-a | Pass 3 generation (may be done) |
| ml-churn | europe-west1-b | ML agent |

## Submissions: 6 fresh at 01:00 CET
