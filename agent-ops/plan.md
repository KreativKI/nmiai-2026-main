# Operations Agent — Phased Plan

## Current Phase: 6

## Completed Work
- Dashboard scaffold (React 19 + Vite + Tailwind v4, Convex stripped)
- Astar Island grid viewer (40x40, color-coded terrain, pan/zoom/click)
- ML animation: "Play 50-Year Simulation" with spreading cell-flip effect
- ML view modes: Initial, Ground Truth, Changes, Animate
- CV training monitor (real data from GCP VM: yolo11m 100ep, yolo26m 26ep)
- CV detection viewer (bounding boxes on images, confidence slider)
- NLP endpoint health check via Vite proxy (CORS fixed)
- NLP clickable task types with Cloud Run execution log
- Leaderboard tracker with score progression chart
- Kreativ KI branding in header
- Code reviewed: 6 issues found and fixed
- Desktop launcher script

## Phases

### Phase 1: CV Submission Viewer — Status: done
Build `validate_cv_zip.py` shared tool + dashboard ZIP inspector component.

Tasks:
- Create shared/tools/ directory structure
- Build validate_cv_zip.py: check ZIP structure, blocked imports, weight sizes, file counts
- Build CVSubmissionViewer dashboard component showing validation results
- Drop tool in shared/tools/, notify CV agent
- Commit: "Phase 1: CV submission viewer with import validation"

### Phase 2: Shared Validation Tools — Status: done
Build all 4 shared tools from TOOL-SHARING.md, drop in shared/tools/, notify agents.

Tasks:
- shared/tools/validate_cv_zip.py (done in Phase 1, move here)
- shared/tools/check_nlp_endpoint.py: health check NLP Cloud Run endpoint
- shared/tools/check_ml_predictions.py: validate ML prediction tensor (40x40x6, floors, normalization)
- shared/tools/scrape_leaderboard.py: already exists, move to shared/tools/
- Notify all 3 agents via intelligence folders
- Dashboard "Validate" buttons per track
- Commit: "Phase 2: Shared validation tools for all tracks"

### Phase 3: Leaderboard Tracking — Status: done
Improve leaderboard with 3-track column breakdown and auto-snapshot.

Tasks:
- Improve column parsing for Tripletex/Astar/NorgesGruppen breakdown
- Store snapshots with timestamp
- Show delta between snapshots
- Commit: "Phase 3: Leaderboard tracking improvements"

### Phase 4: Auto-Refresh + Polish — Status: done
Dashboard auto-refreshes data periodically.

Tasks:
- 5-min refresh cycle for training logs, NLP task log, leaderboard
- Pull fresh data from GCP VMs on refresh
- UI polish: loading states, error states, responsive layout
- Commit: "Phase 4: Auto-refresh and visual polish"

### Phase 5: Sleep Report — Status: done
Write summary to intelligence/for-overseer/.

Tasks:
- Write ops-sleep-report.md with all work done
- Update status.json
- Commit: "Phase 5: Sleep report"

### Phase 6: QC Judge Tools (CRITICAL, blocking submissions) — Status: done

**Why:** Wasted 2 of 3 CV submissions yesterday because we couldn't validate locally. JC blocked all submissions until QC judges exist.

#### Tool A: shared/tools/cv_judge.py (BUILD FIRST)
Score CV submissions exactly like the competition before uploading.
- Convert YOLO labels to COCO format for holdout split (image_id % 5 == 0)
- Unzip submission, run run.py against holdout images
- Calculate detection mAP (all category_ids set to 0) and classification mAP (real category_ids)
- Combined: 0.7 * detection + 0.3 * classification
- Compare against previous results (shared/tools/cv_results.json)
- Verdict: SUBMIT / SKIP / RISKY
- Dependencies: pycocotools, numpy, json, zipfile, pathlib

#### Tool B: shared/tools/ml_judge.py
Validate + score ML predictions before submission.
- Load predictions for all 5 seeds
- Validate: shape 40x40x6, floors >= 0.01, normalization sums to ~1.0
- If ground truth available: calculate per-seed KL divergence and predicted score
- Score formula: max(0, min(100, 100 * exp(-3 * weighted_KL)))
- Compare against previous rounds (shared/tools/ml_results.json)
- Verdict: SUBMIT / SKIP / VALIDATION_ERROR

