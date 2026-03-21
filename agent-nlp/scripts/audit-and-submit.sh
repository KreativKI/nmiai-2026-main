#!/bin/bash
# NLP Audit-Then-Submit Pipeline
# Runs full QC audit first. Only submits if audit passes.
# This is the ONLY way to submit. Never bypass.
#
# Usage:
#   bash agent-nlp/scripts/audit-and-submit.sh [--max N] [--auto]
#   bash agent-nlp/scripts/audit-and-submit.sh --max 10 --auto
#   bash agent-nlp/scripts/audit-and-submit.sh --max 5          # interactive mode

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENDPOINT="https://tripletex-agent-795548831221.europe-west4.run.app"
AUTO_SUBMIT_SCRIPT="/Volumes/devdrive/github_dev/nmiai-worktree-ops/shared/tools/nlp_auto_submit.py"

# Parse args (pass through to auto-submitter)
SUBMIT_ARGS=""
MAX_SUBS=10
for arg in "$@"; do
    SUBMIT_ARGS="$SUBMIT_ARGS $arg"
    if [[ "$arg" == "--max" ]]; then
        shift_next=true
    elif [[ "${shift_next:-false}" == "true" ]]; then
        MAX_SUBS="$arg"
        shift_next=false
    fi
done

echo "============================================"
echo "  NLP AUDIT-THEN-SUBMIT PIPELINE"
echo "  Step 1: Run QC audit"
echo "  Step 2: Submit only if audit passes"
echo "  Max submissions: $MAX_SUBS"
echo "============================================"
echo ""

# --- STEP 1: RUN AUDIT ---
echo ">>> STEP 1: Running pre-submission audit..."
echo ""

if bash "$SCRIPT_DIR/pre-submit.sh" "$ENDPOINT"; then
    echo ""
    echo ">>> AUDIT PASSED. Proceeding to submit."
    echo ""
else
    echo ""
    echo ">>> AUDIT FAILED. BLOCKING SUBMISSION."
    echo ">>> Fix the issues above before submitting."
    echo ""
    exit 1
fi

# --- STEP 2: SUBMIT ---
echo ">>> STEP 2: Running auto-submitter..."
echo ""

# Activate venv
VENV_DIR="$SCRIPT_DIR/../.venv"
if [[ -f "$VENV_DIR/bin/activate" ]]; then
    source "$VENV_DIR/bin/activate"
fi

cd "$REPO_ROOT"
python3 "$AUTO_SUBMIT_SCRIPT" $SUBMIT_ARGS

echo ""
echo ">>> SUBMISSION COMPLETE."
echo ">>> Check logs: gcloud run services logs read tripletex-agent --region europe-west4 --project ai-nm26osl-1779 --limit 50"
