# Tripletex AI Accounting Agent -- Plan

**Track:** NLP | **Weight:** 33.33%
**Last updated:** 2026-03-22 00:00 CET
**Bot:** tripletex_bot_v4.py (27 executors, rev 92 deployed)
**Time remaining:** ~15 hours (deadline Sunday 15:00 CET)
**Submissions:** 300 fresh at 01:00 CET

---

## Autonomous Improvement Loop (CLOSED)

```
1. audit-and-submit.sh --max 15 --auto
   [syntax -> health -> MALFORMED -> smoke test -> SUBMIT -> POST-ANALYSIS]

2. post_submit_analysis.py reads Cloud Run logs automatically:
   - Executor performance (runs, success%, avg calls, errors)
   - 4xx error breakdown (which endpoints fail, why)
   - Submission scores by check count
   - Regression detection (compare vs historical bests)
   - Recommendations: what to fix next

3. Fix top recommendation -> Boris (sequential: review -> simplify -> validate) -> deploy.sh

4. Repeat from step 1
```

### Tools in the loop

| Tool | Role | Status |
|------|------|--------|
| `audit-and-submit.sh` | Pre-submit gate + submit + post-analysis | Ready |
| `post_submit_analysis.py` | Log analysis + regression check + recommendations | NEW |
| `score_trend.py` | Batch-level score trends + check count breakdown | Ready |
| `deploy.sh` | Single-command syntax -> deploy -> health | Ready |
| `nlp_auto_submit.py` | Playwright submission engine | Ready |
| `efficiency_analyzer.py` | Deep API call analysis (run separately) | Needs filter fix |
| `self_improve.py` | Gemini-powered diagnosis (run separately) | Needs filter fix |

---

## Current Score & Gaps

Score: 29.08 (rank #107). Rev 92 has 18+ fixes, latest batch shows improvement.

**Last batch (23:30 CET):** 55.7% avg, ZERO 0% scores. Best batch all session.

| Check count | Best score | Avg recent | Status |
|-------------|-----------|------------|--------|
| 6 checks | 100% | 100% | Done |
| 7 checks | 100% | 77% | Done (best retained) |
| 8 checks | 100% | 52% | Done (best retained) |
| 10 checks | 70% | 29% | **Main gap** |
| 11 checks | 29% | 18% | Gap |
| 13 checks | 100% | 32% | Done (best retained) |
| 14 checks | 79% | 79% | Partial, improving |
| 22 checks | 68% | 63% | Partial, improving |

**Root causes identified:**
- 10-check 0/10: multiple task types. Executors succeed but miss fields.
- /:createPayment cascade: testing needed (no register_payment task received yet)
- Activity creation: re-added with activityType + project link (rev 92)

---

## Sessions Done

### Session 1 (21:00 - 23:00 CET, rev 83 -> 91)
15+ fixes: voucher postings, currency paidAmount, year_end prepaid path,
supplier invoice VAT, travel zone enum, email guard, PM rename, ledger
duplicate account, extraction prompt, register_payment skip /:payment.

### Session 2 (23:00 - 00:00 CET, rev 91 -> 92)
- Regression investigation: NOT a regression, platform shifted to harder tasks
- Activity creation restored with activityType + project link
- Payment endpoint cascade: /:createPayment -> /:payment -> voucher
- Built automation: deploy.sh, score_trend.py, post_submit_analysis.py
- Closed the autonomous improvement loop

---

## Phase 1: Submit + Analyze (01:00 - 02:00 CET)
```bash
bash agent-nlp/scripts/audit-and-submit.sh --max 15 --auto
```
Post-analysis runs automatically. Read its output for:
- Did /:createPayment work? (check register_payment errors)
- Did activity creation work? (check analyze_ledger scores)
- Any regressions?

## Phase 2: Fix top issues (02:00 - 06:00 CET)
For each recommendation from post_submit_analysis.py:
1. Read the specific executor code
2. Fix the issue
3. Boris: review (wait) -> simplify (wait) -> validate (wait)
4. `bash agent-nlp/scripts/deploy.sh`
5. `bash agent-nlp/scripts/audit-and-submit.sh --max 10 --auto`
6. Repeat

## Phase 3: Efficiency sprint (06:00 - 09:00 CET)
Run `python3 agent-nlp/scripts/efficiency_analyzer.py --hours 6`
Reduce API calls on tasks at 100% correctness for efficiency bonus.

## Phase 4: Feature freeze (09:00 - 15:00 CET)
Bug fixes only. Submit for coverage.
14:30: final submission. 14:45: repo public.

---

## Rules
- `audit-and-submit.sh` for EVERY batch (never bypass)
- Max 15 per batch, read post_submit_analysis.py output before next
- Boris SEQUENTIAL: review -> apply -> simplify -> apply -> validate
- Every 4xx error costs efficiency points
- Never deploy without Boris
