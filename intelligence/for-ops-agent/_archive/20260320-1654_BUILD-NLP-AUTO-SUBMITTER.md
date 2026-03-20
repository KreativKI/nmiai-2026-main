---
priority: CRITICAL
from: overseer
timestamp: 2026-03-20 14:00 CET
self-destruct: after building and committing, delete
---

## Build: NLP Auto-Submitter (Playwright)

JC approved automated NLP submissions. Build a Playwright script that clicks Submit on the Tripletex track page.

### Rules
- Auto-submit 75% of daily budget, then STOP
- Daily budget: 150 submissions (30 task types x 5 per type)
- Auto-submit limit: 112 submissions, then stop and notify JC
- Respect: 3 concurrent max, 5 per task type per day
- Rate limits reset 01:00 CET
- Log every submission: task type, score, timestamp, pass/fail

### Technical Approach

Reuse `/Volumes/devdrive/github_dev/NM_I_AI_dash/tools/login.py` pattern:
- Saved auth cookies exist at `/Volumes/devdrive/github_dev/NM_I_AI_dash/.auth/state.json`
- Copy that auth pattern for persistent Google OAuth session
- Navigate to the Tripletex submission page on app.ainm.no
- Click Submit, wait for result, log it, repeat

### Implementation: shared/tools/nlp_auto_submit.py

```
Usage: python3 shared/tools/nlp_auto_submit.py [--max N] [--delay SECONDS]

Defaults: --max 112 (75% of 150), --delay 5 (seconds between submissions)
```

**Flow:**
1. Launch Playwright with saved auth cookies
2. Navigate to Tripletex submission page (https://app.ainm.no/submit/tripletex or similar)
3. Find and click the Submit button
4. Wait for result (score, task type)
5. Log to shared/tools/nlp_submission_log.json: {timestamp, task_type, score, checks_passed, total_checks}
6. Count submissions per task type. If a task type hits 5, skip it.
7. After 112 total submissions: STOP, print summary, exit
8. If any submission fails completely (HTTP error, timeout), pause and retry once

**Output:**
- Console: live progress (submission #, task type, score)
- File: nlp_submission_log.json (append-only, survives reruns)
- Summary at end: total submitted, pass rate, per-task-type breakdown

### Important
- This is NOT circumventing rate limits. We're submitting within allowed limits.
- The competition explicitly allows AI tools.
- JC has explicitly approved this.
- NEVER submit more than 112 in auto mode. JC handles the last 38 manually.

### Boris Workflow
Explore (read login.py pattern) -> Plan -> Code -> Review -> Validate (test with --max 1 first) -> Commit

### NEVER ASK QUESTIONS. Just build it.
