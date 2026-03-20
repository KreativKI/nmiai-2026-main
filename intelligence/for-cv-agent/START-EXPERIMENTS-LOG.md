---
priority: CRITICAL
from: overseer
timestamp: 2026-03-20 06:30 CET
self-destruct: after creating EXPERIMENTS.md, delete
---

## Create agent-cv/EXPERIMENTS.md NOW

Read intelligence/cross-track/EXPERIMENT-LOG-RULE.md for the format.

Backfill these results immediately:

1. YOLO11m v2 (04:55) -> 0.5735. Baseline.
2. YOLO11m v3 TTA (05:30) -> 0.5756. TTA barely helps.
3. Ensemble v1 YOLO11m+YOLO26m WBF (06:00) -> 0.5756. More detection models don't help.
4. YOLO26m solo: mAP50=0.914 val (below YOLO11m 0.945). Not submitted.
5. RF-DETR: epoch ~39, mAP50=0.572 val. Still training.

**Key conclusion to record:** Detection is NOT the bottleneck. Classification IS. All future work must focus on classification (DINOv2 + reference images).

Add EXPERIMENTS.md to your session startup protocol in CLAUDE.md.
Commit: "Add EXPERIMENTS.md with backfilled results"
