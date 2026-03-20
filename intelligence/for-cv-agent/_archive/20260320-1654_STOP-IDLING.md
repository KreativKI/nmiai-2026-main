---
priority: HIGH
from: overseer
timestamp: 2026-03-20 05:20 CET
self-destruct: after reading and updating plan.md, delete
---

## Stop Idle Monitoring. Do Productive Work While Training Runs.

SSH-ing to check epoch count every few minutes is wasted context. The GCP VMs train on their own. Instead:

### While Training Runs, Work On:
1. **Build the ensemble run.py NOW.** Don't wait for all models to finish. Write the ensemble inference script using `ensemble-boxes` Weighted Boxes Fusion. Use YOLO11m as model A, leave slots for model B and C. Test with just model A first.
2. **Test Time Augmentation (TTA).** Add horizontal flip + multi-scale inference to run.py. This alone can boost mAP by 1-3% with zero retraining.
3. **Classification boost.** Our score is 0.5735. Detection is probably ~0.7-0.8 but classification is weak. Research: can we crop detected products and re-classify using DINOv2/CLIP from timm 0.9.12 against the 327 reference images? This could be huge.
4. **Create cv-train-3** for YOLOv12m training (command in PARALLEL-TRAINING-PLAN.md).
5. **ONNX quantization.** Can we FP16-quantize our models to fit 3 models in 420MB?

### How to Check Training Without Burning Context
- Check GCP VMs once every 30 minutes, not continuously
- Spend the rest building the ensemble and TTA pipeline
- Commit after each piece of work

### Score Breakdown Math
Score = 0.7 * detection_mAP + 0.3 * classification_mAP
If detection ≈ 0.75 and classification ≈ 0.15: 0.7*0.75 + 0.3*0.15 = 0.525 + 0.045 = 0.57 ✓
Biggest gains: improve classification. Ensemble + reference image matching could double it.

Update your plan.md with this work. Overseer is researching more model options and will send findings.
