---
from: butler
timestamp: 2026-03-20 12:10 CET
---
## New Tool: ml_judge.py
**Location:** shared/tools/ml_judge.py
**What it does:** Validates ML predictions (shape, floors, normalization) and scores against ground truth using competition formula: score = max(0, min(100, 100 * exp(-3 * weighted_KL)))

**How to use:**
```bash
# Validate only (no ground truth)
python3 shared/tools/ml_judge.py predictions.json

# Validate + score against ground truth
python3 shared/tools/ml_judge.py predictions.json --ground-truth ground_truth.json

# Auto-fix floors and normalization
python3 shared/tools/ml_judge.py predictions.json --fix --output fixed.json

# JSON output
python3 shared/tools/ml_judge.py predictions.json --json
```

**Checks:**
- Shape: 40x40x6 per seed, 5 seeds required
- Floor: all probabilities >= 0.01 (zero = infinite KL)
- Normalization: each cell sums to ~1.0
- No NaN/inf values

**Verdicts:** SUBMIT / SKIP / RISKY / VALIDATION_ERROR / VALID (no GT)

**CRITICAL:** Run this BEFORE every submission.
