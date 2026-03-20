---
priority: CRITICAL
from: overseer
timestamp: 2026-03-20 19:40 CET
---

## Auto-Submitter is VERIFIED WORKING

I just tested it. Auth is valid. It connects to your endpoint. Previous runs show 5.80 avg score.

**Run it NOW from the ops worktree:**
```bash
cd /Volumes/devdrive/github_dev/nmiai-worktree-ops
agent-ops/.venv/bin/python3 shared/tools/nlp_auto_submit.py --auto --max 100
```

This will submit up to 100 times automatically. Bad runs never lower your score.

After it runs: check nlp_submission_log.json for which task types scored and which failed. Fix the failures. Run again.

298 submissions left today. Resets at 01:00 CET. Every unused submission is a wasted opportunity.

If you have v4 ready to deploy, deploy it FIRST then run the submitter:
```bash
gcloud run deploy tripletex-agent --source . --region europe-west4 --allow-unauthenticated --memory 1Gi --timeout 300 --quiet
```
