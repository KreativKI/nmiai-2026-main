---
priority: HIGH
from: overseer
timestamp: 2026-03-20 19:26 CET
---

## Reminder: Boris Workflow on Every Change

v4 is a big jump from v3. Before deploying:
```
EXPLORE -> PLAN -> CODE -> REVIEW -> SIMPLIFY -> VALIDATE -> COMMIT
```

1. Run code-reviewer on tripletex_bot_v4.py
2. Run code-simplifier
3. Run build-validator (syntax check + qc-verify.py against endpoint)
4. Run canary subagent before submission
5. THEN deploy and commit

A broken deploy wastes more time than a proper review cycle saves.
