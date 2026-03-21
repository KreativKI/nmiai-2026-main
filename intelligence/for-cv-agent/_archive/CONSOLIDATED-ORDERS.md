---
priority: CRITICAL
from: overseer
timestamp: 2026-03-20 16:30 CET
permanent: true
---

## Consolidated Orders: What Moves Your Score

Your score: 0.5756. Detection is solved. Classification is the bottleneck.
Delete all other standing orders. This is the only plan.

### Phase 1: Fix ZIP (.npz to .npy)
gallery.npz is DISALLOWED. Allowed extensions: .py .json .yaml .yml .cfg .pt .pth .onnx .safetensors .npy

Fix: save gallery embeddings as gallery.npy, labels as gallery_labels.json.
Update run.py to load the new files.
Run validate_cv_zip.py to confirm no disallowed extensions.
Rebuild ZIP. Commit.

### Phase 2: Run Full QC Toolchain
```
python3 shared/tools/validate_cv_zip.py submission.zip
python3 shared/tools/cv_judge.py --predictions-json predictions.json
```
Only proceed to submission if QC passes.
1 submission left today. Save it for a validated improvement.

### Phase 3: SAHI Sliced Inference (no retraining)
Tile images into overlapping 640x640 patches. Run detection on each tile.
Map coords back to full image. Merge with WBF.
Expected: +3-8% on small products.
No retraining needed. Pure run.py change.

### Phase 4: Copy-Paste Augmentation Pipeline
Cut 327 product reference images, paste onto shelf backgrounds.
Use cv2.seamlessClone for realistic blending.
Generate 250-500 synthetic images with auto-generated COCO annotations.
Retrain YOLO11m on combined dataset (248 real + 500 synthetic) on GCP.

### Phase 5: Train YOLO11l (bigger backbone)
Same pipeline as YOLO11m but 25.3M params instead of 20.1M.
Train on GCP VM. Export ONNX. Compare with cv_judge.

### Communication
After each phase, write a 3-line status to:
`/Volumes/devdrive/github_dev/nmiai-2026-main/intelligence/for-overseer/cv-status.md`

### Rules
- ALLOWED EXTENSIONS: .py .json .yaml .yml .cfg .pt .pth .onnx .safetensors .npy
- Run validate_cv_zip.py before EVERY submission
- Commit after every phase
- Log everything in EXPERIMENTS.md
- 6 submissions per day, 2 concurrent max
