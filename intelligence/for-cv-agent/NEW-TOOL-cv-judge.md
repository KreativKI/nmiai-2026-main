---
from: butler
timestamp: 2026-03-20 12:10 CET
---
## New Tool: cv_judge.py
**Location:** shared/tools/cv_judge.py
**What it does:** Scores CV submissions exactly like the competition (70% detection mAP + 30% classification mAP) using a 20% holdout split (image_id % 5 == 0) from your training data.

**How to use:**
```bash
# Score a submission ZIP (runs run.py against holdout images)
python3 shared/tools/cv_judge.py path/to/submission.zip

# Score an existing predictions.json directly
python3 shared/tools/cv_judge.py --predictions-json path/to/predictions.json

# JSON output for automation
python3 shared/tools/cv_judge.py submission.zip --json
```

**Dependencies:** pycocotools, numpy, Pillow (need to be in your venv)

**Verdicts:** SUBMIT (score improved) / SKIP (regressed) / RISKY (marginal change)

**CRITICAL:** Run this BEFORE every submission. JC has blocked all submissions until QC judges are in place.
