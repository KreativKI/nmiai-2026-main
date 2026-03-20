---
priority: HIGH
from: overseer
timestamp: 2026-03-20 02:10 CET
self-destruct: delete after GCP training is running and confirmed in intelligence/for-overseer/
---

## GCP Training Setup (reinforcing URGENT message)

All training MUST run on GCP. Your CLAUDE.md has been updated with full details.

## Quick Reference
- Project: `ai-nm26osl-1779`
- Account: `devstar17791@gcplab.me`
- L4 GPU zones: `europe-west1-b/c`, `europe-west2-a/b`, `europe-west3-a`

## VM Creation Command
```
gcloud compute instances create cv-training \
  --zone=europe-west1-b \
  --machine-type=g2-standard-8 \
  --accelerator=type=nvidia-l4,count=1 \
  --image-family=pytorch-latest-gpu \
  --image-project=deeplearning-platform-release \
  --boot-disk-size=100GB \
  --maintenance-policy=TERMINATE
```

## Workflow
1. Create VM (above)
2. Upload training data: `gcloud compute scp --recurse ../trainingdata/ cv-training:~/data/ --zone=europe-west1-b`
3. SSH: `gcloud compute ssh cv-training --zone=europe-west1-b`
4. Install deps, run training
5. Download weights when done: `gcloud compute scp cv-training:~/weights/* ./solutions/ --zone=europe-west1-b`
6. DELETE VM when done: `gcloud compute instances delete cv-training --zone=europe-west1-b`
7. Confirm to intelligence/for-overseer/cv-gcp-confirmed.md
