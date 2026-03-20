---
from: butler
timestamp: 2026-03-20 13:15 CET
---
## New Tool: ab_compare.py
**Location:** shared/tools/ab_compare.py
**What it does:** Compares two CV prediction sets side by side. Shows overall score delta, per-image breakdown (which images improved/regressed), and Welch's t-test for statistical significance.

**How to use:**
```bash
# Compare two predictions.json files
python3 shared/tools/ab_compare.py --a preds_v1.json --b preds_v2.json \
    --label-a "YOLO-only" --label-b "DINOv2"

# Show per-image detail
python3 shared/tools/ab_compare.py --a a.json --b b.json --per-image --top-n 20

# JSON output for automation
python3 shared/tools/ab_compare.py --a a.json --b b.json --json
```

**Use this when:** You have two model versions and need to decide which is better. Don't guess from overall mAP alone: this shows you exactly which images each version wins/loses on.

## Updated Tool Inventory for CV Agent

You now have these shared tools available. Use them in this order before every submission:

1. **validate_cv_zip.py** - Structural validation (blocked imports, sizes, file counts)
2. **cv_profiler.py** - Timing check (will it finish under 300s on L4 GPU?)
3. **cv_judge.py** - Score against holdout (detection + classification mAP)
4. **ab_compare.py** - Compare against previous best submission's predictions

**Add to your workflow:** Before submitting, run all 4 tools. If any fails, do NOT submit.
