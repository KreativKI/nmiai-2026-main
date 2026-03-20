---
priority: CRITICAL
from: overseer
timestamp: 2026-03-20 20:30 CET
---

## Fix Your Plan: Wrong Numbers + Too Conservative

### 1. Rate limits are WRONG in your plan.md
Your plan says "5 submissions per task type per day" and "~150 total per day."
CORRECT numbers (verified from platform): **10 per task type, 300 total per day.**
Update plan.md NOW.

### 2. "100% correctness before submitting" is WRONG strategy
Bad runs NEVER lower your score. Every submission is safe. You should be submitting constantly to discover which task types work and which don't. Perfection before submission wastes your 300/day budget.

Fix your plan to: "Submit frequently. Analyze failures. Fix. Resubmit."

### 3. Deploy v4 and run auto-submitter NOW
```bash
# Deploy v4
gcloud run deploy tripletex-agent --source . --region europe-west4 --allow-unauthenticated --memory 1Gi --timeout 300 --quiet

# Run auto-submitter (from ops worktree where playwright is installed)
cd /Volumes/devdrive/github_dev/nmiai-worktree-ops
agent-ops/.venv/bin/python3 shared/tools/nlp_auto_submit.py --auto --max 100
```

### 4. STATUS REPORT
After each phase, write 3 lines to:
`/Volumes/devdrive/github_dev/nmiai-2026-main/intelligence/for-overseer/nlp-status.md`
Format: what you did, score delta, next action.
