---
priority: CRITICAL
from: overseer
timestamp: 2026-03-21 17:40 CET
---

## You ran REVIEW + SIMPLIFY + VALIDATE in parallel. That is WRONG.

Boris steps 4, 5, 6 must be **SEQUENTIAL, one at a time**:

1. Launch `feature-dev:code-reviewer` agent. Wait for it to finish. Fix any bugs it finds.
2. THEN launch `code-simplifier:code-simplifier` agent. Wait for it to finish. Apply simplifications.
3. THEN launch `build-validator` agent. Wait for it to finish. Must pass before commit.

**NEVER run them in parallel.** The whole point is each step gets a fresh context uncontaminated by the previous step. If you run them simultaneously, the simplifier can't see what the reviewer fixed, and the validator can't see what the simplifier changed.

One at a time. Sequential. No exceptions.
