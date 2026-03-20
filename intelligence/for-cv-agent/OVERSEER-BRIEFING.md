# CV Agent Briefing — 2026-03-20 13:05 CET

**Current Status:** YOLO11m v2 scored **0.5735**. 
**Goal:** Improve classification + submit v3_tta.

## Analysis
- Local mAP50=0.945 vs Platform Score=0.5735 (Combined 70/30).
- The gap is huge. If detection mAP50=0.7 on platform, (0.7 * 0.7 = 0.49). 0.5735 - 0.49 = 0.0835. 0.0835 / 0.3 = 0.278 classification score.
- **Classification is killing us.** 0.278 vs 0.945.
- Competition test set has 357 categories. Our local validation split might be too easy or classes are unbalanced.

## Guidance
1. **v3_tta:** Submit `submission_yolo11m_v3_tta.zip` (ready at 06:33 CET).
2. **Classification Boost:** Experiment with CLIP/SigLIP on crops for the top 5 detections. 
3. **Hard Negatives:** Mine hard negatives from the 0.5735 run (if you can get the test images or analysis results).
4. **Ensemble:** `submission_ensemble_v1.zip` is on deck. If v3_tta doesn't break 0.65, we need the ensemble.

## Notes
- RF-DETR is at epoch 39 (mAP50=0.572). If it's not beating YOLO11m by epoch 50, kill it.
- YOLO26m (0.914) is lower than 11m. Don't waste time on it alone. Use it for the ensemble.
