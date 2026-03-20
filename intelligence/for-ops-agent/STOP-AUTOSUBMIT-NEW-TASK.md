---
priority: URGENT
from: overseer
timestamp: 2026-03-20 20:50 CET
---

## STOP: Do NOT run the NLP auto-submitter

The NLP agent owns their own submissions. You built the tool but you do NOT run it.
If you started it, stop it now.

## New Task: Code Review + Shared Tools

### Task 1: Review NLP v4 code
NLP agent built tripletex_bot_v4.py. Run Boris QC on it:
```
Read /Volumes/devdrive/github_dev/nmiai-worktree-nlp/agent-nlp/solutions/tripletex_bot_v4.py
```
Then spawn code-reviewer agent on it. Report issues to intelligence/for-nlp-agent/CODE-REVIEW.md

### Task 2: Review CV submission pipeline
CV has a submission.zip ready. Run the canary:
- Read shared/agents/cv-canary.md
- Audit the ZIP at /Volumes/devdrive/github_dev/nmiai-worktree-cv/agent-cv/submission.zip
Report results to intelligence/for-cv-agent/CANARY-RESULT.md

### Task 3: Merge all shared tools to main
```bash
cd /Volumes/devdrive/github_dev/nmiai-2026-main && git merge agent-ops && git push origin main
```

Report after each task to intelligence/for-overseer/ops-status.md
