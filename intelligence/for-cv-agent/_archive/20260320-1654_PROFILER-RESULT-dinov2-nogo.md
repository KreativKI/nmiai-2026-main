---
from: butler
timestamp: 2026-03-20 12:45 CET
priority: CRITICAL
---
## DINOv2 Submission: NO-GO (4882% over timeout)

Profiled `submission_dinov2_classify_v1.zip` against 5 training images.

**Problem:** YOLO at conf=0.05 produces ~1,303 detections per image. Each detection runs DINOv2 inference (518x518). That's ~294 seconds per image on CPU.

Even on L4 GPU with 5x speedup: ~14,647s total for 248 images. Timeout is 300s.

**Root cause:** CONF_THRESHOLD = 0.05 is way too low. Most detections are noise.

**Options (your call, these are solution decisions):**
A. Raise CONF_THRESHOLD to 0.25-0.50 (cuts detections to ~50-100/image)
B. Batch DINOv2 crops instead of one-at-a-time inference
C. Add a top-N cap per image (e.g. keep top 200 by confidence)
D. Drop DINOv2 entirely, submit YOLO-only (scores up to 70% max)

**Profiler tool:** `shared/tools/cv_profiler.py` - re-run after any changes.
