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

### Phase 1: Gemini Shelf Generation for 116 Weak Categories (~2h, 3 VMs)
Use Gemini to generate each weak product ON A REALISTIC NORWEGIAN GROCERY SHELF.
Not white backgrounds. Not paste-on-shelf. Actual shelf scenes.

Prompt pattern: "This exact product [{name}] sitting on a partly stocked Norwegian grocery store shelf, front label clearly visible, realistic store lighting, between other products."

Split across 3 VMs (cv-train-1, cv-train-3, cv-train-4):
- 10 variations per product for the 54 "seen once" categories = 540 images
- 5 variations per product for the 62 "somewhat known" categories = 310 images
- Total: ~850 new REALISTIC shelf images

### Phase 2: Retrain on Real + Realistic Synthetic (~4h, 1 VM with GPU)
Combine:
- 208 real images (train split)
- ~850 Gemini realistic shelf images (Phase 1)
- Keep existing 315 copy-paste + 331 Gemini white-bg as secondary data
- Total: ~1700 images, but the new 850 are high-quality shelf scenes

Train YOLO11m with aggressive augmentation, 200 epochs.
Use the SAME proper train/val split (40 real images held out).

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
