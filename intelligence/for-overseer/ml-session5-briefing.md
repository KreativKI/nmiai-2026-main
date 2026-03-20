---
from: agent-ml
timestamp: 2026-03-20 21:30 UTC
priority: CRITICAL — Full session briefing + overnight plan
---

## ML Track — Session 5 Complete Briefing

### R9 Result: 82.6 (BEST ROUND)
- Rank 93/221, weight 1.551
- Seeds: 80.9, 82.8, 82.8, 83.4, 83.0
- This was a stable round where the model performed well across all seeds

### R10: Submitted with V7 (first multi-seed submission)
- Regime detected: GROWTH (8% survival, 7 new settlements)
- All 5 seeds observed (first time ever)
- 72K training cells from 9 rounds
- Score pending, closes 00:45 CET

### All Scores
| Round | Score | Rank | Regime |
|-------|-------|------|--------|
| R3 | 39.7 | 33/100 | extinction |
| R4 | 71.8 | 49/86 | extinction |
| R5 | 67.6 | 69/144 | stable |
| R6 | 70.4 | 52/186 | growth |
| R7 | 55.1 | 112/199 | growth |
| R8 | 61.8 | 126/214 | extinction |
| R9 | **82.6** | 93/221 | stable |
| R10 | pending | - | growth |

### What Changed This Session

**A. Mistakes identified:**
- R1-R2 missed entirely (agent not running)
- R3, R8 scored badly because we didn't detect extinction rounds
- 80% of every submission was guesswork (only observed seed 0)

**B. Hidden rules discovered:**
- Three regimes: extinction / stable / growth
- Settlement spread has distance cutoff (3-12 per round)
- Ports ONLY on coast (100% rule)
- Forests consumed by adjacent settlements
- Ground truth = 200 MC runs
- R8 was extinction (we missed it, scored 61.8 instead of ~70+)
- Full report: agent-ml/solutions/data/hidden_rules_analysis.md

**C. V7 built and deployed:**
- Regime-first query protocol: 5 queries on known settlements, detect regime, then observe all seeds
- Backtest: avg 70.3 (vs V6's 63.6 = +6.7)
- Death rounds: +30 points from regime detection
- Multi-seed: all 5 kitchens observed instead of just seed 0

**D. Overseer briefing cross-referenced:**
- Overseer's regime-first protocol tested and CONFIRMED better (+4.4 vs blind overview)
- Official transcript confirms: 3 hidden params (growth, raids, winter)
- R8 confirmed extinction (overseer data)

### Overnight Plan (JC sleeping ~00:00 CET)

**GCP VM autonomous operation:**
1. Script runs every 5 min, checks for new rounds
2. When round opens: run v7 (regime detect, observe all seeds, submit)
3. When round closes: cache ground truth, retrain model
4. Each round makes model smarter (continuous learning)
5. All activity logged to overnight_log.txt

**Overseer should:**
- Monitor that submissions are happening (check /my-rounds)
- Alert if any round gets missed
- Note: ML agent has FULL SUBMIT AUTONOMY per CLAUDE.md
- Do NOT hold queries or submissions overnight

### Key Numbers for Overseer
- Competition ends: Sunday 15:00 CET
- Feature freeze: Sunday 09:00 CET
- Remaining rounds: ~5-6 (every ~3h)
- Each round's weight increases +5% (R11 weight ~1.71)
- Leaderboard = BEST round score (not cumulative)
- Our best: 82.6. Competitor benchmark: 91.49.
- Gap to close: ~9 points

### Files Updated
- agent-ml/plan.md — full phase plan
- agent-ml/EXPERIMENTS.md — all experiments logged
- agent-ml/solutions/astar_v7.py — latest submission script
- intelligence/for-overseer/hidden-rules-discovery.md — rules for cross-check
