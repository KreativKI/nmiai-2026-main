#!/bin/bash
# NM i AI 2026 -- Create Python venvs with dependencies
# Separated from setup.sh because venv creation takes time
# Run AFTER setup.sh

set -e
trap 'echo "ERROR: failed at line $LINENO in agent-${track:-unknown}"' ERR

BASE="/Volumes/devdrive/github_dev/nmiai_multiagent"
cd "$BASE"

echo "Creating Python venvs for each agent workspace..."
echo "This takes ~5 minutes depending on network speed."
echo ""

for track in cv ml nlp; do
  echo "=== agent-${track} ==="
  cd "$BASE/agent-${track}"

  # Use Python 3.13 (3.14 has sentence-transformers hang bug)
  /Volumes/DevDrive/homebrew/bin/python3.13 -m venv .venv
  PIP="$BASE/agent-${track}/.venv/bin/pip"

  "$PIP" install --upgrade pip --quiet

  # Core ML packages (all tracks need these)
  "$PIP" install --quiet \
    scikit-learn \
    xgboost \
    lightgbm \
    catboost \
    pandas \
    numpy \
    scipy \
    matplotlib \
    optuna

  # Deep learning (CPU by default, GPU via Vertex)
  "$PIP" install --quiet \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

  # NLP / transformers
  "$PIP" install --quiet \
    transformers \
    sentence-transformers

  # API clients
  "$PIP" install --quiet \
    anthropic \
    google-generativeai \
    openai

  # Networking
  "$PIP" install --quiet \
    aiohttp \
    websockets \
    requests

  # CV-specific (all agents get it, lightweight)
  "$PIP" install --quiet \
    opencv-python-headless \
    Pillow \
    ultralytics

  echo "  Done: agent-${track}/.venv"
  cd "$BASE"
done

echo ""
echo "=== All venvs created ==="
echo "Activate with: source agent-{cv,ml,nlp}/.venv/bin/activate"
