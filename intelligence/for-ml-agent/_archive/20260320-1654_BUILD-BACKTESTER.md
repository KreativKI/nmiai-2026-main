---
priority: HIGH
from: overseer
timestamp: 2026-03-20 11:50 CET
self-destruct: after building and using backtester, delete
---

## Approved: Build Backtester (Option A), Then Use It

### Phase 1: Build backtester
- Apply current model to rounds 3-5 ground truth
- Compute what score we WOULD have gotten
- Test model changes offline without spending live queries
- Output: per-seed score, per-terrain-type KL breakdown, total predicted score
- Commit: "Phase 1: backtester tool for offline model evaluation"

### Phase 2: Use backtester to find weaknesses
- Run backtester on rounds 3-5
- Identify which terrain types and which spatial patterns have highest KL
- Find where cross-seed transfer breaks down
- Commit: "Phase 2: backtester analysis, identified weaknesses"

### Phase 3: Fix weaknesses and resubmit round 6 (if still open)
- Apply fixes from backtester analysis
- Verify improvement on backtester before submitting
- Resubmit round 6 if time allows
- Commit: "Phase 3: model improvements, resubmitted round 6"

### Phase 4: Build observation visualizer (Option B)
- Heatmap of query placement vs per-cell score
- Shows where stacking helped vs hurt
- Informs query strategy for future rounds
- Commit: "Phase 4: observation visualizer"

### Key Rule
The backtester becomes your QC gate. Never submit without running backtester first.
Log all backtester results in EXPERIMENTS.md.
