---
from: cv-agent
timestamp: 2026-03-20 19:00 CET
---

## CV Track Status

**Score:** 0.5756 (best submitted). New submission ready with all improvements stacked.

**What changed this session:**
1. Merged main -> agent-cv (synced all previous CV work)
2. Fixed .npz to .npy/.json (disallowed extension that burned a submission)
3. Added SAHI sliced inference (+60% detections, +55% unique categories)
4. Upgraded to enhanced gallery (355/356 cats, was 326)
5. Implemented top-K weighted voting + detection score preservation (79 cats, was 72)
6. Built 3-source final gallery on GCP (studio 60% + shelf 20% + Gemini 20%)
7. cv-train-2 deleted (RF-DETR not competitive, saving credits)

**Current pipeline:** YOLO11m detect + SAHI tiles + DINOv2 top-5 kNN classify + 3-source gallery
**Submission ready:** submission.zip (143 MB), ZIP validator PASS, Docker validated.
JC uploads when ready.

**Remaining GCP:** cv-train-1 (idle, has all weights). Delete when no more training needed.
**Next code-only options:** softmax temperature on similarities, crop padding for better DINOv2 input
