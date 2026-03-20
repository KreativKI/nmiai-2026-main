# NM i AI 2026 — Rules Digest

**Source:** https://app.ainm.no/rules (last updated 2026-03-19 20:24 — post-kickoff)

## Critical Numbers
- **Start:** Thursday March 19, 18:00 CET (tasks at ~18:15)
- **Deadline:** Sunday March 22, **15:00 CET** (NOT 18:00!)
- **Duration:** 69 hours
- **Prize pool:** 1,000,000 NOK (400K/300K/200K + 100K U23 prize)

## Scoring
- 3 independent tasks, equal weight (33.33% each)
- Each task normalized 0-100 (divided by highest score across all teams)
- Overall score = average of 3 normalized scores
- **Zero on any task = 0 for that 33.33%.** All 3 must have submissions.
- Tie-breaker: earliest timestamp of submission that produced the tying score

## Prize Eligibility (BOTH required)
1. **Vipps verification** (BankID) before deadline
2. **Public code repo URL** submitted through platform before deadline (MIT license)

## Explicitly ALLOWED
- AI coding assistants (ChatGPT, Claude, Copilot, etc.)
- Publicly available models, datasets, research papers, open-source libraries

## Explicitly PROHIBITED
- Sharing solutions/code/weights between teams
- Multiple accounts or teams
- **Automated scraping, monitoring, or analysis of other teams' activity** ← our social intelligence monitor must stay OFF
- Hardcoded/pre-computed responses
- Circumventing rate limits
- Attacking platform infrastructure

## Team
- 1-4 members. Roster locks after first submission in any task.
- Teams responsible for own infrastructure.

## Code Submission
- Must contain: inference code, training scripts, custom tooling
- Must demonstrate original work by the team
- Publicly accessible (GitHub/GitLab/Bitbucket)
- MIT license required

## Task Metrics & Rate Limits (LIVE post-kickoff)
| Task | Metric | Response Limit |
|------|--------|----------------|
| Tripletex (AI accounting agent) | Score per task (rolling avg) | 300s |
| Astar Island (Norse world prediction) | KL Divergence (0–100) | 60s |
| NorgesGruppen Data (object detection) | mAP@0.5 | 360s |

## U23 Prize (CONFIRMED — was "Category X")
- 100,000 NOK to highest-ranking team where ALL members are under 23 at March 22, 2026
- Combinable with placement prizes

## MCP Server (from /docs)
```
claude mcp add --transport http nmiai https://mcp-docs.ainm.no/mcp
```

## PLAYBOOK CORRECTIONS NEEDED
- Deadline is 15:00 CET, not 18:00. Final submission window is tighter.
- Category X = U23 prize (CONFIRMED at kickoff, combinable with placement)
