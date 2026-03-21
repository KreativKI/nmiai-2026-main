# NorgesGruppen Object Detection — Plan

**Track:** CV | **Task:** Grocery Shelf Detection | **Weight:** 33.33%
**Last updated:** 2026-03-21 07:30 CET

## Current State
- **Leaderboard:** 0.6584 (YOLO11m maxdata, 854 images)
- **Previous:** 0.6475 (YOLO11m, 348 images)
- **Val-to-leaderboard ratio:** ~0.807 (val 0.816 gave 0.6584)
- **Submissions left today:** 4 of 6 (resets 01:00 CET)
- **Deadline:** Sunday 15:00 CET (~31 hours remaining)

## Key Insight: Synthetic Data Quality Matters More Than Quantity
Going from 348 to 854 images only moved leaderboard +0.011. The 500 extra synthetic images (copy-paste + Gemini white-background) inflate val scores but don't teach the model what real test shelves look like. We need REALISTIC shelf images, not more of the same.

## Calibrated Scoring (predicted vs actual)

| # | Val mAP50 | Leaderboard | Ratio | What |
|---|-----------|-------------|-------|------|
| 2 | 0.95 (fake) | 0.5756 | - | Baseline, val=train |
| 4 | 0.767 | 0.6475 | 0.845 | Proper split + augmentation (348 imgs) |
| 5 | 0.816 | 0.6584 | 0.807 | Maxdata (854 imgs, ratio WORSE) |

More synthetic data = diminishing returns UNLESS the synthetic data matches test distribution.

## The Problem: 116 Weak Categories
- 54 products seen only ONCE in training
- 62 products seen 3-9 times
- These 116 categories are where classification mAP bleeds
- The model memorizes rare products instead of learning to generalize

## New Strategy: Realistic Shelf Generation (iterative, each submission builds on the last)

### Phase 1: Gemini 3.1 Flash Multi-Reference Shelf Generation (~5h, 2 VMs parallel)
Use Gemini 3.1 Flash ("Nano Banana") with up to 10 REFERENCE IMAGES per product.
Feed the model actual product photos (front, back, left, right, main) plus shelf crops,
then generate the product ON A REALISTIC NORWEGIAN GROCERY SHELF.

**Tested and confirmed:** 5/5 images generated successfully. 36s average per image.
Multi-reference produces much more accurate product appearance than text-only prompts.

**Approach:**
- Feed all available reference photos (product studio shots + training shelf crops)
- Prompt: "Generate this EXACT product on a Norwegian grocery shelf, front label visible"
- Vary: shelf position, lighting, surrounding products, camera angle

**Split across 2 VMs (rate limit is 60 RPM per project, we use ~4 RPM):**

| VM | Categories | Products | Images | Time |
|----|-----------|----------|--------|------|
| cv-train-1 | 0-177 (weak ones) | ~67 | ~497 | ~5h |
| cv-train-3 | 178-355 (weak ones) | ~67 | ~497 | ~5h |
| **Total** | | **134** | **994** | **~5h** |

**Generation config per product tier:**
- 54 "seen once" products: 10 variations each = 540 images
- 18 "barely known" (2 imgs): 8 variations each = 144 images
- 62 "somewhat known" (3-9 imgs): 5 variations each = 310 images

### Phase 2: Retrain on Real + Realistic Synthetic (~4h, 1 VM with GPU)
Combine:
- 208 real images (train split)
- ~994 Gemini realistic shelf images (Phase 1, HIGH QUALITY)
- Optionally keep existing copy-paste + Gemini white-bg as secondary data
- Total: ~1200-1700 images, with the new 994 being realistic shelf scenes

Train YOLO11m with aggressive augmentation, 200 epochs.
Use the SAME proper train/val split (40 real images held out).

**Timeline:**
- Generation done: ~12:00-13:00 CET Saturday
- Retrain done: ~17:00 CET Saturday
- Evaluate + submit: Saturday evening
- Iterate if needed: Sunday morning (6 fresh slots)
- Deadline: Sunday 15:00 CET

### Phase 3: Evaluate + Submit
- Run honest eval on val set
- Apply calibration ratio (~0.80-0.85) to predict leaderboard score
- Run cv_pipeline.sh + canary
- Submit

### Phase 4: Iterate Based on Result
- If improved: generate more variations, target next weakness
- If not: try confidence threshold sweep, ensemble YOLO11m + YOLO11l

## Product Inventory
- 356 categories total (0-354 named products, 355 = unknown_product)
- No hidden categories. Test set uses same catalog.
- unknown_product (355) is most annotated (422 annotations, 90 images)
- Annotators were thorough: 92 annotations per image average

| Tier | Categories | Training images | Action |
|------|-----------|----------------|--------|
| Well-known (10+) | 222 | 10-86 each | Fine, model handles these |
| Somewhat known (3-9) | 62 | 3-9 each | Generate 5 shelf variations each |
| Barely known (2) | 18 | 2 each | Generate 10 shelf variations each |
| Seen once | 54 | 1 each | Generate 10 shelf variations each (PRIORITY) |

## GCP VMs Available
| VM | Zone | Status |
|----|------|--------|
| cv-train-1 | europe-west1-c | IDLE (has all data + models) |
| cv-train-3 | europe-west1-b | IDLE |
| cv-train-4 | europe-west3-a | IDLE |
| ml-churn | europe-west1-b | ML agent (don't touch) |

## Validated ZIPs Ready
- `submission_maxdata.zip` -- YOLO11m, 854 imgs, val 0.816, leaderboard 0.6584
- `submission_yolo11l.zip` -- YOLO11l, 348 imgs, val 0.780, untested
- `submission_aggressive_v2_final.zip` -- YOLO11m, 348 imgs, leaderboard 0.6475

## What NOT to Do
- No more SAHI (proven: hurts)
- No DINOv2 at inference (proven: hurts)
- No mass random copy-paste (diminishing returns on leaderboard)
- No rotation augmentation on products (makes labels unreadable)
- Don't trust val scores alone. Use calibration ratio ~0.80-0.85.

## Critical Constraints
- BLOCKED IMPORTS: os, sys, subprocess, etc. = instant ban
- Max 420 MB weights, 3 weight files, 10 .py files, 300s timeout
- 6 submissions/day, resets 01:00 CET
- ALL compute on GCP, never local Mac
- Oslo = CET = UTC+1
