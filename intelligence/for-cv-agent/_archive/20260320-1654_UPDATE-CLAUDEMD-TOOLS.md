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
Run ALL tools in order. If any fails, do NOT submit.

1. `python3 shared/tools/validate_cv_zip.py submission.zip` — blocked imports, sizes, structure
2. `python3 shared/tools/cv_profiler.py submission.zip` — timing check vs 300s timeout
3. `python3 shared/tools/cv_judge.py --predictions-json predictions.json` — score vs holdout
4. `python3 shared/tools/ab_compare.py --a prev_best.json --b new.json` — compare vs previous best

Additional tools:
- `shared/tools/batch_eval.py` — rank all submission ZIPs
- `shared/tools/oracle_sim.py --track cv` — theoretical score ceiling

## Shared Tools Location
All shared tools are in `shared/tools/`. Read TOOLS.md there for full inventory.
Request new tools from Butler via intelligence/for-ops-agent/TOOL-REQUEST-[name].md
```

Commit after updating: "Update CLAUDE.md with pre-submission toolchain"
