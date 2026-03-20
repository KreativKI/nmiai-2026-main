# Overseer Plan — NM i AI 2026
**Last updated:** 2026-03-20 04:30 CET (T+10.5h)

## Current State

| Track | Score | Status | Next Action |
|-------|-------|--------|-------------|
| **ML** | 39.72 (Round 3, rank 33) | Round 4 active, full autonomy | Submitting every round autonomously |
| **CV** | Failed (exit code 2) | YOLO11m mAP50=0.945, YOLO26m training | Debug exit code 2, fix ZIP, prepare for resubmission |
| **NLP** | 8/8 PERFECT (last submission) | Endpoint live on Cloud Run | Improve agent, test more task types |
| **Butler** | Dashboard built | 4-tab dashboard with grid viewer, training monitor | Fix loading issues, add CV submission viewer |

## Sleep Mode Active
JC sleeping ~7 hours starting ~04:30 CET. All agents have standing orders in intelligence/ folders.

### Staggered Communication Schedule
| Agent | Reads inbox | Writes status |
|-------|------------|---------------|
| ML | :00, :30 | :05, :35 |
| CV | :10, :40 | :15, :45 |
| Butler | :15, :45 | :20, :50 |
| NLP | :20, :50 | :25, :55 |
| Overseer | every 10m | as needed |

## Active Tasks

### 1. ML: Autonomous Round Submissions
- Full autonomy to submit every round
- Experiment with new approaches, log everything to MEMORY.md
- Explore: spatial modeling, Gaussian processes, better parameter inference
- Standing orders in intelligence/for-ml-agent/STANDING-ORDERS-SLEEP.md

### 2. CV: Debug Exit Code 2 (URGENT)
- YOLO11m ZIP failed with exit code 2 on competition sandbox
- Docker validation must use REAL images and EXACT competition command
- QC loop rule sent: intelligence/for-cv-agent/QC-LOOP-RULE.md
- YOLO26m still training on cv-train-1
- RF-DETR NOT started (second VM not created despite 3 requests)
- When fixed: prepare ZIP but do NOT upload (JC does manually)

### 3. NLP: Improve Agent
- 8/8 perfect on last submission
- Cannot submit while JC sleeps (requires web UI click)
- Focus: test more task types locally, improve error handling, prepare for Tier 2
- HTTP 400 early-exit guard still needs fixing

### 4. Butler: Dashboard & Tools
- Fix loading issues, Playwright-validate all views
- Add CV submission viewer (inspect ZIPs, view detections)
- Build pre-submission validation tools
- Review and improve existing tools from grocery bot archive

## Completed This Session
- All 5 CLAUDE.md files improved to butler quality standard
- Git worktrees created and synced (4 branches + main)
- Desktop shortcuts for all 5 agents
- Two-way intelligence comms with staggered schedule
- 10-min monitoring loop
- GCP training for CV (YOLO11m complete, YOLO26m running)
- NLP deployed to Cloud Run, scored 8/8 perfect
- ML first submission: 39.72 (Round 3)
- Credentials saved to .env (gitignored)
- Competition docs snapshots and rule tracking

## Key Deadlines
| Time | What |
|------|------|
| Daily 01:00 CET | Rate limits reset |
| Friday morning | Tier 2 tasks unlock (NLP 2x multiplier) |
| Saturday 12:00 | CUT-LOSS: any track with no submission = baseline NOW |
| Saturday morning | Tier 3 tasks unlock (NLP 3x multiplier) |
| Sunday 09:00 | FEATURE FREEZE |
| Sunday 14:45 | Repo goes public |
| Sunday 15:00 | COMPETITION ENDS |

## Pending (when JC wakes up)
- Upload fixed CV ZIP manually
- Submit NLP via web UI (multiple times to cover more task types)
- Review ML overnight scores and experiments
- Check Slack for auto-submission ruling
- Review agent sleep reports in intelligence/for-overseer/
