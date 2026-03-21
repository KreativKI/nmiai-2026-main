# NorgesGruppen Object Detection — Plan

**Track:** CV | **Task:** Grocery Shelf Detection | **Weight:** 33.33%
**Last updated:** 2026-03-21 14:15 CET

## Current State
- **Leaderboard:** 0.6584 (YOLO11m maxdata, 854 images)
- **Previous:** 0.6475 (YOLO11m, 348 images)
- **Val-to-leaderboard ratio:** ~0.807 (val 0.816 gave 0.6584)
- **Submissions left today:** 4 of 6 (resets 01:00 CET)
- **Deadline:** Sunday 15:00 CET (~25 hours remaining)

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

**RUNNING on 2 VMs (started 14:00 CET Saturday):**

| VM | Split | Categories | Images | ETA |
|----|-------|-----------|--------|-----|
| cv-train-1 | 0 (weakest) | 55 (41 seen-once, 13 barely-known, 1 somewhat-known) | 519 | ~17:00 CET |
| cv-train-4 | 1 (somewhat-known) | 55 (all somewhat-known) | 275 | ~17:00 CET |
| **Total** | | **110** | **794** | **~3h** |

cv-train-3 deleted (GPU stockout in europe-west1-b).

**Actual tier counts (verified from annotations):**
- 41 seen-once products (38 with reference images): 10 variations each = 380 images
- 13 barely-known (11 with ref): 8 variations each = 88 images
- 56 somewhat-known (47 with ref): 5 variations each = 235 images
- Well-known: SKIPPED (already 10+ training examples)

### Phase 2: Label the Generated Images
Two paths depending on whether Butler's labeling tool + JC's time works out:

**Path A: Human-in-the-loop (preferred)**
- Butler is building a web labeling GUI (assignment sent)
- JC draws one bounding box per image (category pre-filled from filename)
- Output: human-quality YOLO labels
- Time: ~3-4h for ~2000 images (5-10 sec per image with pre-suggested boxes)
- This gives the BEST labels but depends on JC having time

**Path B: Auto-labeling (backup if JC can't label all images)**
- Run our existing trained YOLO model on each generated image
- It detects products and creates pseudo-labels automatically
- Filter: only keep detections where confidence > 0.5 AND the detected category matches the product we generated
- This is circular (training on own predictions) but the new SHELF CONTEXT is still novel
- Quality: ~70% as good as human labels, but zero JC time needed

**Path C: Hybrid (most likely)**
- JC labels the 54 "seen once" products (540 images, ~1.5h)
- Auto-label the remaining 1610 images with Path B
- Best products get human labels, rest get good-enough auto-labels

### Phase 3: Retrain on Real + Labeled Synthetic (~4h, 1 VM with GPU)
Combine:
- 208 real images (train split) with original annotations
- ~2150 Gemini shelf images with labels (human or auto)
- Total: ~2350 images

Train YOLO11m with aggressive augmentation, 200 epochs.
Use the SAME proper train/val split (40 real images held out).

**Timeline (UPDATED):**
- Generation done: ~17:00 CET Saturday (2 VMs, ~3h from 14:00)
- Auto-labeling: ~17:30 CET (run YOLO on generated images, ~30 min)
- JC labels priority products: Saturday evening IF Butler GUI ready
- Retrain: Saturday evening (~4h on cv-train-1 with GPU)
- Evaluate + submit: Sunday morning
- Iterate if needed: Sunday (6 fresh slots)
- Deadline: Sunday 15:00 CET

### Phase 4: Evaluate + Submit
- Run honest eval on val set
- Apply calibration ratio (~0.80-0.85) to predict leaderboard score
- Run cv_pipeline.sh + canary
- Submit

### Phase 5: Iterate Based on Result
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

## In-Flight Work
- **Gemini generation:** RUNNING on cv-train-1 (split 0) + cv-train-4 (split 1). ETA ~17:00 CET.
- **Butler agent:** Check if labeling GUI is ready (assignment in intelligence/for-ops-agent/)
- **Auto-labeling script:** TODO: write after generation completes
- **Labeling strategy:** Hybrid (Path C): JC labels priority products if Butler GUI ready, auto-label the rest

## GCP VMs
| VM | Zone | Status |
|----|------|--------|
| cv-train-1 | europe-west1-c | GENERATING (split 0, 519 images) |
| cv-train-4 | europe-west3-a | GENERATING (split 1, 275 images) |
| ml-churn | europe-west1-b | ML agent (don't touch) |
| cv-train-3 | ~~deleted~~ | GPU stockout, cannot restart |

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
