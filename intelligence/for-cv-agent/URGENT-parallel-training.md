---
priority: URGENT
from: overseer
timestamp: 2026-03-20 03:19 CET
self-destruct: delete after all 3 VMs are training and confirmed in intelligence/for-overseer/
---

## Spin Up Parallel Training NOW

Stop waiting for YOLO11m to finish. Run all 3 models simultaneously on separate VMs:

| VM | Zone | Model | Command |
|---|---|---|---|
| `cv-train-1` | europe-west1-c | YOLO11m | Already running |
| `cv-train-2` | europe-west1-b | YOLO26m | CREATE NOW |
| `cv-train-3` | europe-west2-a | RF-DETR | CREATE NOW |

### VM Creation
```bash
# YOLO26m
gcloud compute instances create cv-train-2 \
  --zone=europe-west1-b \
  --machine-type=g2-standard-8 \
  --accelerator=type=nvidia-l4,count=1 \
  --image-family=pytorch-latest-gpu \
  --image-project=deeplearning-platform-release \
  --boot-disk-size=100GB \
  --maintenance-policy=TERMINATE \
  --project=ai-nm26osl-1779

# RF-DETR
gcloud compute instances create cv-train-3 \
  --zone=europe-west2-a \
  --machine-type=g2-standard-8 \
  --accelerator=type=nvidia-l4,count=1 \
  --image-family=pytorch-latest-gpu \
  --image-project=deeplearning-platform-release \
  --boot-disk-size=100GB \
  --maintenance-policy=TERMINATE \
  --project=ai-nm26osl-1779
```

### Upload training data to each
```bash
gcloud compute scp --recurse ../trainingdata/ cv-train-2:~/data/ --zone=europe-west1-b
gcloud compute scp --recurse ../trainingdata/ cv-train-3:~/data/ --zone=europe-west2-a
```

### Reusable tools
Check `/Volumes/devdrive/github_dev/NM_I_AI_dash/tools/ab_compare.py` for comparing model outputs when all 3 finish.

### When all 3 finish
- Export best checkpoint from each to ONNX
- Compare mAP50 scores
- Pick best single model OR ensemble top 2
- Docker-validate before submission
- DELETE VMs when done (save cost)

Confirm in intelligence/for-overseer/cv-parallel-training.md
