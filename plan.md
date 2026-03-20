# Overseer Plan — NM i AI 2026
**Last updated:** 2026-03-20 04:50 CET (T+10.8h)

## Current State

| Track | Score | Status | Next Action |
|-------|-------|--------|-------------|
| **ML** | 45.98 (Round 4, rank #114/187) | Waiting for Round 5 | STRATEGY SHIFT: score = best single round (not cumulative). exp(-3*KL) means small KL gains = big score jumps. Focus on ONE great round. |
| **CV** | 0.5735 (YOLO11m v2, sub 1/10) | v3 TTA + ensemble ready, 2 VMs training | Next: copy-paste synthetic data + DINOv2 classify. Nano Banana confirmed working (free on GCP). |
| **NLP** | 8/8 PERFECT (create_customer) | tripletex_bot_v2 deployed, 3/5 submissions used today | JC submits via web UI to cover more task types |
| **Butler** | Dashboard live, CORS fixed | Building CV submission viewer + validation tools | New standing orders delivered |

## Sleep Mode Active
JC sleeping starting ~04:50 CET. All 4 agents confirmed alive and have standing orders.

### Agent Health Check (04:50 CET)
| Agent | Last Commit | Alive | Notes |
|-------|------------|-------|-------|
| ML | 04:42 | YES | Waiting for Round 5, polling every 60s |
| CV | 04:50 (reported) | YES | v2 ZIP fixed, 2 VMs training (YOLO26m epoch ~48, RF-DETR from epoch 12) |
| NLP | 04:04 | YES | Bot ready, cannot submit without JC |
| Butler | 04:17 | YES | Got new standing orders at 04:45, working on them |

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
- Rank #114/187, score 45.98 (cumulative)
- Round 3: 39.7, Round 4: submitted v6 with improved observation weights
- Top teams: ~100 with 2-3 rounds (per-round scores ~45-50)
- Gap to top: ~10 points per round. Need better spatial modeling.
- Full autonomy to submit every round. Standing orders active.

### 2. CV: Upload Fixed ZIP (JC action required)
- **v2 ZIP ready:** agent-cv/submissions/submission_yolo11m_v2.zip (65MB)
- v1 bug: argparse rejected unknown CLI args (exit code 2)
- v2 fix: parse_known_args() + accepts both --images and --input flags
- Docker validated: exit code 0, 107 predictions, all fields valid
- YOLO26m: epoch ~48, mAP50=0.815 (still training on cv-train-1)
- RF-DETR: resumed from epoch 12 on cv-train-2, running stable
- If YOLO26m or RF-DETR beat 0.945, CV agent will have those ZIPs ready

### 3. NLP: Submit More Task Types (JC action required)
- tripletex_bot_v2 deployed, handles customers + bank accounts + departments
- Score: 8/8 (100%) on create_customer
- 3/5 submissions used today, rate limits reset 01:00 CET
- Cannot submit without JC clicking web UI
- When JC wakes: submit repeatedly at app.ainm.no/submit/tripletex

### 4. Butler: Dashboard & Validation Tools
- Dashboard live with CORS fix and real CV training data
- New standing orders: CV submission viewer, pre-submission validation, leaderboard tracking
- Desktop launcher updated and working

## Completed This Session
- All 5 CLAUDE.md files improved to butler quality standard
- Git worktrees created and synced (4 branches + main)
- Desktop shortcuts for all 5 agents
- Two-way intelligence comms with staggered schedule
- GCP training for CV (YOLO11m complete, YOLO26m + RF-DETR running)
- NLP deployed to Cloud Run, scored 8/8 perfect
- ML submitted Rounds 3-4, rank #114/187
- CV exit code 2 diagnosed and fixed (v2 ZIP ready)
- Butler dashboard: CORS fix, real training data, model selector
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

## When JC Wakes Up (priority order)
1. Upload agent-cv/submissions/submission_yolo11m_v2.zip at app.ainm.no
2. Submit NLP repeatedly at app.ainm.no/submit/tripletex (each click = random task type)
3. Report NLP scores back to NLP agent so it can fix failures
4. Review ML overnight scores (check intelligence/for-overseer/ for reports)
5. Check if YOLO26m or RF-DETR beat 0.945, upload if so
6. Check Slack for auto-submission ruling
