---
from: cv-agent
timestamp: 2026-03-21 16:20 CET
---

## CV Track Status

**Score:** 0.6584 (leaderboard). 4 submissions left today.

**In progress:**
- Gemini 3.1 Flash shelf generation: 344/794 images (100% success, 2 VMs)
- cv-train-4 finishes ~17:15, cv-train-1 finishes ~19:45
- JC test-labeled 10 images: 90/100 quality, workflow validated
- Butler building labeling GUI
- Retrain pipeline, auto-label scripts, submission builder all ready

**Analysis completed:**
- Conf sweep: optimal 0.28 (marginal +0.001)
- IOU sweep: optimal 0.45 (negligible)
- Confusion analysis: top errors are similar-product variants (Evergood coffees, egg cartons, knekkebrød)
- Grounding DINO: tested and rejected (fails on Norwegian product names)
- Auto-label quality: 93% detect, 92% classify on well-known, 37% on rare

**Next:** Download batch_001 (100 images) when cv-train-4 finishes. JC labels. YOLO second-pass auto-labels other products. Retrain overnight. Submit Sunday morning.

**GCP VMs:** cv-train-1 (generating), cv-train-4 (generating), ml-churn (ML agent). cv-train-3 deleted.
