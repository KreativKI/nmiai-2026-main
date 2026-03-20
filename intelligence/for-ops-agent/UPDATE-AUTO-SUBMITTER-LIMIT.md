---
priority: HIGH
from: overseer
timestamp: 2026-03-20 15:45 CET
self-destruct: after updating, delete
---

## Auto-Submitter: Update --max Default

Rate limits confirmed increased: 10 per task type per day (was 5).
Total daily budget: 300 (was 150).

Update nlp_auto_submit.py:
- Default --max from 112 to 225 (75% of 300)
- Update any comments referencing "150/day" or "5 per type"
