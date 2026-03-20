# ML Track Memory

## Session 3: 2026-03-20 02:00-02:15 UTC

### State
- Round 3 active, closes 02:53 UTC. Weight: 1.1576
- All 5 seeds submitted (twice: first v3 at 00:08, then v4 at 02:12)
- 50/50 queries used (37 from v3, 13 from v4)
- Rounds 1-2: MISSED (0 seeds submitted, no scores)
- No score yet (round 3 not yet scored)

### Experiment 1: v4 observation + resubmit
**Date:** 2026-03-20 02:10 UTC
**Round:** 3
**Approach:** v4 (learned transitions + 13 targeted observations on seed 0)
**Change:** Used 13 remaining queries on seed 0 dynamic regions, tried to blend observations
**Hypothesis:** Round-specific observations should improve predictions vs transition-only model
**Score before:** unknown (round 3 first submission)
**Score after:** pending (round not yet scored)
**Delta:** unknown
**Kept/Reverted:** kept (submitted)
**Time spent:** 0.25h
**Notes:** Broadcasting bug (obs_total shape 40x40 vs obs_counts 40x40x6) crashed script after queries were spent. Observations LOST. Fixed bug, resubmitted with transition model only. Lesson: ALWAYS dry-run with synthetic observation data before spending real queries.

### Experiment 2: v4 transition-only resubmit
**Date:** 2026-03-20 02:12 UTC
**Round:** 3
**Change:** Resubmitted all 5 seeds with learned transition model (no observations)
**Notes:** Predictions are from rounds 1-2 ground truth transitions. Neighborhood-aware (near/far settlement context). Avg confidence ~77%.

### Learned Transitions (from rounds 1-2 ground truth)
- Empty -> Empty 79%, Settlement 14%
- Settlement -> Settlement 40%, Empty 37%
- Port -> Empty 37%, Port 30%
- Forest -> Forest 70%, Settlement 18%
- Mountain -> Mountain 95%
- Near settlements: Empty -> Settlement 21% (higher than far: 12%)

### Key Issues
- Ruin/Port/Settlement "near" transitions show 16.7% uniform (Laplace smoothing default due to few samples)
- Round 2 seed 1 had 23 settlements -> empty (mass die-off). Hidden params vary significantly between rounds.
- Without round-specific observations, our predictions may not match round 3's dynamics well.

### Round 4 Plan
1. Fix the broadcasting bug (DONE in v4.py)
2. When round 4 opens: use ALL 50 queries strategically
   - Concentrate on seed 0: 20 queries (multiple samples per area for probability estimates)
   - Seed 1: 15 queries
   - Seed 2: 10 queries
   - Seeds 3-4: 5 queries combined (rely on cross-seed transfer)
3. Build round-4-specific transition model from observations
4. Blend with rounds 1-2 learned model (lower weight as we get round-specific data)
5. After round 3 scores: analyze ground truth, identify error patterns

### Rules re-read at 2026-03-20T02:00:00Z. No violations found.

## Auth Note
API uses cookie auth: `access_token` cookie. Bearer header returns "Missing token" in curl.
