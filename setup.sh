#!/bin/bash
# NM i AI 2026 -- Competition Repo Setup
# Run this ONCE before competition day
# Creates 3 agent workspaces with venvs and shared templates

set -e

BASE="/Volumes/devdrive/github_dev/nmiai_multiagent"
cd "$BASE"

echo "Setting up NM i AI 2026 multi-agent competition repo..."

# Create agent workspaces
for track in cv ml nlp; do
  echo "Creating agent-${track} workspace..."
  mkdir -p "agent-${track}/solutions"
  mkdir -p "agent-${track}/data"
  mkdir -p "agent-${track}/models"
  mkdir -p "agent-${track}/tests"
  # Map short track names to schema enum values
  case "$track" in
    cv) schema_track="computer-vision" ;;
    ml) schema_track="machine-learning" ;;
    nlp) schema_track="nlp" ;;
  esac
  echo "{\"agent\":\"agent-${track}\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"track\":\"${schema_track}\",\"phase\":\"waiting\",\"state\":\"waiting\",\"approach\":\"\",\"confidence\":0,\"local_score\":0,\"best_submitted_score\":0,\"submissions_count\":0,\"blockers\":[],\"hours_since_improvement\":0,\"rules_last_read\":\"\"}" > "agent-${track}/status.json"
  touch "agent-${track}/MEMORY.md"
  touch "agent-${track}/rules.md"
  touch "agent-${track}/plan.md"
  # Copy CLAUDE.md template (will be customized per track)
  if [ -f "templates/CLAUDE-TRACK.md" ]; then
    sed "s/{TRACK_NAME}/${track}/g" templates/CLAUDE-TRACK.md > "agent-${track}/CLAUDE.md"
  fi
done

# Create intelligence folders
echo "Creating intelligence folder structure..."
mkdir -p intelligence/{cross-track,for-cv-agent,for-ml-agent,for-nlp-agent,for-matilda,for-jc}

# Create shared utilities and templates
echo "Creating shared directories..."
mkdir -p shared/templates
mkdir -p shared/models
mkdir -p shared/api

# Create submissions archive
mkdir -p submissions

# Create templates directory
mkdir -p templates

echo ""
echo "=== Setup complete ==="
echo "3 agent workspaces: agent-cv/, agent-ml/, agent-nlp/"
echo "Intelligence folder: intelligence/"
echo "Shared resources: shared/"
echo ""
echo "Next steps:"
echo "  1. Create Python venvs per agent (run setup-venvs.sh)"
echo "  2. Verify templates in templates/"
echo "  3. Pre-download models to shared/models/"
echo ""
echo "To create venvs with dependencies (takes ~5 min):"
echo "  bash setup-venvs.sh"
