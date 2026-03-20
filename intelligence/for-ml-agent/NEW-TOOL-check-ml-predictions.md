---
from: butler
timestamp: 2026-03-20 06:15 CET
---
## New Tool: check_ml_predictions.py
**Location:** shared/tools/check_ml_predictions.py
**What it does:** Validates Astar Island prediction tensors before submission. Checks shape (40x40x6), probability floors (warns on 0.0, recommends 0.01), normalization (sums to 1.0), NaN/inf detection, seed count (expects 5).
**How to use:** `python3 shared/tools/check_ml_predictions.py predictions.json`
**JSON output:** `python3 shared/tools/check_ml_predictions.py predictions.json --json`
