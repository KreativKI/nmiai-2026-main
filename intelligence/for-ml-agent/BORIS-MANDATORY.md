---
priority: HIGH
from: overseer
timestamp: 2026-03-20 19:26 CET
---

## Reminder: Boris Workflow on Every Change

Good work abandoning the equilibrium approach when it scored -0.5. That's discipline.

Make sure every code change follows the full cycle:
```
EXPLORE -> PLAN -> CODE -> REVIEW -> SIMPLIFY -> VALIDATE -> COMMIT
```

Before committing: run code-reviewer, code-simplifier, build-validator (backtester).
The canary subagent runs before every submission.
