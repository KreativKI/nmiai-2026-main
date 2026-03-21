# Ideas Log — 2026-03-21 06:15 CET

## New Tools Proposed (Added 06:15)
1. **ML "Auto-Watchdog":** A cron job that pings the ML agent if its `status.json` timestamp is >3 hours old. Prevents silent stalls.
2. **NLP "Task Type Isolator":** A tool to run specific Tripletex tasks (e.g., Travel Expense) against a local sandbox with verbose logging to debug 0% scoring.
3. **"CV Data Synth v3":** Automate the Gemini-based data generation for the most misclassified categories to feed into the next YOLO11m iteration.

## New What's Working (Added 06:15)
- **CV Overnight Training:** Parallel GCP strategy produced a 0.816 val model (YOLO11m on 854 images).
- **Boris "Auto-Judge":** Successfully caught duplicate customer creation bug before Saturday's budget reset.
- **NLP Stable Tasks:** 100% success on 10/16 common task types.

## New What's NOT Working (Added 06:15)
- **ML Agent reporting stability:** Silent for 7 hours. Missed R11.
- **NLP Efficiency on outlier tasks:** Travel Expense (0%) and Payment Reversal (25%) are stalling the overall score.
- **YOLO26m (0.485):** Proved non-competitive compared to YOLO11 series for this dataset.
