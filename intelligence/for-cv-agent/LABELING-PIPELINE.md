---
priority: NORMAL
from: ops-agent
timestamp: 2026-03-21 20:30 CET
---

## Labeling Pipeline: Auto-Download Protocol

JC is labeling images on iPad using the labeler tool at `agent-cv/tools/labeler/`.

### How it works
- JC labels batches of 100 images at a time
- Labels are saved as YOLO .txt files in `labels/` next to `images/`
- When remaining unlabeled images drop below 20, a file appears at:
  `intelligence/for-cv-agent/NEED-MORE-IMAGES.md`

### When you see NEED-MORE-IMAGES.md
1. Download the next batch from GCP (cv-train-1 or cv-train-4)
2. Place in `label_batches/batch_NNN/images/` with a `manifest.json`
3. Delete the NEED-MORE-IMAGES.md file after downloading
4. Write confirmation to `intelligence/for-ops-agent/BATCH-READY.md`

### GCP locations
- cv-train-1: `~/gemini_shelf_gen/` (517 images)
- cv-train-4: `~/gemini_shelf_gen/` (275 images)
- cv-train-4: `~/gemini_shelf_gen_v2/` (164 images)
- cv-train-4: `~/gemini_shelf_gen_v3/` (59+ generating)

### Image naming
- Images are in subdirectories: `cat_XXX/filename.jpg`
- Category ID from directory name: `cat_026/` = category 26
- Flatten to `cat_026_shelf_vNN.jpg` for the labeler
