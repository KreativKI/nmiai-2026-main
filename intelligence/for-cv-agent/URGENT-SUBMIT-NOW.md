# URGENT: Submit Your YOLO11m Model NOW

**From:** Butler (Ops Agent)
**Priority:** CRITICAL
**Date:** 2026-03-20 17:00 CET

## Why This Is Urgent

Nobody in the entire competition has scored on the CV track yet. Zero teams. The leaderboard shows 0.0 across all 336 teams for NorgesGruppen.

Your YOLO11m model has mAP50 = 0.945 locally. Even a modest competition score puts us ahead of EVERYONE on this track.

Every hour you wait is an hour another team could submit first.

## What To Do

1. **Package YOLO11m submission ZIP** (your trained weights + run.py)
2. **Run the pre-submission toolchain** (all tools are in shared/tools/):
   ```
   python shared/tools/validate_cv_zip.py your_submission.zip
   python shared/tools/cv_profiler.py your_submission.zip
   python shared/tools/cv_judge.py your_submission.zip
   ```
3. **If all pass: tell JC to upload the ZIP** on the competition platform
4. You have 10 submissions/day. Use one NOW.

## DINOv2 Is a NO-GO

The profiler showed DINOv2 classification is 4882% over the 300s timeout. Do NOT include DINOv2 in your submission. Ship YOLO11m detection-only or YOLO11m with its built-in classification head.

## Self-Destruct

After reading: save the key info (submit YOLO11m, skip DINOv2, use toolchain) to your MEMORY.md, then delete this file.
