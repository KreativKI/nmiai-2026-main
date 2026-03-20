# Tripletex AI Accounting Agent -- Execution Plan

**Track:** NLP | **Weight:** 33.33%
**Last updated:** 2026-03-20 22:10 CET
**Approach:** Structured workflows (LLM extracts fields, Python executes API calls)
**Bot version:** tripletex_bot_v4.py (deployed, rev 37, QC 8/8 PASS)

## Current Scores

| Task Type | Score | Max | Notes |
|-----------|-------|-----|-------|
| Create customer (fr) | 8/8 | 100% | Locked in |
| Unknown task (8/8) | 8/8 | 100% | Locked in |
| Register payment | 2/7 | 29% | v4 fixes customer search, should improve |
| 6/7 task (from auto-submit) | 6/7 | 86% | From session 5 |
| 4/8 task (from auto-submit) | 4/8 | 50% | From session 5 |
| ~25 task types | 0 | 0% | Never attempted |

## Current Phase: Iteration Loop (ACTIVE)

### The Loop

```
SUBMIT (10 runs, auto-submitter)
    |
    v
ANALYZE (score breakdown, Cloud Run logs, group by perfect/partial/broken)
    |
    v
FIX (biggest point gaps first, deploy, syntax check)
    |
    v
SMOKE TEST (health check, 10 sec)
    |
    v
[repeat]
```

### Submission rules
- Small runs (up to 10): I decide, just do it
- Bulk runs (>10): JC approval first
- After each batch: analyze before the next one
- Log everything in EXPERIMENTS.md

### Tools in the loop

| Tool | When | Command |
|------|------|---------|
| Auto-submitter | Submit | `python3 /Volumes/devdrive/github_dev/nmiai-worktree-ops/shared/tools/nlp_auto_submit.py --auto --max 10` |
| Cloud Run logs | Analyze | `gcloud run services logs read tripletex-agent --region europe-west4 --project ai-nm26osl-1779 --limit 50` |
| QC script | Fix (optional) | `python3 agent-nlp/scripts/qc-verify.py [endpoint]` |
| Pre-submit | Smoke test | `bash agent-nlp/scripts/pre-submit.sh` |
| Leaderboard | Track progress | `python3 shared/tools/scrape_leaderboard.py` |

### Fix priority
Whichever task types have the most points left on the table:
- Tier 3 (3x) > Tier 2 (2x) > Tier 1 (1x)
- Broken tasks (0%) > partial tasks > efficiency on perfect tasks

## Completed Phases

### Phase 0-3: Infrastructure + Investigation (DONE)
Local Docker, QC pipeline, Gemini reliability testing, structured workflow decision.

### Phase 4: Build v4 (DONE)
16 task types implemented. QC 8/8 PASS. Deployed rev 37. Zero MALFORMED errors.

## Key Dates

| Time | What |
|------|------|
| Daily 01:00 CET | Rate limits reset |
| Friday (today) | Tier 2 open (2x multiplier) |
| Saturday morning | Tier 3 opens (3x multiplier) |
| Sunday 09:00 | Feature freeze |
| Sunday 15:00 | Competition ends |

## Key Constraints
- 10 submissions per task type per day (resets 01:00 CET)
- 300 total submissions per day
- Bad runs never lower score
- Same task types return (random selection from pool)
- Competition sandbox != dev sandbox (e.g. VAT codes)
