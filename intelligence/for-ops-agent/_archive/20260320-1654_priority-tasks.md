---
priority: HIGH
from: overseer
timestamp: 2026-03-20 03:10 CET
self-destruct: delete after creating plan.md with all tasks and confirming in intelligence/for-overseer/
---

## Butler Task List (ordered by priority)

### Priority A: Submission Automation (DO FIRST)
JC cannot manually submit every time. Build Playwright scripts to automate submissions.

**A1. NLP Auto-Submitter**
- Log into app.ainm.no using Playwright (reuse pattern from `/Volumes/devdrive/github_dev/NM_I_AI_dash/tools/login.py` for Google OAuth + saved cookies)
- Navigate to https://app.ainm.no/submit/tripletex
- Click Submit button repeatedly (with cooldown between submissions)
- Log each submission result
- Respect rate limits: 5 per task type per day, 3 concurrent
- Run as a loop: submit, wait 30s, submit again

**A2. CV ZIP Uploader**
- Same Playwright login flow
- Navigate to CV upload page
- Upload a ZIP file from a specified path
- Log submission result
- Respect rate limits: 10/day

Both scripts should reuse the login.py cookie persistence pattern so you only do Google OAuth once.

### Priority B: Dashboard
Fork the dashboard from `/Volumes/devdrive/github_dev/NM_I_AI_dash/` into agent-ops/. Adapt for 3 tracks:

**B1. Astar Island Grid Viewer**
- 40x40 terrain map, color-coded (Mountain=gray, Forest=green, Settlement=brown, Port=blue, Ruin=red, Empty=light)
- Load from agent-ml/solutions/data/viz_data.json or the Astar Island API
- Show initial terrain vs predictions vs ground truth (after round completes)
- Confidence heatmap overlay

**B2. CV Training Monitor**
- Live training curves: mAP50, mAP50-95, Precision, Recall per epoch
- Read logs from GCP VM: `gcloud compute ssh cv-train-1 --zone=europe-west1-c --project=ai-nm26osl-1779 --command="grep '^\s*all' ~/cv-train/train.log"`
- Show current best checkpoint

**B3. NLP Task Tracker**
- Endpoint health check (GET https://tripletex-agent-795548831221.europe-west4.run.app/solve returns 405 = alive)
- Which of 30 task types tested, scores per type
- Submission history

**B4. Leaderboard + Cross-Track Overview**
- Track top 10 teams over time
- Our score breakdown per track
- Timeline of submissions

### GCP Details
- Project: ai-nm26osl-1779
- Account: devstar17791@gcplab.me
- Use kreativki-frontend skill for all UI work
- Gemini via ADC (no separate key)

### Reference Code
- `/Volumes/devdrive/github_dev/NM_I_AI_dash/tools/login.py` — Playwright auth
- `/Volumes/devdrive/github_dev/NM_I_AI_dash/tools/leaderboard.py` — leaderboard scraper
- `/Volumes/devdrive/github_dev/NM_I_AI_dash/src/` — React dashboard components

Create plan.md first. Then build A1 and A2 before touching the dashboard.
