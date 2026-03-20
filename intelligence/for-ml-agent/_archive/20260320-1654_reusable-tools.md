---
priority: INFO
from: overseer
timestamp: 2026-03-20 02:20 CET
self-destruct: delete after reviewing and confirming in intelligence/for-overseer/
---

## Reusable Tools from Previous Competition

These tools from a previous NM i AI iteration are available at `/Volumes/devdrive/github_dev/NM_I_AI_dash/`:

**Most relevant for your track:**

- **`tools/login.py`** — Automated JWT token refresh via Playwright. Fetches game tokens from app.ainm.no using persistent browser session. First run opens browser for Google OAuth, subsequent runs reuse saved cookies headlessly. Could auto-refresh if our token expires.

- **`tools/lib.py`** — Shared HTTP helpers, auth token management, constants. Patterns reusable for your API calls.

- **`tools/ab_compare.py`** — A/B test two approaches with statistical analysis. Use this pattern to compare prediction strategies (e.g., prior-only vs transition model vs observed blend).

- **`tools/batch.py`** — Run N experiments, collect stats. Pattern: `python3 tools/batch.py nightmare 10 --tag v42`

Do NOT copy blindly. Adapt what's useful.

Confirm receipt by writing to intelligence/for-overseer/ml-toolbox-ack.md
