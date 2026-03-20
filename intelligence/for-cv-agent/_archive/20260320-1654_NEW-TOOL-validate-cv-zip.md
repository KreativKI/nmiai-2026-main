---
from: butler
timestamp: 2026-03-20 06:00 CET
---
## New Tool: validate_cv_zip.py
**Location:** shared/tools/validate_cv_zip.py
**What it does:** Validates a NorgesGruppen submission ZIP before uploading. Checks: run.py at root, blocked imports (os, sys, subprocess, etc.), weight file sizes (420 MB limit), file counts (10 .py max, 3 weight max), CLI interface (--input/--output flags).
**How to use:** `python3 shared/tools/validate_cv_zip.py path/to/submission.zip`
**JSON output:** `python3 shared/tools/validate_cv_zip.py path/to/submission.zip --json`
