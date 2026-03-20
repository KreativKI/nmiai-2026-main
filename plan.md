# Overseer Plan -- NM i AI 2026
**Last updated:** 2026-03-20 19:00 CET | **Next refresh:** 03:00 CET | **Remaining:** 44h

## Mode: AUTONOMOUS EXECUTION

All agents have standing orders (CONSOLIDATED-ORDERS.md) and GO messages. They execute phase by phase without asking JC. Overseer monitors via intelligence/for-overseer/ status files.

## Scores

| Track | Score | Rank | Status |
|-------|-------|------|--------|
| **ML** | 71.77 (R4) | #49/191 | Autonomous. Executing phases 1-5. Submit every round. |
| **CV** | 0.5756 | ~mid/105 | Autonomous. Phase 1: fix .npz, Phase 2: QC, Phase 3: SAHI |
| **NLP** | 8/8 (1 task) | ?/161 | Autonomous. Phase 1: Tier 2 fix, Phase 2: auto-submitter |

## What Changed This Session
- Added "Autonomous Execution Mode" to all 4 agent CLAUDE.md files
- Added scope restrictions: agents only read their own track + inbox + shared tools
- Removed "ask JC for approval" gates that were blocking autonomous execution
- Dropped GO-EXECUTE.md in all 4 agent inboxes (delivered via PostToolUse hook)
- check_inbox.sh already fixed (.last_check working)

## Overseer Role Now
- Monitor intelligence/for-overseer/ for agent status reports
- QC agent outputs when they report phase completion
- Relay cross-track decisions if needed
- Monitor competition for rule changes
- Track scores and adjust priorities if a track stalls

## Agent Communication System
```
Overseer writes to: intelligence/for-{agent}-agent/*.md
Agents write to:    intelligence/for-overseer/{agent}-status.md
Hook delivers:      PostToolUse fires check_inbox.sh on every Bash call
                    Agent sees "NEW MESSAGES" alert, reads inbox
```

## Deadlines

| Time | What |
|------|------|
| Tonight 01:00 CET | Rate limits reset (CV 6, NLP 300) |
| Friday (today) | Tier 2 tasks live (NLP 2x multiplier) |
| Saturday morning | Tier 3 tasks (NLP 3x multiplier) |
| Saturday 12:00 | CUT-LOSS: any track with 0 = submit baseline |
| Sunday 09:00 | FEATURE FREEZE |
| Sunday 14:45 | Repo goes public (PRIZE ELIGIBILITY) |
| Sunday 15:00 | COMPETITION ENDS |

## Key Findings (carried forward)
- Detection is NOT the bottleneck (TTA +0.002, ensemble +0.000)
- Classification IS the bottleneck (DINOv2 + reference images is the path)
- ML score = best single round, not cumulative. exp(-3*KL).
- NLP: bad runs never lower score, submitting is always safe
- NLP: 10/task/day, 300 total/day (verified from platform)
