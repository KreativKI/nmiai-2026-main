# Operations Agent — Phased Plan

## Current Phase: 1

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

### Phase 1: CV Submission Viewer — Status: active
Inspect CV ZIP submissions before uploading: show run.py contents, model weight sizes, blocked import check, file count validation.

Tasks:
- Build CVSubmissionViewer component
- Read ZIP from file path, list contents
- Check run.py for blocked imports (os, sys, subprocess, yaml, etc.)
- Show model weight sizes vs 420 MB limit
- Validate file counts (max 10 .py, max 3 weight files)
- Integrate into CV tab
- Commit: "Phase 1: CV submission viewer with import validation"

### Phase 2: Pre-Submission Validation — Status: pending
One-click validate for each track. CLI tools JC can run before submitting.

Tasks:
- CV: validate ZIP structure, run blocked import scanner, check weight sizes
- NLP: test endpoint with sample prompts, measure response time
- ML: validate prediction tensor format (40x40x6, probabilities sum to 1, floor > 0)
- Dashboard "Validate" buttons per track
- Commit: "Phase 2: Pre-submission validation tools"

### Phase 3: Leaderboard Tracking — Status: pending
Automate leaderboard snapshots and show progression.

Tasks:
- Already have scraper tool + LeaderboardView
- Add auto-refresh button
- Improve column parsing for 3-track breakdown
- Commit: "Phase 3: Leaderboard tracking improvements"

### Phase 4: Auto-Refresh + Polish — Status: pending
Dashboard auto-refreshes data, Playwright visual QC.

Tasks:
- 5-min refresh cycle for training logs and NLP task log
- Playwright screenshot tests for each tab
- UI polish pass
- Commit: "Phase 4: Auto-refresh and visual QC"

### Phase 5: Sleep Report — Status: pending
Write summary of all work done to intelligence/for-overseer/.

Tasks:
- Write ops-sleep-report.md
- Update status.json
- Commit: "Phase 5: Sleep report"
