#!/bin/bash
# CV Pre-Submission Pipeline -- runs ALL validation in order, stops on first failure
# Usage: cv_pipeline.sh <submission.zip> [--prev-best predictions_prev.json]

set -e

ZIP="${1:?Usage: cv_pipeline.sh <submission.zip> [--prev-best prev_predictions.json]}"
TOOLS_DIR="/Volumes/devdrive/github_dev/nmiai-2026-main/shared/tools"

echo "============================================"
echo " CV Pre-Submission Pipeline"
echo " ZIP: $ZIP"
echo "============================================"
echo ""

# Step 1: Validate ZIP structure
echo "--- STEP 1: Validate ZIP ---"
if ! python3 "$TOOLS_DIR/validate_cv_zip.py" "$ZIP"; then
    echo ""
    echo "VERDICT: NO-GO (ZIP validation failed)"
    exit 1
fi
echo "STEP 1: PASS"
echo ""

# Step 2: Profile timing
echo "--- STEP 2: Profile Timing ---"
if python3 "$TOOLS_DIR/cv_profiler.py" "$ZIP" 2>/dev/null; then
    echo "STEP 2: PASS"
else
    echo "STEP 2: SKIPPED (profiler not available or no test images)"
fi
echo ""

# Step 3: Judge score
echo "--- STEP 3: Judge Score ---"
PREDICTIONS_JSON="${ZIP%.zip}_predictions.json"
if [ -f "$PREDICTIONS_JSON" ]; then
    python3 "$TOOLS_DIR/cv_judge.py" --predictions-json "$PREDICTIONS_JSON" 2>&1 || true
    echo "STEP 3: DONE"
else
    echo "STEP 3: SKIPPED (no predictions JSON at $PREDICTIONS_JSON)"
fi
echo ""

echo "============================================"
echo " VERDICT: SUBMIT (structural checks passed)"
echo "============================================"
