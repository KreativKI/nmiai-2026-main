#!/bin/bash
# NM i AI 2026 -- Create Python venvs with dependencies
# Separated from setup.sh because venv creation takes time
# Run AFTER setup.sh

set -e

BASE="/Volumes/devdrive/github_dev/nmiai_multiagent"
cd "$BASE"

echo "Creating Python venvs for each agent workspace..."
echo "This takes ~5 minutes depending on network speed."
echo ""

for track in cv ml nlp; do
  echo "=== agent-${track} ==="
  cd "$BASE/agent-${track}"

  python3 -m venv .venv
  source .venv/bin/activate

  pip install --upgrade pip --quiet

  # Core ML packages (all tracks need these)
  pip install --quiet \
    scikit-learn \
    xgboost \
    lightgbm \
    pandas \
    numpy \
    matplotlib

  # Deep learning (CPU by default, GPU via Vertex)
  pip install --quiet \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

  # NLP / transformers
  pip install --quiet \
    transformers \
    sentence-transformers

  # API clients
  pip install --quiet \
    anthropic \
    google-generativeai \
    openai

  # Networking
  pip install --quiet \
    aiohttp \
    websockets \
    requests

  # CV-specific (all agents get it, lightweight)
  pip install --quiet \
    opencv-python-headless \
    Pillow \
    ultralytics

  deactivate
  echo "  Done: agent-${track}/.venv"
  cd "$BASE"
done

echo ""
echo "=== All venvs created ==="
echo "Activate with: source agent-{cv,ml,nlp}/.venv/bin/activate"
