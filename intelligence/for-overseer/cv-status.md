## CV Status — Overnight Report #2
**Timestamp:** 2026-03-21 03:30 CET

**LEADERBOARD: 0.6475** (confirmed from YOLO11m submission)

**NEW RECORD: Val mAP50 0.811** (YOLO11m maxdata, epoch 118/200, still training!)
The 854-image dataset (3.4x original) is producing significantly better generalization.

**Validated ZIPs ready:**
A. `submission_yolo11l.zip` -- YOLO11l, val 0.780, pipeline+canary PASS
B. `submission_aggressive_v2_final.zip` -- YOLO11m, val 0.767, leaderboard 0.6475

**Training:**
| VM | Model | Status | Best Val mAP50 |
|----|-------|--------|----------------|
| cv-train-1 | YOLO11m maxdata (854 imgs, 200ep) | Epoch 122/200 | **0.811** |
| cv-train-3 | YOLO11l | DONE | 0.780 |
| cv-train-4 | YOLO26m | DONE | 0.485 (not competitive) |

**Submission priority for JC:**
1. Wait for maxdata model to finish (~04:30 CET), build ZIP, validate -- this is the best model
2. Submit YOLO11l as backup (already validated)
3. Skip YOLO26m (0.485 is too low)

**Key insight:** 854 images with aggressive augmentation reached 0.811 val mAP50. The more-data strategy is working decisively.
