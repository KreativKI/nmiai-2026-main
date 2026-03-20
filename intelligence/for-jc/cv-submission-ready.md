---
priority: HIGH
from: cv-agent
timestamp: 2026-03-20 04:35 CET
---

## CV Submission v2 Ready for Upload

### Fix Applied
The v1 failure (exit code 2) was caused by argparse rejecting unknown CLI arguments from the competition sandbox. Fixed by using `parse_known_args()` and adding `--input` as an alias for `--images`.

### QC Results (all passed)
- ZIP: `agent-cv/submissions/submission_yolo11m_v2.zip` (65 MB)
- Docker exit code: 0
- Predictions: 107 on test image
- Sample: image_id=1, cat=27, score=0.5198, bbox=[1191.9, 714.98, 141.77, 83.68]
- Blocked imports: NONE
- Accepts both `--images` and `--input` flags
- Accepts unknown extra arguments without crashing

### Model Performance (training val)
- YOLO11m, 100 epochs on L4 GPU
- mAP50: 0.945, mAP50-95: 0.727
- ONNX: 78 MB, opset 17

### Still Training (parallel)
- YOLO26m on cv-train-1 (europe-west1-c): ~31 epochs, mAP50=0.701
- RF-DETR on cv-train-2 (europe-west3-a): epoch 4/50

### Action for JC
Upload `agent-cv/submissions/submission_yolo11m_v2.zip` at app.ainm.no when ready.
