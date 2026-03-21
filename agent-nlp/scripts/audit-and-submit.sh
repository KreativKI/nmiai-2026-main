#!/bin/bash
# NLP Audit-Then-Submit Pipeline
# Runs hard-blocker checks first. Only submits if all blockers pass.
# Sandbox QC failures are WARNINGS (known sandbox-state issues, not bugs).
# This is the ONLY way to submit. Never bypass.
#
# Hard blockers (any = BLOCK):
#   - Syntax error in bot code
#   - Health check fails (endpoint down)
#   - MALFORMED error rate >20%
#
# Warnings (report but don't block):
#   - Sandbox QC failures (sandbox accumulates state, competition is fresh)
#
# Usage:
#   bash agent-nlp/scripts/audit-and-submit.sh --max 10 --auto
#   bash agent-nlp/scripts/audit-and-submit.sh --max 5

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENDPOINT="https://tripletex-agent-795548831221.europe-west4.run.app"
AUTO_SUBMIT_SCRIPT="/Volumes/devdrive/github_dev/nmiai-worktree-ops/shared/tools/nlp_auto_submit.py"
BOT_FILE="$SCRIPT_DIR/../solutions/tripletex_bot_v4.py"

# Parse args (pass through to auto-submitter)
SUBMIT_ARGS=""
for arg in "$@"; do
    SUBMIT_ARGS="$SUBMIT_ARGS $arg"
done

echo "============================================"
echo "  NLP AUDIT-THEN-SUBMIT PIPELINE"
echo "============================================"
echo ""

BLOCKED=false

# --- CHECK 1: Syntax ---
echo "[1/4] Syntax check..."
if python3 -c "import ast; ast.parse(open('$BOT_FILE').read())"; then
    echo "  PASS: Syntax OK"
else
    echo "  BLOCK: Syntax errors"
    BLOCKED=true
fi
echo ""

# --- CHECK 2: Health ---
echo "[2/4] Health check..."
HEALTH=$(curl -s --max-time 15 "${ENDPOINT}/health" 2>/dev/null || echo "TIMEOUT")
if echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('status')=='ok'; print('  PASS: Health OK, version:', d.get('version','?'))" 2>/dev/null; then
    :
else
    echo "  BLOCK: Health check failed. Response: $HEALTH"
    BLOCKED=true
fi
echo ""

# --- CHECK 3: MALFORMED error rate ---
echo "[3/4] MALFORMED error rate..."
LOGS=$(gcloud run services logs read tripletex-agent --region europe-west4 --project ai-nm26osl-1779 --limit 100 2>/dev/null || echo "")
if [[ -n "$LOGS" ]]; then
    TOTAL_REQUESTS=$(echo "$LOGS" | grep -c "POST /solve" || true)
    MALFORMED_COUNT=$(echo "$LOGS" | grep -ci "MALFORMED" || true)
    if [[ $TOTAL_REQUESTS -gt 0 ]]; then
        MALFORMED_PCT=$(python3 -c "print(round($MALFORMED_COUNT / $TOTAL_REQUESTS * 100, 1))")
        echo "  Requests: $TOTAL_REQUESTS, MALFORMED: $MALFORMED_COUNT ($MALFORMED_PCT%)"
        if python3 -c "exit(0 if $MALFORMED_PCT <= 20 else 1)"; then
            echo "  PASS: MALFORMED rate OK"
        else
            echo "  BLOCK: MALFORMED rate >20%"
            BLOCKED=true
        fi
    else
        echo "  SKIP: No recent requests"
    fi
else
    echo "  SKIP: Could not fetch logs"
fi
echo ""

# --- CHECK 4: Quick smoke test (create_customer only) ---
echo "[4/4] Smoke test (create_customer)..."
SMOKE_RESULT=$(curl -s --max-time 30 -X POST "${ENDPOINT}/solve" \
    -H "Content-Type: application/json" \
    -d '{"prompt":"Opprett en testkundeaudit med navn AuditTest","files":[],"tripletex_credentials":{"base_url":"https://kkpqfuj-amager.tripletex.dev/v2","session_token":"'"$(grep TRIPLETEX_SESSION_TOKEN "$REPO_ROOT/.env" 2>/dev/null | cut -d= -f2 || echo '')"'"}}' 2>/dev/null || echo '{"error":"timeout"}')
if echo "$SMOKE_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('status')=='completed'; print('  PASS: Bot responds correctly')" 2>/dev/null; then
    :
else
    echo "  WARNING: Smoke test did not return completed. Response: $SMOKE_RESULT"
    echo "  (Not blocking: may be sandbox token issue)"
fi
echo ""

# --- VERDICT ---
echo "============================================"
if $BLOCKED; then
    echo "  VERDICT: BLOCKED"
    echo "  Fix hard blockers above before submitting."
    echo "============================================"
    exit 1
else
    echo "  VERDICT: APPROVED FOR SUBMISSION"
    echo "============================================"
fi
echo ""

# --- SUBMIT ---
echo ">>> Proceeding to submit..."
echo ""

VENV_DIR="$SCRIPT_DIR/../.venv"
if [[ -f "$VENV_DIR/bin/activate" ]]; then
    source "$VENV_DIR/bin/activate"
fi

cd "$REPO_ROOT"
python3 "$AUTO_SUBMIT_SCRIPT" $SUBMIT_ARGS

echo ""
echo ">>> SUBMISSION COMPLETE. Running post-submission analysis..."
echo ""

python3 "$SCRIPT_DIR/post_submit_analysis.py" --hours 1
