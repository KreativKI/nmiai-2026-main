---
priority: HIGH
from: overseer
timestamp: 2026-03-20 05:15 CET
self-destruct: after incorporating into plan.md, delete
---

## YOLO11m v2 Scored: 0.5735

First real score on the board. Now we scale up.

### Current VMs
- cv-train-1 (europe-west1-c): YOLO26m, epoch ~48
- cv-train-2 (europe-west3-a): RF-DETR, resumed from epoch 12

### New VMs to Create (JC approved, free GCP compute)

**VM 3: YOLOv12 medium**
```
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
- YOLOv12 uses attention (Area Attention A2) instead of pure CNN
- Captures spatial context better for dense shelf layouts
- Train with ultralytics: `YOLO("yolo12m.pt").train(data=..., epochs=100, imgsz=1280)`

**VM 4: Ensemble run.py development**
- Don't need a new VM for this, do it locally or on an existing VM after training completes
- Use `ensemble-boxes` (pre-installed in sandbox) with Weighted Boxes Fusion
- Combine predictions from YOLO11m + YOLO26m + RF-DETR + YOLOv12
- This is likely our biggest score jump: different architectures catch different products

### Ensemble Strategy (KEY INSIGHT)
`ensemble-boxes 1.0.9` is pre-installed in the sandbox. This means our run.py can:
1. Load multiple ONNX models (up to 420MB total, max 3 weight files)
2. Run inference with each model
3. Fuse detections via Weighted Boxes Fusion
4. Submit fused predictions

**Constraint:** Max 3 weight files, 420MB total. So we pick the best 3 models and ensemble them.

### Updated Phase Plan

**Phase 1:** Continue monitoring YOLO26m and RF-DETR training (already running)
**Phase 2:** Create cv-train-3, start YOLOv12m training
**Phase 3:** As each model finishes: export ONNX, Docker-validate solo, measure mAP
**Phase 4:** Build ensemble run.py using Weighted Boxes Fusion with best 3 models
**Phase 5:** Docker-validate ensemble submission (check: total weight < 420MB, inference < 300s)
**Phase 6:** Prepare ensemble ZIP for JC to upload

### Classification Boost
Our 0.5735 suggests classification is weak. Two options:
A. Ensemble inherently improves classification (different models disagree on hard classes, majority wins)
B. If still weak: crop detected products, match against 327 reference images with cosine similarity (timm 0.9.12 has DINOv2/CLIP backbones pre-installed)

### Priority Order
1. Get YOLO26m and RF-DETR finished (already running)
2. Start YOLOv12m on new VM
3. Build ensemble run.py as soon as 2+ models are ready
4. Classification boost if ensemble alone isn't enough
