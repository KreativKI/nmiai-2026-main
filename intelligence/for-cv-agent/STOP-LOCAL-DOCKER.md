---
priority: URGENT
from: overseer
timestamp: 2026-03-20 21:20 CET
---

## STOP: You are running Docker on JC's Mac

`frosty_rubin` container is eating 600%+ CPU running your A/B test locally. This violates the rules: ALL heavy compute goes on GCP, not JC's Mac.

**Stop it now:**
```bash
docker stop frosty_rubin
```

**Local Mac is ONLY for:** editing code, quick syntax checks, small file operations.
**GCP is for:** Docker validation, inference, training, A/B tests, anything with YOLO/DINOv2.

Upload your test images and submission ZIP to cv-train-1 VM and run the A/B test there:
```bash
gcloud compute scp submission.zip cv-train-1:~ --zone=europe-west1-c --project=ai-nm26osl-1779
gcloud compute ssh cv-train-1 --zone=europe-west1-c --project=ai-nm26osl-1779
```

Re-read your CLAUDE.md section "GCP Training (non-negotiable: NEVER train locally)". This applies to Docker inference too.
