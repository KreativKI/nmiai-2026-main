---
priority: HIGH
from: overseer
timestamp: 2026-03-20 23:50 CET
---

## GCP IS FREE -- Use All Available GPUs

All GCP compute is free for this competition. Stop running one thing at a time.

**Spin up parallel training runs:**
- cv-train-1: current YOLO11m augmented (already running)
- cv-train-3 (europe-west1-b): YOLO11l on same augmented dataset
- cv-train-4 (europe-west2-a): YOLO11m with different augmentation config (heavier copy-paste, imgsz=1536)

Three models overnight = three candidates Saturday morning. Upload datasets via gcloud compute scp, start training, let them run.

Don't wait for one to finish before starting the next.
