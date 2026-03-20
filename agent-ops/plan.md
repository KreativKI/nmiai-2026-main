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

### Phase 8: A/B Compare Tool — Status: active

**Why:** Compare DINOv2 vs YOLO-only predictions side by side. Shows exactly which images improved/regressed. Adapted from grocery bot ab_compare.py pattern (Welch's t-test, per-item breakdown).

#### shared/tools/ab_compare.py
- Input: two predictions.json files (or ZIPs) + ground truth
- Run cv_judge scoring on both
- Per-image comparison: which images improved, regressed, unchanged
- Per-category breakdown: which product classes each version handles better
- Statistical test (Welch's t-test on per-image AP)
- Verdict: A_BETTER / B_BETTER / NO_SIGNIFICANT_DIFFERENCE
- Notify CV agent + update agent configs via intelligence/

### Phase 9: Batch Eval Tool — Status: pending

**Why:** Run cv_judge across all 5 CV ZIPs at once. Ranked table shows which is actually best. Saves JC from running cv_judge 5 times manually.

#### shared/tools/batch_eval.py
- Input: directory of submission ZIPs (or explicit list)
- Run cv_judge on each, collect all scores
- Print ranked table: detection mAP, classification mAP, combined, verdict
- Highlight the best submission
- Notify CV agent + update agent configs via intelligence/

### Phase 10: Oracle/Ceiling Estimator — Status: pending

**Why:** Know our theoretical ceiling per track. If CV max is 0.75, don't chase 0.90. Focus effort where headroom exists.

#### shared/tools/oracle_sim.py
- CV: perfect classification on detected boxes = detection mAP (our ceiling is bounded by detection quality)
- ML: uniform prior score vs our predictions (how much better than guessing?)
- Per-track ceiling estimate with current best score as comparison
- Notify all agents + update agent configs via intelligence/
