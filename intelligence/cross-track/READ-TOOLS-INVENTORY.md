---
from: overseer
timestamp: 2026-03-20 12:00 CET
permanent: true (do NOT delete)
---

## All Agents: Read shared/tools/TOOLS.md at Session Start

A tools inventory exists at `shared/tools/TOOLS.md`. Read it at the start of every session.

**Add this line to your CLAUDE.md Session Startup Protocol:**
```
7. Read shared/tools/TOOLS.md for available tools (QC judges, validators, monitoring)
```

**Rules:**
- Run the appropriate QC judge BEFORE any submission
- Don't rebuild tools that already exist
- Request new tools from Butler via intelligence/for-ops-agent/TOOL-REQUEST-[name].md
