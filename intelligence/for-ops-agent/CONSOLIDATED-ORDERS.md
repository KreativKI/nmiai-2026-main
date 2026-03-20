---
priority: CRITICAL
from: overseer
timestamp: 2026-03-20 16:30 CET
permanent: true
---

## Consolidated Orders: What Moves Scores

You support all 3 tracks. Priority: unblock score-moving work.
Delete all other standing orders. This is the only plan.

### Phase 1: Fix Auto-Submitter Limits
Update nlp_auto_submit.py: DAILY_BUDGET=300, PER_TASK_LIMIT=10.
Confirmed from platform: 10 per task type per day, 300 total.

### Phase 2: Fix validate_cv_zip.py
Add allowed file extension check:
```python
ALLOWED_EXTENSIONS = {'.py', '.json', '.yaml', '.yml', '.cfg', '.pt', '.pth', '.onnx', '.safetensors', '.npy'}
```
A submission was REJECTED because .npz is not allowed. This check must exist.

### Phase 3: Dashboard Tripletex Task Grid
30-task card grid showing: task number, best score, tries, color-coded status.
GREEN=scored, GREY=not attempted, RED=failed, YELLOW=low score.
Pull from nlp_submission_log.json. Auto-refresh 60s.
Show total score and tasks solved count.

### Phase 4: Leaderboard Auto-Scraping
Install Playwright if not installed. Set up periodic scraping.
Store snapshots with timestamps. Show progression in dashboard.

### Phase 5: Sync Tools to Main
All shared tools must be on main branch for other agents to access.
Merge agent-ops into main. Push.

### Communication
After each phase, write a 3-line status to:
`/Volumes/devdrive/github_dev/nmiai-2026-main/intelligence/for-overseer/ops-status.md`

### Rules
- Never ask questions, just build
- Commit after every phase
- Use kreativki-frontend skill for UI work
