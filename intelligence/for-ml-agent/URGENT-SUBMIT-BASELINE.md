# URGENT: Submit Baseline Predictions NOW

**From:** Butler (Ops Agent)
**Priority:** CRITICAL
**Date:** 2026-03-20 17:00 CET

## Why This Is Urgent

You have not participated in any rounds since March 16. Rounds run every ~3 hours and later rounds are weighted MORE. Every missed round = permanently lost points.

Our ML score is 94.38. Top team has 140.3. The gap is 45.9 points, and it grows every round you miss.

## What To Do

1. **Check for open rounds NOW:**
   ```
   curl -s https://api.ainm.no/astar-island/rounds | python3 -m json.tool
   ```

2. **If a round is open: submit baseline predictions for ALL 5 seeds**
   - Use astar_v3.py in your solutions/ folder
   - Run with --dry-run first to verify output format
   - Then submit all 5 seeds

3. **Pre-submission validation** (tools in shared/tools/):
   ```
   python shared/tools/ml_judge.py your_predictions.json
   ```
   Must show: shape 40x40x6, all probs >= 0.01, all rows sum to ~1.0

4. **After round closes:** Hit /analysis/{round_id}/{seed_index} for all 5 seeds. Log what you learned in MEMORY.md.

## Key Rules (from rules.md)
- Floor ALL probabilities at 0.01, renormalize
- Submit ALL 5 seeds (missing seed = 0 for that seed)
- 50 observation queries per round, shared across seeds
- NEVER submit without JC approval on the actual API call

## Self-Destruct

After reading: save key info to MEMORY.md, then delete this file.
