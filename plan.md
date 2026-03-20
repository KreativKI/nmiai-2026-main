# Overseer Plan — NM i AI 2026
**Last updated:** 2026-03-20 14:30 CET | **Next refresh:** 22:30 CET | **Remaining:** 48.5h

## Scores

| Track | Score | Rank | Subs Left Today |
|-------|-------|------|-----------------|
| **ML** | 71.77 (R4) | #49/191 | API (unlimited) |
| **CV** | 0.5756 | ~mid/105 | 2/10 |
| **NLP** | 8/8 (1 task type) | ?/161 | ~147/150 |

## Priority Actions Right Now

### 1. NLP: Run auto-submitter (CRITICAL)
- 147 submissions unused today. Tier 2 opened (2x multiplier).
- Auto-submitter built at `shared/tools/nlp_auto_submit.py`
- Test with --max 1 first, then run 75% budget

### 2. ML: Build simulation engine (APPROVED)
- Test query strategies offline against 6 cached rounds
- No API calls, no submission risk
- Apply best strategy to R8 (~18:53 CET)

### 3. CV: QC toolchain on DINOv2 ZIP
- Run: validate_cv_zip -> cv_profiler -> cv_judge -> ab_compare
- Submit only if classification mAP improved
- 2 submissions left today, save for validated improvement

## Key Findings (do NOT repeat this work)
- Detection is NOT the bottleneck (TTA +0.002, ensemble +0.000)
- Classification IS the bottleneck (DINOv2 + reference images is the path)
- ML score = best single round, not cumulative. exp(-3*KL).
- Nano Banana works free on GCP (gemini-2.5-flash-image, location=global)
- Copy-paste augmentation: not built yet, for Saturday

## Deadlines

| Time | What |
|------|------|
| Today 01:00 CET | Rate limits reset (CV 10, NLP 150) |
| Today (Friday) | Tier 2 tasks live (NLP 2x multiplier) |
| Saturday morning | Tier 3 tasks (NLP 3x multiplier) |
| Saturday 12:00 | CUT-LOSS: any track with 0 = submit baseline |
| Sunday 09:00 | FEATURE FREEZE |
| Sunday 12:00 | Git-lfs + MIT LICENSE + prepare public repo |
| Sunday 14:45 | MANDATORY: Repo goes public (PRIZE ELIGIBILITY) |
| Sunday 15:00 | COMPETITION ENDS |

## When JC Wakes Up (next session)
1. Check auto-submitter log (nlp_submission_log.json)
2. Review ML simulation results, apply best strategy
3. Submit CV DINOv2 if QC passed
4. Refresh this plan
