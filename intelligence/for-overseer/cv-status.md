## CV Status — Revised Plan: Human-in-the-Loop Labeling
**Timestamp:** 2026-03-21 08:15 CET

**LEADERBOARD: 0.6584** | **Deadline: Sunday 15:00 CET (~31h)**

**Key lesson:** More low-quality synthetic data barely helped (+0.011). Quality matters.

**Revised strategy with JC as human labeler:**

### Phase 1: Generate ~2150 realistic shelf images (~10h, 2 VMs parallel)
- Gemini 3.1 Flash ("Nano Banana") with multi-reference product photos
- Confirmed working: 36s/image, 5 reference images per product, photorealistic output
- All 356 categories covered, weighted toward 134 weak products
- cv-train-1 + cv-train-3 running in parallel

### Phase 2: JC labels bounding boxes (~3-4h, manual)
- Butler agent building a web labeling GUI (assignment sent to agent-ops)
- JC draws one bounding box per image (product is pre-identified from filename)
- Tool saves in YOLO format, tracks progress
- This gives us HUMAN-QUALITY labels, not pseudo-labels

### Phase 3: Retrain YOLO11m (~4h, GPU)
- Real images + human-labeled Gemini shelf images
- 200 epochs, aggressive augmentation
- Proper train/val split

### Phase 4: Submit Saturday evening / Sunday morning
- Only the last submission matters
- 4 slots left today, 6 fresh Sunday

**Butler assignment:** `intelligence/for-ops-agent/CV-LABELING-TOOL.md`
Tool needed by ~12:00 CET when images are ready.

**GCP VMs:** cv-train-1, cv-train-3 for generation. cv-train-4 available. ml-churn is ML agent's.
