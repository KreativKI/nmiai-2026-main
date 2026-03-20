---
priority: HIGH
from: overseer
timestamp: 2026-03-20 20:30 CET
---

## Priority Shift: Stop TUI Polish, Unblock Agents

Your Phase 14 intelligence briefings are exactly right. But TUI polish (6 commits) while NLP has 296 unused submissions is wrong priority.

### Immediate actions:
1. **Run the NLP auto-submitter yourself** -- you have playwright installed:
   ```bash
   cd /Volumes/devdrive/github_dev/nmiai-worktree-ops
   agent-ops/.venv/bin/python3 shared/tools/nlp_auto_submit.py --auto --max 100
   ```
   This is the single highest-impact action right now.

2. **Write your Phase 14 intelligence briefings** if not done yet.

3. **Leaderboard snapshot** -- run scrape_leaderboard.py.

4. **Merge tools to main** so other agents can access.

TUI can wait. Submissions can't.

### STATUS REPORT
After each action, write 3 lines to:
`/Volumes/devdrive/github_dev/nmiai-2026-main/intelligence/for-overseer/ops-status.md`
