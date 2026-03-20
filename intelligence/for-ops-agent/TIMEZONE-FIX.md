---
priority: HIGH
from: overseer
timestamp: 2026-03-20 21:50 CET
---

## Timezone: Oslo = CET = UTC+1

Norway is on CET (UTC+1) until March 29 when DST switches to CEST (UTC+2).

**When reporting times to JC, always use Oslo time (UTC+1).**

To convert API timestamps (UTC) to Oslo: add 1 hour.

Quick reference for current round timing:
```python
from datetime import timezone, timedelta
OSLO = timezone(timedelta(hours=1))  # CET, NOT hours=2
```

Do NOT use hours=2. That's CEST which doesn't start until March 29.
