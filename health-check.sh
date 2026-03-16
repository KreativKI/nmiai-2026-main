#!/bin/bash
# NM i AI 2026 -- Pre-flight health check
# Run this on Thursday before competition to verify everything works.

trap 'echo "FAIL at line $LINENO"' ERR

BASE="/Volumes/devdrive/github_dev/nmiai_multiagent"
cd "$BASE"
PASS=0
FAIL=0

check() {
  if eval "$2" > /dev/null 2>&1; then
    echo "  OK  $1"
    PASS=$((PASS+1))
  else
    echo "  FAIL $1"
    FAIL=$((FAIL+1))
  fi
}

echo "=== NM i AI 2026 Health Check ==="
echo ""

echo "--- Repo ---"
check "Git repo valid" "git status"
check "Remote configured" "git remote get-url origin"
check "Main branch clean" "test -z \"\$(git status --porcelain)\""

echo ""
echo "--- Agent Workspaces ---"
for track in cv ml nlp; do
  check "agent-${track}/CLAUDE.md exists" "test -f agent-${track}/CLAUDE.md"
  check "agent-${track}/rules.md exists" "test -f agent-${track}/rules.md"
  check "agent-${track}/status.json exists" "test -f agent-${track}/status.json"
  check "agent-${track}/MEMORY.md exists" "test -f agent-${track}/MEMORY.md"
  check "agent-${track}/plan.md exists" "test -f agent-${track}/plan.md"
  check "agent-${track}/solutions/ exists" "test -d agent-${track}/solutions"
done

echo ""
echo "--- Python Venvs ---"
for track in cv ml nlp; do
  check "agent-${track}/.venv exists" "test -d agent-${track}/.venv"
  check "agent-${track} torch import" "agent-${track}/.venv/bin/python -c 'import torch'"
  check "agent-${track} sklearn import" "agent-${track}/.venv/bin/python -c 'import sklearn'"
  check "agent-${track} xgboost import" "agent-${track}/.venv/bin/python -c 'import xgboost'"
  check "agent-${track} transformers import" "agent-${track}/.venv/bin/python -c 'import transformers'"
  check "agent-${track} anthropic import" "agent-${track}/.venv/bin/python -c 'import anthropic'"
done

echo ""
echo "--- Intelligence Sharing ---"
check "intelligence/ exists" "test -d intelligence"
check "intelligence/for-cv-agent/ exists" "test -d intelligence/for-cv-agent"
check "intelligence/for-ml-agent/ exists" "test -d intelligence/for-ml-agent"
check "intelligence/for-nlp-agent/ exists" "test -d intelligence/for-nlp-agent"
check "intelligence/for-matilda/ exists" "test -d intelligence/for-matilda"
check "intelligence/for-jc/ exists" "test -d intelligence/for-jc"
check "intelligence/cross-track/ exists" "test -d intelligence/cross-track"

echo ""
echo "--- Worktrees ---"
for wt in cv ml nlp; do
  WT="/Volumes/devdrive/github_dev/nmiai-worktree-${wt}"
  check "worktree-${wt} exists" "test -d ${WT}"
  check "worktree-${wt} intel symlink" "test -L ${WT}/intelligence"
  check "worktree-${wt} settings" "test -f ${WT}/.claude/settings.local.json"
done

echo ""
echo "--- Shared Resources ---"
check "shared/templates/ has baselines" "test \$(ls shared/templates/*.py 2>/dev/null | wc -l) -ge 5"
check "shared/stats.py exists" "test -f shared/stats.py"
check "shared/models/ exists" "test -d shared/models"

echo ""
echo "--- Templates ---"
check "CLAUDE-TRACK.md" "test -f templates/CLAUDE-TRACK.md"
check "RULES-TEMPLATE.md" "test -f templates/RULES-TEMPLATE.md"
check "COMMUNICATION-PROTOCOL.md" "test -f templates/COMMUNICATION-PROTOCOL.md"

echo ""
echo "--- MPS (Apple Silicon GPU) ---"
check "MPS available" "agent-cv/.venv/bin/python -c 'import torch; assert torch.backends.mps.is_available()'"

echo ""
echo "========================================="
echo "Results: ${PASS} passed, ${FAIL} failed"
if [ $FAIL -eq 0 ]; then
  echo "ALL CHECKS PASSED. Ready for competition."
else
  echo "SOME CHECKS FAILED. Fix before competition."
fi
echo "========================================="
