# Astar Island — Plan

**Track:** ML | **Task:** Norse World Prediction | **Weight:** 33.33%
**Last updated:** 2026-03-20 03:58 UTC

## Current State
- **Best score:** 39.72 (round 3, rank #33/187)
- **Rounds submitted:** 3 (scored), 4 (pending)
- **Script:** `solutions/astar_v6.py` (phased observation)
- **Top teams:** ~50 per round, ~100+ cumulative with 2-3 rounds

## The Problem
Predict terrain probability distributions on a 40x40 grid after 50 years of stochastic simulation. 50 observation queries per round across 5 seeds. Scored by entropy-weighted KL divergence (0-100). Leaderboard uses weighted cumulative score.

## Key Learnings (rounds 1-4)
- Settlement/Port cells dominate scoring (high entropy, high weight) despite being few
- Round 3: settlements -> empty(70%)/forest(30%) but we predicted settlement(40%) = #1 error
- Hidden params vary hugely between rounds (round 4 had 249 changes vs 37 in round 3)
- Each query returns ONE stochastic realization (different each time)
- Multi-sample stacking on same area gives empirical probability estimates
- 9 queries = full 40x40 coverage on one seed (3x3 tiling with 15x15 viewports)
- Scores are cumulative: submitting every round is critical even with mediocre scores

---

## Phased Work Plan

### Phase A: Score Analysis (when round 4 completes)
**Goal:** Learn from round 4 results, compare with round 3
**Boris:** EXPLORE
- Fetch round 4 ground truth via /analysis endpoint for all 5 seeds
- Compute per-cell-type KL divergence breakdown
- Compare round 4 dynamics with round 3 (was our phased approach better?)
- Check leaderboard position change
- Log all findings in MEMORY.md
**Commit after this phase**

### Phase B: Model Improvement (between rounds)
**Goal:** Fix the #1 error source: settlement/port predictions
**Boris:** PLAN -> CODE -> REVIEW -> VALIDATE
- If round 4 score improved: the phased observation approach works, keep it
- If not: investigate why, adjust blend weights or query strategy
- Potential improvements:
  - Better settlement neighborhood model (distance-weighted, not just binary near/far)
  - Use per-round ground truth to calibrate transition model adaptively
  - Investigate what top teams (~50 score) do differently
**Commit after this phase**

### Phase C: Round 5 Execution (when round opens)
**Goal:** Submit all 5 seeds with best available model
**Boris:** Full workflow per phase
1. `astar_v6.py --phase overview` (9 queries, seed 0 full map)
2. `astar_v6.py --phase analyze` (identify dynamics, 0 queries)
3. `astar_v6.py --phase stack --max-stack 32` (32 queries, 4 passes for ~5 samples/cell)
4. `astar_v6.py --phase secondary --max-secondary 9` (9 queries, seed 1 full coverage)
5. Dry-run validation
6. `astar_v6.py --phase submit`
**Total: 9+32+9=50 queries. Max stacking depth on settlements.**
**Commit after this phase**

### Phase D: Repeat for rounds 6, 7, 8...
**Goal:** Submit every round, accumulate weighted score
- Same v6 phased approach
- After each round: analyze, log, adjust if needed
- Later rounds have higher weights: +5% compounding
- Feature freeze Sunday 09:00 CET (per overseer CLAUDE.md)

---

## Standing Autonomous Rules (JC sleeping)
- Submit every round using v6 phased approach
- Commit after each completed phase
- Push to origin/agent-ml after every 2-3 commits
- Log all experiments in MEMORY.md
- Do NOT modify files outside agent-ml/ (except intelligence/)
- If something breaks: revert to last known good, don't experiment with live rounds

## Scoring Math (verified from MCP docs)
```
score = 100 * exp(-3 * weighted_kl)
```
The 3x multiplier means:
- weighted_kl 0.30 -> score 41 (current)
- weighted_kl 0.20 -> score 55 (+14 points!)
- weighted_kl 0.10 -> score 74 (+33 points!)
Reducing settlement/port KL from 0.52 to 0.20 would be huge.

## Leaderboard = BEST round score (not cumulative)
This changes strategy: we need ONE excellent round, not many mediocre ones.
Investing time in model quality pays more than just submitting every round.

## Answered Questions
- **Stacking vs coverage?** Stacking wins massively. N=1: score ~2 for settlements. N=7: score ~58.
- **Cross-seed transfer quality?** Nearly optimal (0.7 point gap vs perfect).
- **Forest adjacency?** Small effect (26% to 33% survival). Round params dominate.

## Remaining Questions
- Can settlement stats (food, pop) from observations predict per-cell survival?
- What's the theoretical max score with 50 queries?
