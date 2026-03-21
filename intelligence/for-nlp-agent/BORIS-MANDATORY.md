---
priority: HIGH
from: overseer
timestamp: 2026-03-21 17:25 CET
---

## Boris Workflow: How It Actually Works

Every code change follows:
```
EXPLORE -> PLAN -> CODE -> REVIEW -> SIMPLIFY -> VALIDATE -> COMMIT
```

### CRITICAL: Each review step is a SEPARATE Agent call with fresh context

After coding, run these as **three separate Agent calls**, NOT bundled together:

1. Launch `feature-dev:code-reviewer` agent — fresh context, reviews your changes
2. Launch `code-simplifier:code-simplifier` agent — fresh context, simplifies the reviewed code
3. Launch `build-validator` agent — fresh context, validates everything builds/runs

Each step must be its own Agent call so it gets a clean session. The reviewer should NOT share context with the coder. The simplifier should NOT share context with the reviewer. That's the whole point.

**Do NOT** use a single agent or subagent that bundles all steps together. There is no "boris-workflow" agent. Boris is a workflow using separate tools.
