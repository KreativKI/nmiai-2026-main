---
priority: URGENT
from: overseer
timestamp: 2026-03-20 01:55 CET
self-destruct: delete this file after confirming GCP training is running
---

STOP LOCAL TRAINING IMMEDIATELY.

All training must run on Google Cloud, not on JC's Mac.

## GCP Details
- Project: ai-nm26osl-1779
- Account: devstar17791@gcplab.me
- L4 GPUs available: europe-west1-b/c, europe-west2-a/b, europe-west3-a
- APIs enabled: aiplatform, compute, storage
- ADC is set up: just use gcloud normally

## What To Do
1. Kill any local training process
2. Spin up a Compute Engine VM with L4 GPU in one of the available zones
3. Upload training data to the VM
4. Run training there
5. Download trained weights back when done
6. Write confirmation to intelligence/for-overseer/cv-gcp-confirmed.md
