---
priority: HIGH
from: overseer
timestamp: 2026-03-20 05:10 CET
self-destruct: after reading, save to MEMORY.md then delete
---

## YOLO11m v2 Score: 0.5735

Submitted 04:55, scored in 14.2s. Score = 0.5735 (combined 70% detection + 30% classification).

### Analysis
- Local mAP50 was 0.945 but that's detection-only
- If detection mAP50 ≈ 0.945 on competition data: 0.945 * 0.7 = 0.66 from detection
- That means classification is contributing: (0.5735 - 0.66) / 0.3 ≈ negative, so detection score on competition test set is lower than local eval
- More likely: competition test set is harder than our validation split
- 14.2s inference = well within 300s timeout

### What This Means
- We have a working baseline at 0.5735
- 9 submissions remaining today
- Need to improve both detection AND classification
- Classification boost (CLIP/SigLIP on crops) could help significantly

### JC wants to explore parallel training of other models on GCP
Overseer is researching options now. Stand by for new training orders.
