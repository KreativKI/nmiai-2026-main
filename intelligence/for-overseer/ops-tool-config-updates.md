---
from: butler
timestamp: 2026-03-20 13:20 CET
priority: HIGH
---
## Request: Update Agent CLAUDE.md Files With Tool References

Butler has built 8 shared tools. Agents need these referenced in their CLAUDE.md files so future sessions know to use them. I can't modify agent CLAUDE.md files directly (solution directory restriction).

### CV Agent CLAUDE.md — add this section:

```markdown
## Pre-Submission Toolchain (MANDATORY before every submission)
Run ALL tools in order. If any fails, do NOT submit.

1. `python3 shared/tools/validate_cv_zip.py submission.zip` — blocked imports, sizes, structure
2. `python3 shared/tools/cv_profiler.py submission.zip` — timing check vs 300s timeout
3. `python3 shared/tools/cv_judge.py --predictions-json predictions.json` — score vs holdout
4. `python3 shared/tools/ab_compare.py --a prev_best.json --b new.json` — compare vs previous best

Additional tools:
- `shared/tools/batch_eval.py` — rank all submission ZIPs (coming soon)
```

### ML Agent CLAUDE.md — add this section:

```markdown
## Pre-Submission Toolchain (MANDATORY before every submission)
1. `python3 shared/tools/ml_judge.py predictions.json` — validate shape, floors, normalization
2. `python3 shared/tools/ml_judge.py predictions.json --ground-truth gt.json` — score if GT available
3. If validation fails: `python3 shared/tools/ml_judge.py predictions.json --fix --output fixed.json`
```

### NLP Agent CLAUDE.md — add this section:

```markdown
## Shared Tools Available
- `python3 shared/tools/check_nlp_endpoint.py` — health check Cloud Run endpoint
- `python3 shared/tools/scrape_leaderboard.py` — track leaderboard positions
```

### All Agents — add:

```markdown
## Shared Tools Location
All shared tools are in `shared/tools/`. Check `intelligence/for-{track}-agent/` for new tool notifications.
```
