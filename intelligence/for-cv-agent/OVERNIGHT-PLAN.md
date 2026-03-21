---
priority: CRITICAL
from: overseer
timestamp: 2026-03-21 01:00 CET
---

# CV Overnight Autonomous Plan (JC sleeping)

## GCP is FREE. Use ALL of it. Run everything in parallel.

You have ~8 hours until JC wakes up. 6 fresh submission slots after 01:00 reset. Multiple GCP VMs available. No reason to run anything sequentially.

## Parallel Tracks (run ALL simultaneously)

### Track A: YOLO11l (cv-train-3, already running)
- Finishing ~01:30 CET. When done:
- Export ONNX, build ZIP, run cv_pipeline.sh on GCP
- Have submission ready for JC when he wakes

### Track B: YOLO26 (spin up cv-train-4, NEW)
YOLO26 has Small-Target-Aware Label Assignment (STAL) - built for small products on dense shelves. This could be a breakthrough.
```bash
gcloud compute instances create cv-train-4 \
  --zone=europe-west2-a \
  --machine-type=g2-standard-8 \
  --accelerator=type=nvidia-l4,count=1 \
  --image-family=pytorch-latest-gpu \
  --image-project=deeplearning-platform-release \
  --boot-disk-size=100GB \
  --maintenance-policy=TERMINATE \
  --project=ai-nm26osl-1779
```
1. SSH in, pip install latest ultralytics
2. Upload augmented dataset from cv-train-1
3. Train YOLO26m on same dataset, same augmentation config
4. Export ONNX (opset <= 20 for sandbox compatibility)
5. Must work with onnxruntime 1.20.0 in sandbox

### Track C: Better Synthetic Images (cv-train-1, Gemini)
Current Gemini images are products on WHITE backgrounds. That's unrealistic.
**New prompt for Gemini:** Generate products as the LAST ITEM on a realistic Norwegian grocery store shelf. Shelf should look real, partly stocked, product clearly visible as a product for sale.

Example Gemini prompt:
```
A single [PRODUCT NAME] sitting on a partially empty Norwegian grocery store shelf.
The product is the last remaining item. The shelf has price tags and shelf labels visible.
Realistic supermarket lighting. Product is clearly identifiable and takes up about 30% of the image.
Photorealistic, high detail.
```
Generate 2 images per product category with this new prompt. These become additional YOLO training data.

### Track D: Extended Training (cv-train-1, after Gemini finishes)
When Gemini generation completes:
1. Download ALL Gemini images (both white background and shelf versions)
2. Generate YOLO-format pseudo-labels for shelf images
3. Retrain YOLO11m with: 248 real + 500 copy-paste + ALL Gemini images
4. 200 epochs instead of 120 (more data needs longer training)

## Submission Prep (for when JC wakes up)
For EVERY model that finishes training:
1. Export best checkpoint to ONNX
2. Build submission ZIP (run.py + best.onnx, under 420MB)
3. Run cv_pipeline.sh ON GCP (not local!)
4. Run canary subagent
5. Save validated ZIP ready for JC to upload

JC should wake up to a menu of validated ZIPs to choose from:
- YOLO11l augmented
- YOLO26m augmented (if training completes)
- YOLO11m extended training (if time)

## Rules (always)
- ALL compute on GCP
- Never use BETA API endpoints
- Verify ONNX opset compatibility with sandbox (onnxruntime 1.20.0)
- Boris workflow on every code change
- Report progress to /Volumes/devdrive/github_dev/nmiai-2026-main/intelligence/for-overseer/cv-status.md every 2 hours
- Oslo = CET = UTC+1
