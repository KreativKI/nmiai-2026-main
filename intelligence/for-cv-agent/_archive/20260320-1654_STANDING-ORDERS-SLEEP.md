---
priority: HIGH
from: overseer
timestamp: 2026-03-20 05:05 CET
self-destruct: delete when JC wakes up and confirms new orders
---

## Standing Orders: JC Is Sleeping

v2 ZIP passed overseer QC. JC will upload when awake.

### FIRST: Update Your plan.md

Before doing any work, update your plan.md with a phased work plan. Use the phases below as a starting point but adapt based on what you see (training progress, errors, etc.).

**Structure your plan.md like this:**
```
## Current Phase: [N]
## Phases
### Phase 1: [name] — Status: [done/active/pending]
- Tasks...
- Commit: "Phase 1: [description]"

### Phase 2: [name] — Status: [pending]
...
```

Update the "Current Phase" line as you progress. This way if your context resets, the next session reads plan.md and knows exactly where you left off.

**Commit plan.md first:** `git add plan.md && git commit -m "Updated phased plan for sleep mode" && git push origin agent-cv`

### Suggested Phases (adapt as needed)

**Phase 1:** Monitor YOLO26m on cv-train-1 (SSH, check epoch/mAP50). If > 0.945: export ONNX, build ZIP.
**Phase 2:** Monitor RF-DETR on cv-train-2. Same criteria.
**Phase 3:** Research classification boost (CLIP/SigLIP on detected crops using 327 reference images).
**Phase 4:** Build comparison ZIPs for any models that beat 0.945. Docker validate each.
**Phase 5:** Write sleep report to intelligence/for-overseer/cv-sleep-report.md.

After Phase 5: loop back to Phase 1. Check training every 30 min.

### Key Rules
- Commit after EVERY phase (crash insurance)
- Update status.json after every phase
- Do NOT upload any ZIPs (JC does that)
- Check intelligence/for-cv-agent/ at :10 and :40 past each hour
