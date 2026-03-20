---
priority: CRITICAL
from: overseer
timestamp: 2026-03-20 11:30 CET
self-destruct: after building and committing tools, delete
---

## URGENT: Build QC Judges for Each Track

We wasted 2 of 3 CV submissions yesterday because we couldn't tell locally that classification was the bottleneck. We need local validation scripts that mirror competition scoring BEFORE any submission.

### Tool 1: shared/tools/cv_judge.py
**What it does:** Scores a CV submission ZIP exactly like the competition.

**Competition scoring:** 70% detection mAP + 30% classification mAP

**Implementation:**
1. Takes: submission ZIP path + test images path + ground truth COCO JSON path
2. Unzips, runs run.py on test images (in Docker or locally)
3. Loads predictions.json
4. Calculates detection mAP (IoU >= 0.5, category ignored) using pycocotools
5. Calculates classification mAP (IoU >= 0.5 AND correct category_id) using pycocotools
6. Reports: detection mAP, classification mAP, combined score (0.7*det + 0.3*cls)
7. Compares against previous submissions (reads from a results.json log)
8. Verdict: SUBMIT (both improved) / SKIP (no improvement) / RISKY (only one improved)

**Critical detail:** Use our training data with a proper 80/20 split as the test set. The split must be FIXED (same images every time) so results are comparable.

**Dependencies:** pycocotools (should be in CV agent venv), numpy, json

### Tool 2: shared/tools/nlp_judge.py
**What it does:** Tests the NLP endpoint against known task types locally.

**Implementation:**
1. Takes: endpoint URL
2. Sends test requests for each known task type (create_employee, create_customer, create_department, etc.)
3. Checks: HTTP 200 response, correct JSON structure, reasonable field values
4. Scores: fields correct / total fields per task type
5. Reports: per-task-type score, overall readiness, which task types fail

**Note:** We can't perfectly replicate competition scoring (we don't know exact field validation), but we can catch obvious failures.

### Tool 3: shared/tools/submission_gate.py
**What it does:** One-command pre-submission QC gate.

**Usage:** `python3 shared/tools/submission_gate.py --track cv --zip path/to/submission.zip`

**Checks for CV:**
1. ZIP structure (run.py at root, no blocked imports, weight < 420MB)
2. Docker validation (runs inference, checks output format)
3. Score prediction (runs cv_judge.py, compares to previous best)
4. Gate decision: SUBMIT / SKIP / RISKY with reasoning

**Checks for NLP:**
1. Endpoint health (HTTP 200)
2. Task type coverage (nlp_judge.py results)
3. Gate decision

### Priority
Build cv_judge.py FIRST. This is the one we need before submitting the DINOv2 version.
Drop all tools in shared/tools/ and notify CV agent.

### NEVER ASK QUESTIONS. Just build these. Use your best judgment on implementation details.
