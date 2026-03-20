# Overseer Plan — NM i AI 2026
**Last updated:** 2026-03-20 06:35 CET (T+12.6h)

## Current State

| Track | Score | Status | Next Action |
|-------|-------|--------|-------------|
| **ML** | 45.98 (Round 4, #114/187) | Resubmitting R4 with improved model, waiting R5 | Build better spatial model from ground truth. Score = best single round, exp(-3*KL). |
| **CV** | 0.5756 (3 subs used, 1 left today) | Detection solved. Classification is the bottleneck. | **DINOv2 crop-and-classify with 327 reference images. #1 priority.** |
| **NLP** | 8/8 PERFECT (create_customer) | tripletex_bot_v2 deployed | Harden more task types. JC submits 3x concurrently when awake. |
| **Butler** | Dashboard + 4 shared tools | All tools Boris-reviewed and committed | CV submission viewer, then support other agents |

## Sleep Mode Active
JC sleeping starting ~06:35 CET. All 4 agents have phased standing orders + EXPERIMENTS.md rule.

### Key Findings This Session
- **Detection is NOT the bottleneck.** YOLO11m solo (0.5735), TTA (0.5756), ensemble (0.5756) all score the same. More detection models won't help.
- **Classification IS the bottleneck.** 327 product reference images are unused. DINOv2 crop-and-classify is the highest-impact move.
- **ML scoring:** score = 100 * exp(-3 * KL). Best single round, not cumulative. Small KL improvements = big score jumps.
- **Nano Banana works free on GCP:** `gemini-2.5-flash-image` with `location=global`. JC decides tomorrow.
- **Copy-paste augmentation:** +6.9 mAP in low-data regimes (CVPR 2021). 250-500 images optimal.

## CV Submissions Today (resets 01:00 CET)
| # | What | Score | Verdict |
|---|------|-------|---------|
| 1 | YOLO11m v2 (baseline) | 0.5735 | Baseline |
| 2 | YOLO11m v3 TTA + conf=0.05 | 0.5756 | TTA barely helps |
| 3 | Ensemble YOLO11m+YOLO26m WBF | 0.5756 | More detection doesn't help |
| 4 | (saved for DINOv2 version) | - | 1 submission left |

## Active Tasks

### 1. CV: Pre-Submission Toolchain + DINOv2 Submit (HIGHEST PRIORITY)
DINOv2 crop-and-classify submission is built and Docker-validated (submission_dinov2_classify_v1.zip, 143MB).
Before uploading, run full toolchain. Butler never built the scripts, so overseer builds them now.

**Phase A: Build tools (Boris per tool, one at a time)**
1. validate_cv_zip.py -- ZIP structure, blocked imports, sizes DONE
2. cv_profiler.py -- timing vs 300s timeout DONE
3. cv_judge.py -- prediction quality + verdict (SUBMIT/SKIP/RISKY) IN PROGRESS
4. ab_compare.py -- compare DINOv2 vs YOLO-only predictions DONE

**Phase B: Run toolchain on submission_dinov2_classify_v1.zip**
```
python3 shared/tools/validate_cv_zip.py agent-cv/submissions/submission_dinov2_classify_v1.zip
python3 shared/tools/cv_profiler.py agent-cv/submissions/submission_dinov2_classify_v1.zip
python3 shared/tools/cv_judge.py --predictions-json agent-cv/docker_output/predictions.json
python3 shared/tools/ab_compare.py --a [yolo-only preds] --b agent-cv/docker_output/predictions.json
```

**Phase C: Housekeeping**
- Create EXPERIMENTS.md
- Update agent-cv/CLAUDE.md with toolchain section
- Commit after each phase

### 2. ML: Build Better Spatial Model
- Resubmitted R4 with improved distance-based model
- Stop idle polling. Build proper spatial model from R1-R4 ground truth
- Analyze cell transitions, neighborhood influence, parameter inference
- Check rounds every 15-20 min, not every 60s

### 3. NLP: Harden More Task Types
- 8/8 on create_customer. Bot handles customers + bank accounts + departments
- Audit all 30 task types, test locally, improve for Tier 2 (Friday)
- Cannot submit without JC. Ready when he wakes.
- JC should click Submit 3 times quickly (3 concurrent allowed)

### 4. Butler: Support and Tools
- 4 shared tools delivered: validate_cv_zip.py, check_nlp_endpoint.py, check_ml_predictions.py, scrape_leaderboard.py
- Next: CV submission viewer, leaderboard tracking, dashboard polish
- Can take tool orders from other agents via intelligence/for-ops-agent/

## Systems Established This Session
- Intelligence folder comms (two-way, staggered schedule)
- Phased standing orders with commit checkpoints (crash insurance)
- EXPERIMENTS.md rule (persistent logs, prevent repeating work)
- Tool sharing system (shared/tools/, agents can order from Butler)
- Butler never-ask rule (just build, iterate later)
- Stop-idling orders (productive work between monitoring checks)
- Overseer QC process for CV submissions

## Completed This Session
- All 5 CLAUDE.md files improved to butler quality standard
- Git worktrees created and synced (4 branches + main)
- Desktop shortcuts for all 5 agents
- Two-way intelligence comms with staggered schedule
- GCP training: YOLO11m done, YOLO26m done (0.914), RF-DETR training (~epoch 39)
- NLP deployed to Cloud Run, scored 8/8 perfect
- ML submitted Rounds 3-4, rank #114/187, found scoring formula
- CV: 3 submissions (0.5735, 0.5756, 0.5756), bottleneck identified
- Butler: dashboard + 4 shared tools + branding + ML ground truth viewer
- 6 research agents completed (models, ensemble, classification, synthetic data, Nano Banana)
- Nano Banana verified working free on GCP
- EXPERIMENTS.md rule pushed to all agents

## Key Deadlines
| Time | What |
|------|------|
| Daily 01:00 CET | Rate limits reset (CV: 10 subs, NLP: 5/task type) |
| Friday morning | Tier 2 tasks unlock (NLP 2x multiplier) |
| Saturday 12:00 | CUT-LOSS: any track with no submission = baseline NOW |
| Saturday morning | Tier 3 tasks unlock (NLP 3x multiplier) |
| Sunday 09:00 | FEATURE FREEZE |
| Sunday 14:45 | Repo goes public |
| Sunday 15:00 | COMPETITION ENDS |

## When JC Wakes Up (priority order)
1. Submit CV DINOv2 version if ready (1 sub left today, or 10 fresh after 01:00)
2. Submit NLP repeatedly (3 clicks at a time, report scores back to NLP agent)
3. Review ML overnight scores in intelligence/for-overseer/
4. Review all agent sleep reports in intelligence/for-overseer/
5. Decide on Nano Banana synthetic data (free on GCP, ~500 images)
6. Check if RF-DETR finished training
