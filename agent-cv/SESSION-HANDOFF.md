# CV Session Handoff — 2026-03-22 15:00 CET (COMPETITION END)

## Final Score: 0.8783 (public leaderboard)

## Score Progression
| Time | Score | What changed |
|------|-------|-------------|
| ~01:00 | 0.6584 | YOLO11m only (maxdata weights, val 0.816) |
| ~12:00 | 0.8293 | + DINOv2 ViT-S kNN reclassification (gallery 9,949 crops) |
| ~13:00 | 0.8521 | + PCA whitening 320d, k=10, distance²-weighted voting |
| ~14:06 | 0.8783 | + LinearSVC replacing kNN, conf=0.15, IoU=0.6 |
| ~14:35 | 0.8783 | Pre-computed SVC (same score, 53s faster: 146s vs 199s) |
| ~14:58 | FAILED | Multiscale tiling + WBF (exit code 1, fixed but too late) |

## Submissions Used: 5 of 6
1. submission_twostage.zip → 0.8293 (DINOv2 kNN, gallery_rich)
2. submission_pca.zip → 0.8521 (PCA whitening, k=10, dist²)
3. submission_svc.zip → 0.8783 (LinearSVC, conf=0.15, IoU=0.6)
4. submission_pretrained_clean.zip → 0.8783 (pre-computed SVC, 146s)
5. submission_multiscale_clean.zip → FAILED (ONNX fixed input 1280, tried 1920)

## What Worked
- Two-stage pipeline (YOLO detect + DINOv2 classify) was the single biggest gain (+0.1709)
- PCA whitening removed noisy DINOv2 dimensions (+0.0228)
- LinearSVC learned proper decision boundaries vs kNN voting (+0.0262)
- Validated every change on eval before submitting (avoided regressions)
- Boris workflow caught real bugs (post-DINOv2 NMS risk, negative hash, dummy crops)
- PMM competitor team audit identified LinearSVC and PCA whitening

## What Failed / Was Rejected (validated on eval)
- Combined gallery (studio photos): ZERO improvement
- Crop padding 10%: HURT (0.8050 vs 0.8340)
- Centroid classifier: HURT (0.7550 vs 0.8340)
- TTA: negligible (+0.002)
- SAHI: hurt
- Ensemble YOLO11m+26m: +0.000
- Multiscale YOLO (1920): crashed (fixed input shape), fixed with tiling but too late
- R5 training (YOLO retrain with JC labels): val 0.802 < 0.816 baseline

## What We Never Got To
- Full 22,731-crop SVC training (GCP SSH overloaded)
- DINOv2 ViT-B (larger encoder, 768d embeddings)
- Per-class confidence calibration
- Soft-NMS
- Multi-scale tiling (fixed too late)
- Query-time augmentation (embed multiple augmented versions)

## Key Decisions & Timing
- Spent first ~2h on R5 training (waiting, not productive)
- Competitor analysis at ~10:00 identified two-stage approach
- DINOv2 was previously marked as "REJECT" in plan but had never been properly tested (failed due to .npz packaging, not accuracy)
- Gallery evaluation showed combined vs rich gallery = identical, saved a wasted submission
- PCA hyperopt grid search found optimal k=10, PCA=320, dist² in one run
- LinearSVC idea came from PMM audit team role-play

## Architecture (final)
```
YOLO11m (ONNX, 78MB)
  → detect boxes (conf=0.15, NMS IoU=0.6)
  → crop each detection from original image
DINOv2 ViT-S (ONNX, 84MB)
  → embed crops (batched, 16 at a time)
  → PCA whiten (384→320 dims, computed at runtime from gallery)
LinearSVC (pre-computed weights in classifier_params.json, 4.7MB)
  → classify: decision = X @ coef.T + intercept
  → confidence: sigmoid(max_decision)
Output score = det_conf * cls_confidence
```

## Files
- Best submission code: solutions/run_svc.py (runtime SVC) or solutions/run_pretrained_clean.py (pre-computed)
- Gallery builder: scripts/build_rich_gallery.py
- PCA hyperopt: scripts/eval_knn_hyperopt.py
- SVC precompute: scripts/precompute_svc.py
- All eval scripts: scripts/eval_*.py

## GCP VMs (STOP THESE TO SAVE MONEY)
| VM | Zone | Action |
|----|------|--------|
| cv-train-1 | europe-west1-c | STOP |
| cv-train-4 | europe-west3-a | STOP |
