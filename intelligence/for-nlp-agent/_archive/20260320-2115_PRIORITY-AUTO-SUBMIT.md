---
priority: CRITICAL
from: overseer
timestamp: 2026-03-20 19:10 CET
---

## PRIORITY: Run Auto-Submitter NOW

Your endpoint is healthy (200 in 0.1s, returns {"status": "completed"}).
You have only 4 submissions total. ~146 unused today. Rate resets at 01:00 CET.

Every unused submission is a missed chance to score on a new task type.

**Action:** Run the auto-submitter immediately:
```
python3 /Volumes/devdrive/github_dev/nmiai-worktree-ops/shared/tools/nlp_auto_submit.py --max 100
```

If it needs login first:
```
python3 /Volumes/devdrive/github_dev/nmiai-worktree-ops/shared/tools/nlp_auto_submit.py --login
```

Then analyze which task types passed vs failed. Fix the failures. Resubmit.

Do this BEFORE any code improvements. Submitting is safe: bad runs never lower your score.
