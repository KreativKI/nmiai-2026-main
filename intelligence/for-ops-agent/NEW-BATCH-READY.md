---
priority: HIGH
from: cv-agent
timestamp: 2026-03-21 20:25 CET
---

## New Batch Ready for Labeling

**Batch:** batch_002
**Path:** /Volumes/devdrive/github_dev/nmiai-worktree-cv/agent-cv/label_batches/batch_002/
**Images:** 100
**Manifest:** manifest.json in same folder
**Products:** Somewhat-known categories (3-5 training annotations each)

JC draws one tight bounding box per image around the target product.
Labels go in labels/ folder as YOLO .txt files.

When done, notify CV agent at:
`intelligence/for-cv-agent/BATCH-LABELED.md`
