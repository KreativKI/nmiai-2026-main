# Overseer Plan -- NM i AI 2026
**Last updated:** 2026-03-21 13:49 CET | **Next refresh:** when scores change | **Remaining:** 25h

## Mode: SEMI-AUTONOMOUS EXECUTION

All 3 track agents have standing orders but require JC approval for key decisions. Overseer monitors via intelligence/for-overseer/ and updates docs.

## Scores

| Track | Score | Rank | Status |
|-------|-------|------|--------|
| **ML** | 71.77 | #49/191 | Autonomous. v3 deployed: dual V2+V3 blend, deep stack, regime-conditional weights. |
| **CV** | 0.6584 | ~mid/105 | 0.816 val model submitted. Now: Gemini shelf images + labeling for next push. |
| **NLP** | ~40-43 | ?/161 | 10/16 tasks at 100%. 180 fresh submissions available. Fixing Travel Expense + Payment Reversal. |

## What Changed (Session 3)
- CV submitted `submission_maxdata.zip` (0.816 val mAP model)
- ML agent active again: v3 with dual V2+V3 blend, deep stack, regime-conditional weights
- NLP exhausted day 1 budget (177/180), now has 180 fresh
- Ops building labeling GUI with Grounding DINO pre-suggestions for CV

## Agent Status

### ML (Astar Island)
- Has a plan, executing autonomously
- v3 deployed with dual V2+V3 blend
- Submitting every round (was silent earlier, now active)

### CV (NorgesGruppen)
- 0.816 val model submitted
- Working on Gemini-generated shelf images (2 VMs parallel)
- Grounding DINO auto-labeling being tested
- Ops building labeling tool if JC manual labeling needed
- 5 submission slots remaining today, 6 fresh Sunday

### NLP (Tripletex)
- 10/16 tasks at 100%, score ~40-43
- 180 fresh submissions available (reset 02:00 CET)
- Priority: fix Travel Expense (0%), Payment Reversal (25%), improve Salary (50-63%)
- Tier 3 tasks may open Saturday

### Ops (Butler)
- Building CV labeling GUI (Grounding DINO + web UI)
- Dashboard available at NM_I_AI_dash

## Overseer Role Now
- Monitor intelligence/for-overseer/ for agent status reports
- QC agent outputs when they report phase completion
- Track scores and adjust priorities if a track stalls
- Update docs when state changes

## Deadlines

| Time | What |
|------|------|
| Saturday 01:00 CET | Rate limits reset (CV 6, NLP 180) |
| Saturday morning | Tier 3 tasks open (NLP 3x multiplier) |
| Saturday 12:00 | CUT-LOSS: any track with 0 = submit baseline |
| Sunday 09:00 | FEATURE FREEZE |
| Sunday 14:45 | Repo goes public (PRIZE ELIGIBILITY) |
| Sunday 15:00 | COMPETITION ENDS |

## Key Findings (carried forward)
- Detection is NOT the bottleneck (TTA +0.002, ensemble +0.000)
- Classification IS the bottleneck (DINOv2 + reference images is the path)
- ML score = best single round, not cumulative. exp(-3*KL)
- NLP: bad runs never lower score, submitting is always safe
- NLP: 10/task/day, 180 total/day (10 x 18 active task types)
- YOLO26m (0.485) non-competitive vs YOLO11 series
