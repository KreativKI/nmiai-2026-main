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
## Pre-Submission Toolchain (MANDATORY before every submission)
1. `python3 shared/tools/ml_judge.py predictions.json` — validate shape, floors, normalization
2. `python3 shared/tools/ml_judge.py predictions.json --ground-truth gt.json` — score if GT available
3. If validation fails: `python3 shared/tools/ml_judge.py predictions.json --fix --output fixed.json`

Additional tools:
- `shared/tools/oracle_sim.py --track ml` — theoretical score ceiling
- `shared/tools/ab_compare.py` — compare two prediction versions

## Shared Tools Location
All shared tools are in `shared/tools/`. Read TOOLS.md there for full inventory.
Request new tools from Butler via intelligence/for-ops-agent/TOOL-REQUEST-[name].md
```

Commit after updating: "Update CLAUDE.md with pre-submission toolchain"
