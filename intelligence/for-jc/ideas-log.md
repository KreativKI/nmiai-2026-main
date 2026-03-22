# Ideas Log — 2026-03-22 01:11 CET

## New Tools Proposed (Added 06:15)
1. **ML "Auto-Watchdog":** A cron job that pings the ML agent if its `status.json` timestamp is >3 hours old. Prevents silent stalls.
2. **NLP "Task Type Isolator":** A tool to run specific Tripletex tasks (e.g., Travel Expense) against a local sandbox with verbose logging to debug 0% scoring.
3. **"CV Data Synth v3":** Automate the Gemini-based data generation for the most misclassified categories to feed into the next YOLO11m iteration.

## New Tools Proposed (Added 01:11, Sunday)
1. **Boris-as-a-Service:** Automated code-review for CV and ML agents before final submission to catch import violations or logic errors (like the NLP duplicate customer bug).
2. **NLP "Deep Inspector":** Script to walk through the sandbox for Travel Expense to identify missing reference data or hidden mandatory fields that cause 0% scores.
3. **GUI Update:** Butler labeling tool needs a "Confidence Re-labeler" — Let JC quickly re-label only the low-confidence detections from the auto-labeler.

## New What's Working (Added 06:15)
- **CV Overnight Training:** Parallel GCP strategy produced a 0.816 val model (YOLO11m on 854 images).
- **Boris "Auto-Judge":** Successfully caught duplicate customer creation bug before Saturday's budget reset.
- **NLP Stable Tasks:** 100% success on 10/16 common task types.

## New What's Working (Added 01:11, Sunday)
- **CV Synthetic Data:** Generation of 794 shelf images with Gemini 3.1 Flash is in progress (cv-train-1, cv-train-4).
- **NLP Budget Reset:** 180 fresh submissions available for the Sunday push (01:00 CET).
- **ML Stability:** Score 71.77 stable with v3 dual blend.

## New What's NOT Working (Added 06:15)
- **ML Agent reporting stability:** Silent for 7 hours. Missed R11.
- **NLP Efficiency on outlier tasks:** Travel Expense (0%) and Payment Reversal (25%) are stalling the overall score.
- **YOLO26m (0.485):** Proved non-competitive compared to YOLO11 series for this dataset.

## New Tools Proposed (Added 03:14, Sunday)
1. **CV "VM Batch Downloader":** Tool to auto-rsync synthetic images from multiple GCP VMs to the local workspace for JC's labeling session.
2. **NLP "Salary Verifier":** Helper script to cross-reference annual vs monthly salary requirements in Tripletex for the process_salary task.
3. **ML "Round Trend Analyzer":** Automated KL-divergence tracker to detect model drift between rounds.
4. **Ops "Leaderboard Delta Monitor":** Real-time alert when competitors in our tier jump significantly in score.

## New What's Working (Added 03:14, Sunday)
- **Status Reporting (Overseer):** Coordination rounds are running hourly.
- **Track Agents:** CV and NLP have clear paths to Sunday morning (synthetic retraining + 180 budget).
- **ML Stability:** v3 dual blend (V2+V3) remains stable at 71.77.

## New What's NOT Working (Added 03:14, Sunday)
- **ML Agent Reporting:** Still silent for over 2 hours. Briefing sent to request a status update.
- **Butler GUI Progress:** Still waiting for JC's wake-up to validate the labeling tool.
