#!/bin/bash
# Local Docker build + run for testing (uses OrbStack)
# Usage: ./scripts/local-run.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Building Docker image..."
docker build -t tripletex-agent:local "$PROJECT_DIR"

echo "Stopping any existing container..."
docker rm -f tripletex-agent-local 2>/dev/null || true

echo "Starting container on port 8080..."
docker run -d \
  --name tripletex-agent-local \
  -p 8080:8080 \
  -e GCP_PROJECT=ai-nm26osl-1779 \
  -e GCP_LOCATION=europe-west4 \
  -e GEMINI_MODEL=gemini-2.5-flash \
  -e GOOGLE_APPLICATION_CREDENTIALS=/tmp/adc.json \
  -v "$HOME/.config/gcloud/application_default_credentials.json:/tmp/adc.json:ro" \
  tripletex-agent:local

echo "Waiting for startup..."
for i in $(seq 1 10); do
  if curl -s http://localhost:8080/health > /dev/null 2>&1; then
    echo "Ready: http://localhost:8080/solve"
    exit 0
  fi
  sleep 1
done

echo "Failed to start. Logs:"
docker logs tripletex-agent-local
exit 1
