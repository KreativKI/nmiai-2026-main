---
priority: HIGH
from: cv-agent
timestamp: 2026-03-21 20:25 CET
permanent: true
---

## Image Batch Notification Protocol

### How it works
When new batches of images are ready for JC to label, I (CV agent) will drop a file here:

```
intelligence/for-ops-agent/NEW-BATCH-READY.md
```

The file will contain:
- Path to the batch folder on JC's Mac
- Number of images
- Manifest location (product names + category IDs)
- Which products are highest priority

### Butler's job
When you see `NEW-BATCH-READY.md`:
1. Notify JC that a new batch is ready for labeling
2. Open the batch folder if the labeling GUI is running
3. After JC finishes, notify CV agent by dropping a file at:
   `intelligence/for-cv-agent/BATCH-LABELED.md`
   with the path to the completed labels

### Batch structure
```
label_batches/batch_NNN/
  images/      <- shelf images to label
  labels/      <- JC puts YOLO .txt files here
  manifest.json <- {filename: {category_id, product_name}}
```

### Current status
- batch_001: DONE (100 images labeled, in labeled_complete/)
- batch_002: ON JC'S MAC, ready to label (label_batches/batch_002/)
- More batches: will be downloaded from GCP and notification dropped here

### Label format
One .txt file per image. One line: `{category_id} {cx} {cy} {w} {h}` (normalized 0-1).
JC draws ONE tight bounding box around the target product per image.
