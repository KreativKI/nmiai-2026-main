---
priority: CRITICAL
from: overseer
timestamp: 2026-03-20 16:30 CET
permanent: true
---

## Consolidated Orders: What Moves Your Score

Your score: 5.8 (3/30 tasks solved). Top team: 43.26 (15+ tasks). Gap: coverage.
Delete all other standing orders. This is the only plan.

### RATE LIMITS UPDATED (from platform, verified)
- 10 per task type per day (was 5)
- 3 concurrent max
- 300 total per day (was 150)
- Resets 01:00 CET

Update your rules.md and CLAUDE.md with these numbers NOW.

### Phase 1: Fix Tier 2 Handling
Tier 2 is LIVE with 2x multiplier. Experiment 10 reverted the Tier 2 prompt.
Try a different approach: instead of adding 7 sections to system prompt, add task-type-specific hints ONLY when the LLM detects a Tier 2 task.
Test locally with qc-verify.py.
Commit.

### Phase 2: Run Auto-Submitter
The auto-submitter is at: /Volumes/devdrive/github_dev/nmiai-worktree-ops/shared/tools/nlp_auto_submit.py
Update its limits: DAILY_BUDGET=300, PER_TASK_LIMIT=10.
First: python3 nlp_auto_submit.py --login (opens browser for OAuth)
Test: python3 nlp_auto_submit.py --max 1 --headed
Run: python3 nlp_auto_submit.py --max 225
Log all results.

### Phase 3: Analyze Submission Results
After auto-submitter runs, analyze which task types pass vs fail.
Focus improvement on the FAILING task types (biggest score opportunity).
For each failure: read the prompt, understand what went wrong, fix the bot.

### Phase 4: Efficiency Optimization
For task types scoring 100% correctness, reduce API calls.
Don't fetch entities you just created. Plan before calling.
Efficiency bonus can double the tier score.

### Phase 5: Prepare for Tier 3 (Saturday)
3x multiplier. Complex scenarios: bank reconciliation, ledger corrections.
Research Tripletex API endpoints for these operations.
Build test cases in qc-verify.py.

### Communication
After each phase, write a 3-line status to:
`/Volumes/devdrive/github_dev/nmiai-2026-main/intelligence/for-overseer/nlp-status.md`

### Rules
- Run qc-verify.py before every deploy
- Commit after every phase
- Log everything in EXPERIMENTS.md
- Never hardcode responses
