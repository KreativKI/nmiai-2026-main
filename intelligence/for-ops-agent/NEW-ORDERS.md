---
priority: HIGH
from: overseer
timestamp: 2026-03-20 19:10 CET
---

## New Orders: Support Active Agents

Your previous 5 phases are complete. New priorities:

### Phase 6: NLP Auto-Submitter Session
The NLP agent has only 4 submissions. ~146 unused today.
Verify the auto-submitter works end-to-end:
1. Check nlp_auto_submit.py has correct limits (DAILY_BUDGET=300, PER_TASK_LIMIT=10)
2. Run a test: `python3 shared/tools/nlp_auto_submit.py --max 1 --headed`
3. If auth issue: run `--login` first
4. Report results to intelligence/for-overseer/ops-status.md

### Phase 7: Leaderboard Snapshot
Run scrape_leaderboard.py to get current rankings for all 3 tracks.
Save snapshot to shared/tools/.leaderboard_snapshots/

### Phase 8: Merge Tools to Main
All shared tools must be accessible from main branch.
`cd /Volumes/devdrive/github_dev/nmiai-2026-main && git merge agent-ops && git push origin main`

Report after each phase to intelligence/for-overseer/ops-status.md.
