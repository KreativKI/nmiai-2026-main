---
priority: INFO
from: overseer
timestamp: 2026-03-20 02:10 CET
self-destruct: delete after acknowledging in intelligence/for-overseer/
---

## GCP Available For Your Track

You have access to Google Cloud for running your prediction script. This is optional for ML (your workload is light) but available if you want reliability (survives Mac sleep, lower latency to API).

## GCP Details
- Project: `ai-nm26osl-1779`
- Account: `devstar17791@gcplab.me`
- L4 GPU zones: `europe-west1-b/c`, `europe-west2-a/b`, `europe-west3-a`
- ADC is set up: use `gcloud` normally
- APIs enabled: aiplatform, compute, storage, bigquery

## For ML Track
A small VM (no GPU needed) could run astar_v2.py with --poll to catch rounds automatically. Example:
```
gcloud compute instances create ml-runner --zone=europe-west1-b --machine-type=e2-medium --image-family=debian-12 --image-project=debian-cloud --boot-disk-size=20GB
```

Only set this up if JC approves. Do NOT auto-submit. The script defaults to --preview mode.
