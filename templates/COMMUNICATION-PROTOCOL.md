# Communication Protocol

## Folder Structure

```
nmiai_multiagent/
+-- intelligence/
|   +-- cross-track/              # Matilda -> All agents
|   |   +-- SPEC-DIGEST.md
|   |   +-- PRIORITY-RECOMMENDATION.md
|   |   +-- RULES-CHECK-REMINDER.md
|   |   +-- DAILY-BRIEF-{date}.md
|   +-- for-cv-agent/             # Matilda -> CV agent
|   +-- for-ml-agent/             # Matilda -> ML agent
|   +-- for-nlp-agent/            # Matilda -> NLP agent
|   +-- for-matilda/              # Any agent -> Matilda
|   +-- for-jc/                   # Matilda -> JC (decisions needed)
|       +-- STATUS-BOARD.md
|       +-- DECISION-NEEDED-{topic}.md
```

## Intel File Format

Every file in intelligence/ follows this format:

```markdown
# {TITLE}
**From:** {agent}  **To:** {recipient}  **Date:** {ISO timestamp}
**Priority:** CRITICAL / HIGH / NORMAL / FYI
**Action Required:** {yes/no} -- {what action}

## Summary (3 sentences max)

## Details

## Implications
```

## Priority Levels

- **CRITICAL**: Blocks progress. Needs response within 15 minutes.
- **HIGH**: Important decision needed. Response within 1 hour.
- **NORMAL**: Useful information. Check at next build cycle.
- **FYI**: Background context. Read when convenient.

## status.json Schema

Each agent maintains status.json in their workspace root:

```json
{
  "agent": "agent-cv",
  "timestamp": "2026-03-19T18:30:00+01:00",
  "track": "computer-vision",
  "phase": "build",
  "state": "coding",
  "approach": "A",
  "confidence": 0.7,
  "local_score": 0.82,
  "best_submitted_score": 0.78,
  "submissions_count": 3,
  "blockers": [],
  "hours_since_improvement": 1.5,
  "rules_last_read": "2026-03-19T18:15:00+01:00"
}
```

**States:** waiting -> recon -> researching -> planning -> coding -> testing -> optimizing -> done
**Phases:** recon -> research -> plan -> build -> polish -> done

## Communication Rules

A. Agents NEVER communicate directly. All flows through intelligence/.
B. Matilda reads all status.json every 30 minutes.
C. JC reads intelligence/for-jc/STATUS-BOARD.md whenever convenient.
D. CRITICAL items: Matilda writes DECISION-NEEDED-{topic}.md immediately.
E. Agents check their intelligence folder at start of every build cycle.
F. No agent modifies another agent's files. Ever.

## Escalation Path

```
Agent detects blocker
  -> Writes to intelligence/for-matilda/BLOCKER-{topic}.md (CRITICAL)
  -> Updates status.json: blockers: ["description"]
  -> Matilda reads within 15 min
  -> If Matilda can resolve: writes solution to intelligence/for-{track}-agent/
  -> If Matilda cannot resolve: writes DECISION-NEEDED to intelligence/for-jc/
  -> JC decides, writes response to intelligence/for-{track}-agent/
```

## STATUS-BOARD.md Format (for JC)

```markdown
# Status Board
**Updated:** {ISO timestamp}
**Time remaining:** {hours to deadline}

## Track Summary
| Track | Phase | Score | Confidence | Blocker |
|-------|-------|-------|------------|---------|
| CV    | build | 0.82  | 0.7        | none    |
| ML    | plan  | 0.45  | 0.5        | none    |
| NLP   | recon | --    | 0.3        | API key |

## Decisions Needed
- {list or "none"}

## Recommendation
{Matilda's strategic recommendation}
```
