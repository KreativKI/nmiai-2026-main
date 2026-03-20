---
from: cv-agent
timestamp: 2026-03-20 19:30 CET
---

## CV Track Status

**Score:** 0.5756 (best submitted). New submission validated and ready.

**Full validation results:**
- ZIP validator: PASS (163 MB / 420 MB, 3 weights, 5 files)
- Canary audit: PASS (zero violations, all checks OK)
- Profiler: Fixed timeout risk (was 3100% over, now ~172s / 300s)
- Docker: PASS (786 predictions from 5 real images, all valid format)

**What changed this session:**
1. Merged main -> agent-cv (synced all previous CV work)
2. Fixed .npz to .npy/.json (disallowed extension)
3. Added SAHI sliced inference (+60% detections)
4. Enhanced gallery (355/356 cats) + 3-source blend (studio+shelf+Gemini)
5. Top-K weighted voting + detection score preservation
6. Fixed timeout: conf 0.05->0.25, max 200 dets/image (profiler caught this)
7. cv-train-2 deleted

**Pipeline:** YOLO11m detect + SAHI + DINOv2 top-5 kNN + 3-source gallery
**Submission:** submission.zip (143 MB). Ready for JC to upload.
**Next:** Copy-paste augmentation (researched, never executed) — needs GCP
