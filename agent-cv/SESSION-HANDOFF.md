# CV Session Handoff — 2026-03-21 08:00 CET

## Leaderboard: 0.6584 | ~31 hours to deadline (Sun 15:00 CET)

## Strategy: Quality Over Quantity
Low-quality synthetic data barely moved the needle (+0.011). New approach: use Gemini 3.1 Flash ("Nano Banana") with MULTI-REFERENCE IMAGES to generate 994 realistic shelf images for all 134 weak products.

## CONFIRMED AND TESTED
- Gemini 3.1 Flash multi-reference: 5/5 images generated, 36s avg per image
- Up to 10 reference images per product (object fidelity mode)
- Feeding actual product photos (front/back/left/right) produces much more accurate results
- Imagen 3.0 also available but text-only (no reference images)

## Next Session: Execute Full Pipeline

### Step 1: Write generation script
- Load ALL available reference images per product (studio photos + shelf crops + existing Gemini)
- Feed to Gemini 3.1 Flash with shelf scene prompt
- Save images with product name + category_id in filename
- Save manifest.json mapping filename -> category

### Step 2: Generate ~2150 images on 2 VMs (~10h parallel)
- cv-train-1: categories 0-177
- cv-train-3: categories 178-355
- 15 variations for "seen once", 10 for "barely known", 8 for "somewhat known", 3 for "well-known"

### Step 3: JC labels bounding boxes using Butler's GUI tool
- Butler building labeling tool (assignment in intelligence/for-ops-agent/)
- JC draws one box per image, category pre-filled
- Output: YOLO format labels

### Step 4: Retrain + Submit
- Merge real images + human-labeled Gemini shelf images
- Retrain YOLO11m, 200 epochs
- Evaluate, validate, submit

## Product Weakness Tiers
| Tier | Count | Generate per product | Total images |
|------|-------|---------------------|-------------|
| Seen once | 54 | 10 | 540 |
| Barely known (2 imgs) | 18 | 8 | 144 |
| Somewhat known (3-9 imgs) | 62 | 5 | 310 |
| **Total** | **134** | | **994** |

## GCP VMs
- cv-train-1: europe-west1-c (has all data, models, Gemini ADC) -- USE FOR GENERATION
- cv-train-3: europe-west1-b -- USE FOR GENERATION
- cv-train-4: europe-west3-a -- available for training later
- ml-churn: ML agent, don't touch

## API Details
- Model: gemini-3.1-flash-image-preview
- Location: "global" (for Vertex AI)
- Rate limit: 60 RPM per project (we use ~4 RPM with 2 VMs)
- Generation time: 36s average per image (25-58s range)
- Reference images: up to 10 per product (object fidelity)

## Calibration (predict leaderboard from val)
| Val mAP50 | Leaderboard | Ratio |
|-----------|-------------|-------|
| 0.767 | 0.6475 | 0.845 |
| 0.816 | 0.6584 | 0.807 |
Use ~0.82 ratio to estimate. Only the LAST submission on Sunday matters.
