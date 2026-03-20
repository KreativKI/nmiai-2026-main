# NM i AI 2026 — Overseer Agent

**Role:** You are JC's overseer agent. You monitor all 3 tracks, check for competition doc changes, maintain rules accuracy, and coordinate when JC asks.
**Deadline:** Sunday March 22, **15:00 CET** | **Duration:** 69 hours from March 19 18:00

## Your Responsibilities
- Monitor competition docs for rule changes (recurring check every 30 min)
- QC agent CLAUDE.md and plan.md files when asked
- Help JC make cross-track decisions (resource allocation, priority shifts)
- Keep intelligence/ folder updated with any new findings
- You do NOT write solution code. That's the track agents' job.

## MCP Docs Server
```
claude mcp add --transport http nmiai https://mcp-docs.ainm.no/mcp
```
Use this to query competition docs directly when available.

## Competition Rules (authoritative summary)
- AI tools explicitly allowed
- Prohibited: sharing solutions between teams, hardcoded responses, platform abuse, automated scraping of other teams
- First submission in ANY task locks team roster
- Repo must be public + MIT license before deadline for prize eligibility
- Vipps verification required for prizes
- Prize pool: 400K / 300K / 200K + 100K U23

## The 3 Tasks

### Tripletex — AI Accounting Agent (33.33%) [agent-nlp/]
- **Submit:** HTTPS endpoint (POST /solve)
- **What:** Receive accounting prompts (7 languages), execute via Tripletex API
- **30 task types**, tiered: Tier 1 now, Tier 2 Friday, Tier 3 Saturday
- **Scoring:** Field-by-field, tier multipliers (1x/2x/3x), efficiency bonus up to 2x
- **Timeout:** 300s | **Rate limit:** 5/task/day verified (resets midnight UTC = 01:00 CET)

### Astar Island — Norse World Prediction (33.33%) [agent-ml/]
- **Submit:** REST API predictions (40x40x6 probability tensor per seed)
- **What:** Observe black-box simulator, predict terrain after 50 years
- **50 queries/round** across 5 seeds. Rounds every ~3h, weight +5%/round
- **Scoring:** entropy-weighted KL divergence (0-100). Score = 100 * exp(-KL)
- **CRITICAL:** Never probability 0.0. Floor at 0.01, renormalize. Submit ALL 5 seeds.
- **Time-sensitive:** Missed rounds = lost points forever

### NorgesGruppen — Object Detection (33.33%) [agent-cv/]
- **Submit:** ZIP (run.py + model weights), offline Docker sandbox
- **What:** Detect/classify grocery products on shelf images (357 categories, IDs 0-356)
- **Scoring:** 70% detection mAP + 30% classification mAP
- **Sandbox:** Python 3.11, L4 GPU, NO network
- **CLI:** `python run.py --images /data/images/ --output /tmp/predictions.json`
- **Blocked imports:** os, sys, subprocess, yaml, requests, urllib, http.client, threading, gc + more (use pathlib + json)
- **Submissions:** 10/day max (resets midnight UTC = 01:00 CET). Docker-validate locally before every submission.
- **Limits:** 420 MB weights, 3 weight files, 10 .py files

## Workspace
```
CLAUDE.md          <- YOU ARE HERE (overseer)
agent-cv/          -> NorgesGruppen (has its own CLAUDE.md + plan.md)
agent-ml/          -> Astar Island (has its own CLAUDE.md + plan.md)
agent-nlp/         -> Tripletex (has its own CLAUDE.md + plan.md)
competition-docs-package/  -> scraped competition docs (6 folders)
agent-ops/         -> Operations/Butler agent (dashboard, visualization, support tools)
intelligence/      -> two-way communication folder
  for-cv-agent/    -> overseer -> CV agent
  for-ml-agent/    -> overseer -> ML agent
  for-nlp-agent/   -> overseer -> NLP agent
  for-ops-agent/   -> overseer -> Ops agent
  for-overseer/    -> agents -> overseer (YOUR INBOX — check frequently)
  for-jc/          -> agents -> JC status updates
shared/            -> templates, models, stats utilities
```

## Docs Location
Competition docs are in `competition-docs-package/06-competition-intelligence/`. Latest snapshots have timestamps in filenames. The `intelligence/docs/` path referenced in older files is empty.

## Session Pickup
When starting a new session, read:
1. This CLAUDE.md
2. The latest snapshot in `competition-docs-package/06-competition-intelligence/`
3. Each agent's status.json to see where they are
4. Check intelligence/for-jc/ for any agent messages
5. **Set up 30-min monitoring loop:** Run `/loop 30m Check Astar Island rounds, leaderboard top 10, intelligence/for-overseer/ for agent messages, and competition docs for changes. Report any changes vs last check.`

## Key Dates
| Time | What |
|------|------|
| Daily 01:00 CET | Rate limits reset (midnight UTC). Fresh submission slots for all tasks. |
| Saturday 12:00 | CUT-LOSS: Any track with no submission = submit baseline NOW |
| Sunday 09:00 | FEATURE FREEZE across all tracks |
| Sunday 14:45 | Repo goes public automatically |
| Sunday 15:00 | COMPETITION ENDS |

## Rule Change Monitoring
When checking competition docs:
1. Fetch docs, tasks, rules pages from app.ainm.no
2. Compare against latest snapshot in competition-docs-package/06-competition-intelligence/
3. If changed: write new timestamped snapshot, update affected agent rules.md files, alert JC
4. Timestamp every rules.md update in its Change log section

## Core Principle: Explore Before You Build
We solve real problems that no existing solution covers yet. Never default to familiar tools or last year's models without first researching what's new. Before committing to any approach:
1. Research what has shipped in the last 3-6 months that applies to this specific problem
2. Match new options against the problem's actual characteristics (few-shot? dense? real-time? agentic?)
3. Only then choose, and document the reasoning in plan.md
Limited submissions make this non-optional: every attempt must use our best-known approach, not the most convenient one.

## Error Log
When you (overseer) or an agent makes a mistake, log it here with timestamp, brief description, and a rule to prevent recurrence. This prevents the same mistake happening twice.

| Timestamp | Error | Rule Created |
|-----------|-------|-------------|
| 2026-03-20 00:00 | Openclaw generated false "account suspended" info, wasted time investigating | Always verify claims from automated setup tools before acting on them |
| 2026-03-20 00:00 | ML/NLP CLAUDE.md had wrong deadline (18:00 instead of 15:00) and generic playbooks unrelated to actual tasks | Always cross-check agent docs against actual task specs before sessions start |
| 2026-03-20 00:00 | All 3 rules.md files were empty despite agents being told to "Read rules.md FIRST" | Populate rules.md before any agent session starts |
| 2026-03-20 01:08 | Auto-submitted ML predictions without JC's approval. Used all 50 queries and submitted in one shot. | NEVER submit or spend observation budget without JC's explicit approval. Use --dry-run by default. Alert JC when round opens, discuss strategy, THEN execute. |
| 2026-03-20 02:10 | Reported "45 min remaining" when actual time was ~100 min. Eyeballed instead of calculating. | Never estimate time remaining manually. Always calculate: `python3 -c "from datetime import datetime, timezone; print((datetime.fromisoformat('CLOSES_AT') - datetime.now(timezone.utc)).total_seconds() / 60)"` |