Boris for each: Explore → Plan → Code → Review → Simplify → Validate → Commit

### Phase 7: CV Submission Profiler (CRITICAL, last submission at stake) — Status: done

**Why:** DINOv2 submission runs 2 ONNX models per image. Competition timeout is 300s on L4 GPU. Must verify it stays under before using last submission slot.

#### shared/tools/cv_profiler.py
- Unzip submission to temp dir
- Run against small sample batches (5, 10, 25 images), timing each
- Per-image breakdown: YOLO inference, NMS, crop extraction, DINOv2 per crop, gallery kNN
- Count average detections per image (each = one DINOv2 forward pass)
- Extrapolate to full test set at L4 GPU speed (known ONNX benchmarks)
- Print GO/NO-GO verdict against 300s timeout with safety margin

Boris: Explore → Plan → Code → Review → Simplify → Validate → Commit

### Phase 8: A/B Compare Tool — Status: done

**Why:** Compare DINOv2 vs YOLO-only predictions side by side. Shows exactly which images improved/regressed. Adapted from grocery bot ab_compare.py pattern (Welch's t-test, per-item breakdown).

#### shared/tools/ab_compare.py
- Input: two predictions.json files (or ZIPs) + ground truth
- Run cv_judge scoring on both
- Per-image comparison: which images improved, regressed, unchanged
- Per-category breakdown: which product classes each version handles better
- Statistical test (Welch's t-test on per-image AP)
- Verdict: A_BETTER / B_BETTER / NO_SIGNIFICANT_DIFFERENCE
- Notify CV agent + update agent configs via intelligence/

### Phase 9: Batch Eval Tool — Status: done

**Why:** Run cv_judge across all 5 CV ZIPs at once. Ranked table shows which is actually best. Saves JC from running cv_judge 5 times manually.

#### shared/tools/batch_eval.py
- Input: directory of submission ZIPs (or explicit list)
- Run cv_judge on each, collect all scores
- Print ranked table: detection mAP, classification mAP, combined, verdict
- Highlight the best submission
- Notify CV agent + update agent configs via intelligence/

### Phase 10: Oracle/Ceiling Estimator — Status: done

### Phase 11: NLP Auto-Submitter — Status: done

### Phase 12: Live Leaderboard Feed — Status: done

### Phase 13: Competition TUI — Status: planning

**Why:** Web dashboard doesn't give JC a good enough overview. Need a terminal UI that shows everything at a glance, with keyboard navigation.

**Tech:** Python `textual` (modern TUI framework, async, rich-based)

**Inspiration:** The screenshot shows a split-pane TUI with tabs, inline charts, data tables, and a 40x40 terrain grid. We adapt this for 3-track competition monitoring.

#### Layout

```
[Tab bar: 1:Overview  2:Leaderboard  3:ML  4:CV  5:NLP  6:Tools  7:Logs]
+---------------------------+----------------------------------+
|   Left pane (data)        |   Right pane (visualization)     |
|                           |                                  |
+---------------------------+----------------------------------+
[Status bar: Rank #62 | Score 18.4 | Deadline 23h12m | Subs today 15/300]
```

#### Tab 1: Overview (default view)
Left pane:
- Countdown timer to each deadline (cut-loss, freeze, repo public, end)
- 3 track cards:
  - ML: score, rank, rounds participated, last round time
  - NLP: total 18.4, rank #62, 13/30 tasks, 15 submissions, tier breakdown
  - CV: best mAP, submissions used/10, last submission verdict
- Submission budget: ML (unlimited API), NLP (15/300 used), CV (X/10 used)

Right pane:
- Live leaderboard top 10 with our position highlighted
- Score progression sparkline per track

#### Tab 2: Leaderboard
- Full leaderboard table (top 30 + our position)
- Per-track columns: Tripletex, Astar Island, NorgesGruppen, Total
- Delta since last snapshot (green/red arrows)
- Auto-refresh from fetch_leaderboard.py data
- Keyboard: arrow keys to scroll, Enter for team detail

#### Tab 3: ML Explorer
Left pane:
- Round history table: round#, score, weight, seeds submitted
- Per-seed score breakdown
- Observation budget: queries used/remaining

Right pane:
- 40x40 terrain grid (unicode symbols, color-coded)
  - Mountain=gray triangle, Forest=green tree, Settlement=yellow house, Port=blue anchor, Ruin=red cross, Empty=dot
- Seed selector: 1-5 keys
- View modes: Initial / Predicted / Ground Truth / Changes
- Keyboard: arrow keys to pan viewport

#### Tab 4: CV Status
Left pane:
- Submission table: ZIP name, det_mAP, cls_mAP, combined, verdict, profiler result
- Best submission highlighted
- Submissions remaining today: X/10

Right pane:
- Training progress from GCP logs (if available)
- Category coverage bar (X/357 categories seen)
- Profiler summary: estimated time vs 300s timeout

#### Tab 5: NLP Submit
Left pane:
- 30-task grid (6x5): colored cards showing task#, best score, tries
  - GREEN = scored, GREY = not attempted, RED = 0 score, YELLOW = low
- Total: 18.4 | Solved: 13/30 | Tier1: 7.31 | Tier2: 11.13 | Tier3: 0
- Top team comparison row

Right pane:
- Recent Results list (scrollable)
- Endpoint health status
- Submit button (interactive, asks y/n)
- Live submission log

Data sources:
- Tripletex leaderboard API (our team entry) for total/rank/tiers
- nlp_submission_log.json for recent results
- nlp_task_scores.json for manual task score entry
- Platform scrape for task-level detail (task names not in API)

#### Tab 6: Tools
- Menu of all shared tools with one-key launch
- cv_judge, ml_judge, cv_profiler, ab_compare, batch_eval, oracle_sim
- Output shown inline in right pane

#### Tab 7: Logs
- Combined log viewer from all tracks
- Filter by track (ML/CV/NLP/OPS)
- Search

#### Status Bar (always visible)
`Rank #62 | Score 18.4 | NLP 13/30 | CV 3/10 subs | ML R6 | Deadline: 23h12m | [q]uit`

#### Keyboard
- 1-7: switch tabs
- q: quit
- r: refresh data
- Tab within panes: switch focus
- Arrow keys: navigate tables/grid

#### Data Sources (no new fetching, reuse existing)
- fetch_leaderboard.py output (leaderboard.json)
- Tripletex API (direct fetch for our team stats)
- Astar Island API (round status, leaderboard)
- nlp_submission_log.json
- nlp_task_scores.json (manual entry file, created by ops)
- cv_results.json, ml_results.json (from judges)
- viz_data.json (ML terrain data)

#### Build Phases
A. Skeleton: textual app with tab bar, status bar, placeholder views
B. Overview tab: deadline countdown, track cards, budget display
C. Leaderboard tab: table from fetch_leaderboard data
D. NLP tab: 30-task grid, submission log, submit button
E. ML tab: terrain grid viewer, round history
F. CV tab: submission table, profiler results
G. Tools tab: tool launcher
H. Polish: keyboard shortcuts, auto-refresh, colors

#### Outstanding Orders (from intelligence/)
- UPDATE-AUTO-SUBMITTER-LIMIT: raise to 300/day, 10/type (do first)
- UPDATE-CV-VALIDATOR: add .npz to allowed extensions (do first)
- ADAPT-ARCHIVE-TOOLS: already done (Phases 8-10)

**Why:** Know our theoretical ceiling per track. If CV max is 0.75, don't chase 0.90. Focus effort where headroom exists.

#### shared/tools/oracle_sim.py
- CV: perfect classification on detected boxes = detection mAP (our ceiling is bounded by detection quality)
- ML: uniform prior score vs our predictions (how much better than guessing?)
- Per-track ceiling estimate with current best score as comparison
- Notify all agents + update agent configs via intelligence/
