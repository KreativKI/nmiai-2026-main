---
priority: HIGH
from: overseer
timestamp: 2026-03-20 02:20 CET
self-destruct: delete after reviewing the service.py file and confirming in intelligence/for-overseer/
---

## Proven FastAPI Service Pattern Available

Before building your /solve endpoint from scratch, review this existing FastAPI service from a previous competition:

**File:** `/Volumes/devdrive/github_dev/NM_I_AI_dash/solver/service.py`

This wraps a solver as an HTTP API. Adapt the pattern for your Tripletex /solve endpoint. Key things to reuse:
- Request/response structure
- Error handling patterns
- Health check endpoint

Also useful:
- `/Volumes/devdrive/github_dev/NM_I_AI_dash/tools/pipeline.py` — automated auth + submission pipeline pattern
- `/Volumes/devdrive/github_dev/NM_I_AI_dash/tools/login.py` — auth token management (Playwright-based)
- `/Volumes/devdrive/github_dev/NM_I_AI_dash/tools/lib.py` — shared HTTP helpers, constants

Do NOT copy blindly. Adapt what's useful for the Tripletex task.

Confirm receipt by writing to intelligence/for-overseer/nlp-toolbox-ack.md
