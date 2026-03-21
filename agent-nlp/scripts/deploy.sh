#!/bin/bash
# Single-command deploy: syntax check -> deploy -> health check
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BOT="$SCRIPT_DIR/../solutions/tripletex_bot_v4.py"
DEPLOY_DIR="$SCRIPT_DIR/.."
ENDPOINT="https://tripletex-agent-795548831221.europe-west4.run.app"

echo "=== DEPLOY PIPELINE ==="

echo "[1/3] Syntax check..."
python3 -c "import ast; ast.parse(open('$BOT').read())"
echo "  OK"

echo "[2/3] Deploying to Cloud Run..."
cd "$DEPLOY_DIR"
gcloud run deploy tripletex-agent \
  --source . \
  --region europe-west4 \
  --allow-unauthenticated \
  --memory 1Gi \
  --timeout 300 \
  --project ai-nm26osl-1779 \
  --quiet

echo "[3/3] Health check..."
HEALTH=$(curl -s --max-time 15 "$ENDPOINT/health")
echo "  $HEALTH"

echo ""
echo "=== DEPLOY COMPLETE ==="
