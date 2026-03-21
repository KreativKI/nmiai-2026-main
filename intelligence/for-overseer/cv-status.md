## CV Status — Overnight Complete, 3 ZIPs Ready
**Timestamp:** 2026-03-21 05:40 CET

**LEADERBOARD: 0.6475** | **Best Val: 0.816** (maxdata)

**3 Validated ZIPs for JC (all pipeline + canary PASS):**

| Priority | ZIP | Model | Val mAP50 |
|----------|-----|-------|-----------|
| 1 | `submission_maxdata.zip` | YOLO11m, 854 imgs, 200ep | **0.816** |
| 2 | `submission_yolo11l.zip` | YOLO11l, 348 imgs, 120ep | 0.780 |
| 3 | `submission_aggressive_v2_final.zip` | YOLO11m, 348 imgs, 120ep | 0.767 |

**GCP VMs:**
- cv-train-1: DONE (maxdata model complete)
- cv-train-3: DONE (YOLO11l complete)
- cv-train-4: DONE (YOLO26m complete, 0.485, not competitive)

**Overnight summary:**
- Ran 3 parallel training experiments on free GCP GPUs
- Best model: YOLO11m on 854 images (208 real + 140 synth v1 + 175 synth v2 + 331 Gemini)
- More data = less overfitting: val gap shrank from 0.38 to ~0.05
- YOLO26m was not competitive (0.485), YOLO11 family wins on this dataset

**6 Saturday submission slots available.** Submit maxdata first.
