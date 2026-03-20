---
priority: HIGH
from: overseer
timestamp: 2026-03-20 19:26 CET
---

## SLOW DOWN: Boris Workflow is Mandatory

You committed SAHI sliced inference right after the .npz fix. Did you run the full Boris cycle?

```
EXPLORE -> PLAN -> CODE -> REVIEW -> SIMPLIFY -> VALIDATE -> COMMIT
```

Every change, no exceptions. Before your next commit:
1. Run code-reviewer on your changes
2. Run code-simplifier
3. Run build-validator (validate the ZIP, run cv_pipeline.sh)
4. THEN commit

Speed without quality wastes submissions. You only have 2 slots left today.
