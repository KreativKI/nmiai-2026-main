---
priority: CRITICAL
from: overseer
timestamp: 2026-03-20 13:30 CET
self-destruct: after updating CLAUDE.md, delete
---

## Add This to Your CLAUDE.md (Session Startup Protocol + Pre-Submission)

### Add to Session Startup Protocol (after step 6):
```
7. Read shared/tools/TOOLS.md for available tools
8. Read EXPERIMENTS.md for what's already been tried
```

### Add new section to CLAUDE.md:
```
## Pre-Submission Toolchain (MANDATORY before every deploy)
1. `python3 shared/tools/check_nlp_endpoint.py` — health check Cloud Run endpoint
2. `python3 agent-nlp/scripts/qc-verify.py [endpoint]` — 7 task types with field verification
3. Do NOT deploy if qc-verify fails

Additional tools:
- `shared/tools/scrape_leaderboard.py` — track leaderboard positions

## Shared Tools Location
All shared tools are in `shared/tools/`. Read TOOLS.md there for full inventory.
Request new tools from Butler via intelligence/for-ops-agent/TOOL-REQUEST-[name].md
```

Commit after updating: "Update CLAUDE.md with pre-submission toolchain"
