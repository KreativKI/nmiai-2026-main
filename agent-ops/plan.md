# Operations Agent — Phased Plan

## Current Phase: 14

## Situation Assessment (2026-03-20 ~17:00 CET)

Rank #120/336, Score 112.6. Gap to #1: 65.7. Deadline: Sunday 15:00 CET (~44h).

| Track | Our Score | Best Score | Headroom | Status |
|-------|-----------|------------|----------|--------|
| ML    | 94.38     | 140.3      | 45.9     | Rounds running, need more observations |
| NLP   | 18.22     | 46.02      | 27.8     | Bot deployed, auto-submitter NOT running |
| CV    | 0         | 0          | FIRST MOVER | YOLO11m done (0.945 mAP), 0 submissions |

**Critical failures:**
A. NLP auto-submitter is NOT running. Only 4 submissions total. Should be 225/day.
B. CV has 0 competition submissions despite having a trained model.
C. ML agent stale since March 16. Rounds are running without us.

## Phase 14: Emergency Intelligence Briefings (DO NOW)

Write actionable intelligence messages to unblock all 3 agents.

### 14A: CV Agent - SUBMIT NOW briefing
- YOLO11m training done (mAP50 0.945 locally)
- Nobody has scored CV yet. First valid submission = instant advantage.
- Pre-submission toolchain: validate_cv_zip -> cv_profiler -> cv_judge
- DINOv2 is NO-GO (timeout). Ship YOLO11m-only submission.
- Tell agent: "Your trained model is good enough. Package and submit."

### 14B: ML Agent - WAKE UP briefing
- Agent hasn't engaged in 4 days. Solutions exist but aren't being used.
- Rounds are running every ~3h. Each missed round = lost points forever.
- Tell agent: "Submit baseline NOW. Use astar_v3.py. Every round matters."

### 14C: NLP Agent - MAXIMIZE SUBMISSIONS briefing
- Only 4 submissions used out of 300/day budget.
- Auto-submitter approved but not running.
- Tell agent: "Run nlp_auto_submit.py immediately. Target all 30 task types."

### 14D: JC Briefing
- Situation report for intelligence/for-jc/
- Score breakdown, what's blocking, what JC needs to do

## Phase 15: Verify Auto-Submitter Works
- Test nlp_auto_submit.py can still reach the endpoint
- If broken, fix it
- Document how to start it

## Phase 16: Refresh Leaderboard Data
- Run fetch_leaderboard.py to get latest snapshot
- Update dashboard data

## Phase 17: Update TUI with Latest Scores
- Ensure all data files are current
- TUI reflects real-time state

## Completed Phases (1-13)
(see git history for details)
