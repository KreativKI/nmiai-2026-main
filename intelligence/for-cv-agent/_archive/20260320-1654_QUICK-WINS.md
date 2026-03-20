---
priority: CRITICAL
from: overseer
timestamp: 2026-03-20 05:50 CET
self-destruct: after acting on these, delete
---

## Two Quick Wins Before Anything Else

### A. Lower Confidence Threshold (5 minutes, free score boost)
Current run.py has `CONF_THRESHOLD = 0.15`. Change to `0.01`.

mAP calculation handles filtering. A lower threshold means more detections, which helps recall without hurting precision in the mAP metric. This is standard practice in detection competitions.

Edit run.py line 18: `CONF_THRESHOLD = 0.01`

Build new ZIP, Docker validate, mark as v3.

### B. Train YOLO11l or YOLO11x (bigger backbone, same pipeline)
Your YOLO11m has 20.1M params. The L4 has 24GB VRAM.

| Variant | Params | ONNX Size | COCO mAP50-95 |
|---------|--------|-----------|---------------|
| YOLO11m | 20.1M | ~78 MB | 51.5 |
| YOLO11l | 25.3M | ~100 MB | 53.4 |
| YOLO11x | 56.9M | ~220 MB | 54.7 |

Start YOLO11l training on the first VM that finishes (or create cv-train-4). Same training script, just change the model:
```python
model = YOLO("yolo11l.pt")
model.train(data="norgesgruppen.yaml", imgsz=1280, epochs=150,
            batch=8, mosaic=1.0, mixup=0.15, copy_paste=0.1,
            close_mosaic=15, scale=0.9, patience=30)
```

YOLO11l + YOLO11m ensemble = ~178MB. Plenty of room for DINOv2 classifier (42MB). Total: 220MB out of 420MB budget.

### Add to Your Plan
Insert these as Phase 0A and 0B, before TTA work.
