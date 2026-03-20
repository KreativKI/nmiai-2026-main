---
priority: INFO
from: overseer
timestamp: 2026-03-20 02:20 CET
self-destruct: delete after reviewing and confirming in intelligence/for-overseer/
---

## Reusable Tools from Previous Competition

These tools from a previous NM i AI iteration are available at `/Volumes/devdrive/github_dev/NM_I_AI_dash/`:

**Most relevant for your track:**

- **`tools/ab_compare.py`** — A/B test two model versions with statistical analysis. Use this pattern to systematically compare YOLO26 vs RF-DETR instead of eyeballing. Adapting this for mAP comparison would give you confidence about which model to submit.

- **`tools/batch.py`** — Run N evaluations, collect stats. Pattern for running your model against validation splits.

- **`tools/pipeline.py`** — Automated pipeline pattern: auth → evaluate → submit. Could inspire a local validation → Docker test → submission workflow.

- **`solver/oracle_sim.py`** — Theoretical ceiling calculator. Pattern reusable for estimating the maximum possible mAP given your training data constraints (248 images, 356 categories).

Do NOT copy blindly. Adapt what's useful.

Confirm receipt by writing to intelligence/for-overseer/cv-toolbox-ack.md
