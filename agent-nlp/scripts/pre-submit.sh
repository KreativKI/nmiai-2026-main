#!/bin/bash
# NLP Pre-Submission Pipeline
# Runs all checks before submitting to competition.
# Exit 0 = READY TO SUBMIT, Exit 1 = BLOCKED
#
# Usage:
#   bash agent-nlp/scripts/pre-submit.sh [endpoint]
#   bash agent-nlp/scripts/pre-submit.sh [endpoint] --tier2

set -euo pipefail

# Activate venv if available
VENV_DIR="$(cd "$(dirname "$0")/.." && pwd)/.venv"
if [[ -f "$VENV_DIR/bin/activate" ]]; then
    source "$VENV_DIR/bin/activate"
fi

ENDPOINT="${1:-https://tripletex-agent-795548831221.europe-west4.run.app}"
TIER2=false
if [[ "${2:-}" == "--tier2" ]]; then
    TIER2=true
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BLOCKED=false

echo "============================================"
echo "  NLP PRE-SUBMISSION PIPELINE"
echo "  Endpoint: $ENDPOINT"
echo "  Tier 2:   $TIER2"
echo "============================================"
echo ""

# --- Step 1: Syntax check ---
echo "[1/5] Syntax check..."
if python3 -c "import ast; ast.parse(open('${SCRIPT_DIR}/../solutions/tripletex_bot_v4.py').read())"; then
    echo "  PASS: Syntax OK"
else
    echo "  FAIL: Syntax errors found"
    BLOCKED=true
fi
echo ""

# --- Step 2: Health check ---
echo "[2/5] Health check..."
HEALTH=$(curl -s --max-time 15 "${ENDPOINT}/health" 2>/dev/null || echo "TIMEOUT")
if echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('status')=='ok'; print('  PASS: Health OK, version:', d.get('version','unknown'))" 2>/dev/null; then
    :
else
    echo "  FAIL: Health check failed. Response: $HEALTH"
    BLOCKED=true
fi
echo ""

# --- Step 3: QC Tier 1 ---
echo "[3/5] QC Tier 1 (8 task types)..."
QC_OUTPUT=$(python3 "${SCRIPT_DIR}/qc-verify.py" "$ENDPOINT" 2>&1)
QC_EXIT=$?
echo "$QC_OUTPUT" | tail -20

# Parse pass/fail counts
PASS_COUNT=$(echo "$QC_OUTPUT" | grep -c "PASS" || true)
FAIL_COUNT=$(echo "$QC_OUTPUT" | grep -c "FAIL" || true)

if [[ $QC_EXIT -ne 0 ]] || [[ $FAIL_COUNT -gt 0 ]]; then
    echo "  BLOCKED: QC Tier 1 has failures ($FAIL_COUNT FAIL)"
    BLOCKED=true
else
    echo "  PASS: QC Tier 1 all passed ($PASS_COUNT PASS)"
fi
echo ""

# --- Step 4: QC Tier 2 (optional) ---
if $TIER2; then
    echo "[4/5] QC Tier 2 (extended tests)..."
    QC2_OUTPUT=$(python3 "${SCRIPT_DIR}/qc-verify.py" "$ENDPOINT" --tier2 2>&1)
    QC2_EXIT=$?
    echo "$QC2_OUTPUT" | tail -20

    T2_FAIL=$(echo "$QC2_OUTPUT" | grep -c "FAIL" || true)
    if [[ $QC2_EXIT -ne 0 ]] || [[ $T2_FAIL -gt 0 ]]; then
        echo "  WARNING: QC Tier 2 has failures ($T2_FAIL FAIL)"
        # Don't block on Tier 2 failures, just warn
    else
        echo "  PASS: QC Tier 2 all passed"
    fi
    echo ""
else
    echo "[4/5] QC Tier 2: SKIPPED (use --tier2 to enable)"
    echo ""
fi

# --- Step 5: MALFORMED rate check ---
echo "[5/5] MALFORMED error rate check..."
LOGS=$(gcloud run services logs read tripletex-agent --region europe-west4 --project ai-nm26osl-1779 --limit 100 2>/dev/null || echo "")
if [[ -z "$LOGS" ]]; then
    echo "  SKIP: Could not fetch Cloud Run logs"
else
    TOTAL_REQUESTS=$(echo "$LOGS" | grep -c "POST /solve" || true)
    MALFORMED_COUNT=$(echo "$LOGS" | grep -ci "MALFORMED" || true)

    if [[ $TOTAL_REQUESTS -gt 0 ]]; then
        MALFORMED_PCT=$(python3 -c "print(round($MALFORMED_COUNT / $TOTAL_REQUESTS * 100, 1))")
        echo "  Requests: $TOTAL_REQUESTS, MALFORMED: $MALFORMED_COUNT ($MALFORMED_PCT%)"
        if python3 -c "exit(0 if $MALFORMED_PCT <= 20 else 1)"; then
            echo "  PASS: MALFORMED rate within threshold"
        else
            echo "  BLOCKED: MALFORMED rate >20%"
            BLOCKED=true
        fi
    else
        echo "  SKIP: No recent /solve requests in logs"
    fi
fi
echo ""

# --- VERDICT ---
echo "============================================"
if $BLOCKED; then
    echo "  VERDICT: BLOCKED -- fix issues above"
    echo "============================================"
    exit 1
else
    echo "  VERDICT: READY TO SUBMIT"
    echo "============================================"
    exit 0
fi
