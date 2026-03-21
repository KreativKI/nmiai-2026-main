# CV Session Handoff — 2026-03-21 05:40 CET

## Leaderboard: 0.6475 | Best Val: 0.816

## 3 Validated ZIPs Ready (pipeline + canary PASS)
1. `submission_maxdata.zip` -- YOLO11m, 854 images, val 0.816 (SUBMIT FIRST)
2. `submission_yolo11l.zip` -- YOLO11l, 348 images, val 0.780
3. `submission_aggressive_v2_final.zip` -- YOLO11m, 348 images, val 0.767, leaderboard 0.6475

## GCP VMs (all training complete)
- cv-train-1: europe-west1-c (maxdata DONE, Gemini gen may still be running)
- cv-train-3: europe-west1-b (YOLO11l DONE)
- cv-train-4: europe-west3-a (YOLO26m DONE, 0.485, skip)

DELETE VMs when no longer needed to save credits.

## What Worked
- Proper 80/20 train/val split eliminated fake local scores
- Aggressive augmentation (mosaic=1.0, mixup=0.3, copy_paste=0.3, scale=0.5)
- More training data: 854 images (3.4x original) produced val 0.816 vs 0.767 with 348

## Next Moves If Needed
- Confidence threshold sweep (0.10, 0.12, 0.15, 0.20, 0.25) on best model
- Even more synthetic data (Gemini with shelf backgrounds, not white)
- Ensemble YOLO11m + YOLO11l (WBF or NMS merge)
- Train on maxdata with YOLO11l backbone (bigger model + more data)
