# RESEARCH-CV.md — NorgesGruppen Object Detection

**Track:** CV (Task 3)
**Agent:** agent-cv
**Date:** 2026-03-19 (Opus refresh at T+2.5h)
**Status:** Phase 2 RESEARCH — OPUS VALIDATED

---

## Problem Type
Retail shelf object detection with 356 product categories. COCO format input/output. mAP@0.5 scoring (70% detection + 30% classification). Runs in sandboxed Docker on NVIDIA L4 GPU (24GB VRAM), **no network access during inference**.

## Training Data
1. **COCO Dataset** (NM_NGD_coco_dataset.zip, ~864 MB)
   - 248 shelf images from Norwegian grocery stores
   - ~22,700 COCO-format bounding box annotations
   - 356 product categories (category_id 0–355)
   - 4 store sections: Egg, Frokost, Knekkebrod, Varmedrikker
   - bbox format: [x, y, width, height] in pixels (COCO format)

2. **Product Reference Images** (NM_NGD_product_images.zip, ~60 MB)
   - 327 individual products, multi-angle photos per barcode
   - Organized by barcode: {product_code}/main.jpg, front.jpg, back.jpg, etc.
   - Includes metadata.json with product names + annotation counts

## Key Constraint
- Inference runs offline in Docker — **all model weights must be in the ZIP**
- No downloading during inference
- L4 GPU available (24GB VRAM)
- 360s time limit for inference

## SOTA Resources

### 1. YOLOv8-SKU110K (Champion Model) ⭐
- **Source:** https://huggingface.co/foduucom/product-detection-in-shelf-yolov8
- **Model:** YOLOv8 fine-tuned on SKU-110K (densely packed retail shelves)
- **Match:** 90% — Exact domain: retail shelf detection
- **License:** Apache 2.0
- **Limitation:** SKU-110K detects generic "products" (1 class), not 356 categories. Must fine-tune classification head.

### 2. shelf-product-identifier (Detection + Classification)
- **Source:** https://github.com/albertferre/shelf-product-identifier
- **Approach:** YOLOv8 detection + image embeddings for product identification
- **Match:** 75% — Combines detection + classification via reference images
- **Key insight:** Uses product reference photos for few-shot matching — we have these!
- **Risk:** Embedding approach may be slow or complex to integrate

### 3. Ultralytics YOLOv8/v11 (Latest Framework)
- **Source:** https://docs.ultralytics.com/
- **Framework:** Native COCO format support, built-in augmentation, export to various formats
- **Key:** `ultralytics` already in our venv. Use directly.

### 4. Enhanced YOLOv8 with FFA-Net (Dense Product Detection)
- **Paper:** Springer 2025 — Enhanced YOLOv8 for retail cabinet product recognition
- **Insight:** Feature Fusion Attention Network improves detection in dense placement scenarios
- **Relevance:** Norwegian shelves are densely packed

## Approach Recommendations

### Approach A (Primary): YOLOv8m Fine-tuned on NorgesGruppen Data
1. Start with YOLOv8m pretrained on COCO (general detection)
2. Fine-tune on the 248 NorgesGruppen shelf images with 356 categories
3. Use mosaic + mixup augmentation (built into Ultralytics)
4. **GPU:** L4 can handle YOLOv8m at batch_size=8 (~15GB VRAM)
5. **Time:** 3-4 hours (including data prep)
6. **Expected Score:** 70-85% mAP

### Approach B (Fallback): Two-Stage (Detect + Classify)
1. YOLOv8 SKU-110K weights for detection (1 class: "product")
2. Separate classifier (ResNet/EfficientNet) trained on product reference images
3. Crop detected products → classify with reference model
4. **Advantage:** Decouples detection from classification
5. **Time:** 4-6 hours
6. **Expected Score:** 60-75% mAP

### Approach C (Baseline — MUST SHIP FIRST): YOLOv8n + Minimal Training
- YOLOv8n (nano) pretrained on COCO
- Fine-tune for 10-20 epochs on NorgesGruppen data
- **Time:** 1 hour
- **Expected Score:** 40-55% mAP
- **Purpose:** Guaranteed valid submission

## Critical Implementation Notes

### Scoring Math
- **70%:** Detection — did we find products? (IoU ≥ 0.5)
- **30%:** Classification — did we assign correct category_id?
- **Metric:** mAP@0.5 (mean Average Precision at IoU threshold 0.5)
- **Implication:** Detection matters more than classification. A model that finds all products but misclassifies some still scores well.

### Data Considerations
- 248 images / 356 categories = very few examples per category (~1-2 on average)
- Some categories may have zero training examples (category 356 = "unknown_product")
- This is a **few-shot / long-tail classification** problem
- Product reference images (multi-angle) can help augment rare categories

### run.py Requirements
```python
# Must read input images from a specified directory
# Must output COCO-format predictions
# Must include model weights in the ZIP
# No network access
```

### GPU Strategy (L4, 24GB VRAM)
| Model | VRAM | Batch | Speed | mAP (typical) |
|-------|------|-------|-------|----------------|
| YOLOv8n | ~4GB | 16 | Fast | 37-45% |
| YOLOv8s | ~8GB | 16 | Fast | 44-50% |
| YOLOv8m | ~15GB | 8 | Medium | 50-59% |
| YOLOv8l | ~20GB | 4 | Slow | 53-63% |
| YOLOv8x | ~24GB | 2 | Slowest | 54-65% |

**Recommendation:** Train YOLOv8m, inference with YOLOv8m. If time permits, ensemble with YOLOv8l.

### Data Augmentation Strategy
- Mosaic augmentation (YOLO built-in) — critical for small datasets
- MixUp (α=0.3)
- RandomHorizontalFlip
- ColorJitter (brightness ±0.3, contrast ±0.3)
- Scale jitter (0.8-1.2)
- NO vertical flip (shelves don't flip vertically)

## Ceiling Analysis
- **What separates good from #1:** (a) Handling rare categories via reference images, (b) Dense product detection without missed/merged boxes, (c) Proper NMS tuning for densely packed shelves
- **Theoretical ceiling:** ~90%+ mAP with perfect training data balance
- **Realistic ceiling with 248 images:** 75-85% mAP

## Next Steps (Priority Order)
1. Download COCO dataset + product reference images from platform
2. Verify data integrity, check category distribution
3. Implement Approach C (YOLOv8n baseline) — submit within 1h
4. Implement Approach A (YOLOv8m fine-tune) — 3-4h
5. If classification weak: add Approach B (two-stage) pipeline
6. Tune NMS confidence threshold for dense shelves

## References
- [Ultralytics YOLOv8 Docs](https://docs.ultralytics.com/)
- [YOLOv8 SKU-110K Model](https://huggingface.co/foduucom/product-detection-in-shelf-yolov8)
- [SKU-110K Dataset](https://docs.ultralytics.com/datasets/detect/sku-110k/)
- [Shelf Product Identifier](https://github.com/albertferre/shelf-product-identifier)
- [Enhanced YOLOv8 for Retail](https://link.springer.com/article/10.1007/s11760-025-04180-x)
