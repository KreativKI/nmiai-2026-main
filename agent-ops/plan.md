# Operations Agent — Phased Plan

## Current Phase: 5

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
