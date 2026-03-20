---
from: cv-agent
timestamp: 2026-03-20 18:50 CET
---

## CV Track Status

**Score:** 0.5756 (best submitted). New submission ready with expected improvement.

**What changed this session:**
1. Merged main -> agent-cv (synced all previous CV work)
2. Fixed .npz to .npy/.json (disallowed extension that burned a submission)
3. Added SAHI sliced inference (+60% detections, +55% unique categories)
4. Upgraded to enhanced gallery (355/356 cats, was 326)
5. Implemented top-K weighted voting + detection score preservation (79 unique cats, was 72)
6. cv-train-2 deleted (RF-DETR was not competitive)

**Submission ready:** submission.zip (143 MB), ZIP validator PASS, Docker validated.
JC uploads when ready.

**Next:** Action 3 (3-source final gallery with Gemini photos on cv-train-1)
