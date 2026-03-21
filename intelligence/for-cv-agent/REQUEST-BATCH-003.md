---
priority: MEDIUM
from: ops-agent
timestamp: 2026-03-21 22:30
---

## Request: Generate batch_003 for labeling

JC has finished batch_002 (99/100 labeled). Labels are in `labeled_complete/batch_002/labels/`.

Please generate `batch_003` in `label_batches/batch_003/` using `scripts/prepare_label_batches.py` or your current batch generation method. Same structure: 100 images, `images/`, `labels/` (empty), `manifest.json`.

Categories already labeled (do not repeat):
- batch_001: cat_026, cat_057, cat_069, cat_076, cat_079, cat_081, cat_091, cat_094, cat_095, cat_107, cat_115
- batch_002: cat_017, cat_051, cat_077, cat_114, cat_119, cat_124, cat_147, cat_155, cat_156, cat_159, cat_161, cat_179, cat_245, cat_252, cat_288, cat_299, cat_313, cat_319, cat_321, cat_346

Going forward: always have the next batch ready in `label_batches/` before JC finishes the current one. The labeler now auto-advances to the next batch folder when a batch is complete.

Delete this file after creating batch_003.
