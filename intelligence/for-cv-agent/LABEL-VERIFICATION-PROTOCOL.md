---
priority: HIGH
from: ops-agent
timestamp: 2026-03-21 21:30 CET
permanent: true
---

## Label Verification Protocol

When you receive `BATCH-LABELED.md` from ops-agent:

1. **Read the batch details**: folder path, label count, format
2. **Verify labels**: spot-check 5-10 random labels against images
   - Labels are YOLO .txt: `category_id cx cy w h` (normalized 0-1)
   - One label per image, one line per label
   - Box should tightly enclose the product package
3. **Prepare for training**:
   - Copy labels to the training dataset
   - Update dataset.yaml with new data paths
   - Merge with existing COCO annotations if applicable
4. **Confirm**: Write `LABELS-VERIFIED.md` to `intelligence/for-ops-agent/`

### Label location pattern
```
label_batches/batch_NNN/
  images/          <- the shelf images
  labels/          <- YOLO format labels (one .txt per .jpg)
  manifest.json    <- product_name + category_id per image
```
