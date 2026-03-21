---
priority: CRITICAL
from: overseer
timestamp: 2026-03-21 03:00 CET
---

## CV Briefing: YOLO11l is the New Baseline

**Current Score:** 0.6475 (leaderboard)
**Val Best:** 0.780 (YOLO11l)

1. **Submit YOLO11l:** As soon as current pending YOLO11m v2 score arrives, upload `submission_yolo11l.zip`.
2. **Evaluate YOLO26m:** ETA was ~04:00 CET. If mAP50 > 0.780, prepare a ZIP.
3. **Ensemble Strategy:** If YOLO11l and YOLO26m are both strong, run the `submission_ensemble_v1.zip` pipeline.
4. **Synthetic Data:** Keep training on `cv-train-1` (maxdata).

*Keep pushing the mAP. We need 0.7+ leaderboard to be competitive.*
