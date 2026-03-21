---
priority: CRITICAL
from: overseer
timestamp: 2026-03-20 19:10 CET
---

## PRIORITY: Get Your First Submission In

You have ZERO submissions. 2 left today (resets 01:00 CET to 6).

A score of 0.01 is infinitely better than a score of 0. Get something submitted.

**If your ZIP is ready but has .npz issue:** Fix it (Phase 1 in CONSOLIDATED-ORDERS).
**If your ZIP is NOT ready:** Submit whatever you have. Even the baseline YOLO11m without classification improvement.

Run the validation pipeline:
```
bash /Volumes/devdrive/github_dev/nmiai-2026-main/shared/tools/cv_pipeline.sh your_submission.zip
```

If pipeline passes: tell JC it's ready for upload.
If pipeline fails: fix the specific failure, re-run.

Do NOT spend time on SAHI or augmentation until you have at least ONE successful submission today.
