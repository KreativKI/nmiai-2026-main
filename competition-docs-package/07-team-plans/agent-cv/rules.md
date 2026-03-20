# Rules — NorgesGruppen Object Detection (CV Track)

**Task:** Object detection on retail shelf images  
**Metric:** mAP@0.5 (70% detection + 30% classification)  
**Deadline:** Sunday 22 March 2026, 15:00 CET  

---

## Mandatory Fields

### Input
- **Format:** COCO dataset (images + annotations)
- **Training Data:** 248 shelf images, ~22,700 bbox annotations, 356 categories
- **Reference Images:** 327 products, multi-angle photos
- **Test Data:** Unknown (platform holds out)

### Output
- **Format:** COCO-format predictions (bbox + category_id)
- **Delivery:** ZIP upload (run.py + model weights)
- **Container:** Sandboxed Docker, NVIDIA L4 GPU, 24GB VRAM
- **Timeout:** 360 seconds per submission
- **Network:** No internet access in container

### Scoring
- **Metric:** mAP@0.5 (mean Average Precision at IoU threshold 0.5)
- **Breakdown:**
  - 70%: Detection (did we find the product?)
  - 30%: Classification (correct category_id?)
- **Range:** 0.0 to 1.0 (higher is better)

### Constraints
- **Must include:** run.py as entry point
- **Max size:** Check platform limits
- **No hardcoding:** Predictions must be model-based
- **No network:** Container has no internet

---

## Approach Summary

### Approach C (Baseline): YOLOv8 Inference
- Use pretrained YOLOv8n (no training)
- Direct inference on test images
- Expected: 40-50% mAP

### Approach B (Primary): Fine-tuned YOLOv8
- YOLOv8m pretrained on SKU-110K
- Fine-tune on NorgesGruppen COCO data
- Expected: 65-75% mAP

### Approach A (Stretch): YOLOv8 + Embeddings
- YOLOv8m for detection
- Product reference image embeddings for classification
- Few-shot learning with reference photos
- Expected: 80-90% mAP

---

## Validation Strategy
- Train/val split: 80/20 on COCO data
- Local mAP calculation using pycocotools
- Test inference pipeline end-to-end before submission

## Submission Command
```bash
cd solutions
zip -r submission_v1.zip run.py best.pt
# Upload via platform
```

## Rules Last Read
2026-03-19 20:30 CET (Gunnar)
