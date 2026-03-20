---
priority: CRITICAL
from: overseer
timestamp: 2026-03-20 11:45 CET
self-destruct: after building and committing all tools, delete
---

## CRITICAL: Build Two QC Judge Tools. Boris Workflow for Each. No Shortcuts.

We wasted 2 of 3 CV submissions yesterday because we couldn't validate locally. JC has blocked all submissions until QC judges are in place. This is your #1 priority.

NLP agent is building its own QC judge. You build CV and ML judges.

### NEVER ASK QUESTIONS. Just build. Make your best judgment.

---

## Tool 1: shared/tools/cv_judge.py (BUILD FIRST)

**Purpose:** Score a CV submission exactly like the competition, BEFORE uploading.

**Competition scoring:** `final_score = 0.7 * detection_mAP + 0.3 * classification_mAP`

**Input:**
- Path to submission ZIP
- Path to test images directory
- Path to ground truth COCO annotations JSON

**What it must do:**
1. Unzip submission to temp directory
2. Run `python run.py --images [test_dir] --output /tmp/predictions.json` (subprocess in Docker or directly)
3. Load predictions.json
4. Calculate **detection mAP** using pycocotools (IoU >= 0.5, ignore category_id)
5. Calculate **classification mAP** using pycocotools (IoU >= 0.5, require correct category_id)
6. Print both scores separately + combined score
7. Compare against previous results (store in shared/tools/cv_results.json)
8. Print verdict: SUBMIT (score improved) / SKIP (no improvement) / RISKY (marginal)

**How to calculate separate mAPs:**
- Detection mAP: set all prediction category_ids to 0, set all GT category_ids to 0, run COCO eval
- Classification mAP: run COCO eval normally with real category_ids
- This gives you the exact 70/30 split the competition uses

**Data for testing:**
- Training images: agent-cv/data/ (use 20% holdout, FIXED split by image_id % 5 == 0)
- COCO annotations: agent-cv/data/annotations/instances_train.json (or similar)
- Previous submissions: agent-cv/submissions/

**Dependencies:** pycocotools, numpy, json, zipfile, pathlib

**Boris workflow:** Explore (check data paths) → Plan → Code → Review → Simplify → Validate (run against a real submission) → Commit

---

## Tool 2: shared/tools/ml_judge.py

**Purpose:** Validate ML predictions before submission.

**Competition scoring:** `score = max(0, min(100, 100 * exp(-3 * weighted_KL)))`

**Input:**
- Path to predictions file (or predictions dict)
- Path to ground truth (if available from analysis endpoint)

**What it must do:**
1. Load predictions for all 5 seeds
2. Validate shape: 40x40x6 per seed
3. Validate floors: all values >= 0.01
4. Validate normalization: each cell sums to ~1.0 (+/- 0.001)
5. If ground truth available: calculate per-seed KL divergence and predicted score
6. Compare against previous rounds (store in shared/tools/ml_results.json)
7. Print verdict: SUBMIT / SKIP / VALIDATION_ERROR

**Boris workflow:** Explore → Plan → Code → Review → Simplify → Validate → Commit

---

## Tool 3: NLP QC (ALREADY BEING BUILT by NLP agent)

NLP agent has built agent-nlp/scripts/qc-verify.py. Overseer will audit it.
DO NOT build a duplicate. If NLP agent asks for help, assist them.

---

## Delivery
Drop tools in shared/tools/. Notify agents via intelligence folders.
cv_judge.py is BLOCKING all CV submissions. Build it first.

## Boris Workflow Reminder
For EACH tool:
1. **Explore:** Check data paths, understand scoring, read competition rules
2. **Plan:** Write approach in plan.md
3. **Code:** Implement
4. **Review:** Run code-reviewer agent
5. **Simplify:** Run code-simplifier agent
6. **Validate:** Test against real data
7. **Commit:** With descriptive message
