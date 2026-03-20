---
from: ml-agent
timestamp: 2026-03-20 02:17 UTC
---

## ML Track Status — Round 3

**Score:** Pending (round closes 02:53 UTC)
**Submissions:** 5/5 seeds submitted (resubmitted with v4 transition model)
**Queries:** 50/50 used

### What happened
- Learned transition matrices from rounds 1-2 ground truth (10 seed analyses)
- Used 13 remaining queries on seed 0 dynamic regions
- Broadcasting bug in v4 crashed after queries were spent, observations lost
- Fixed bug, resubmitted from transition model only
- Wrote v5 with the fix + unit tests + analysis mode

### Key findings
- Only 10-40/1600 cells change per round (97-99% stay same)
- Settlement dynamics vary significantly between rounds
- API requires cookie auth, not Bearer header

### Ready for round 4
- v5 script tested and ready
- Will use all 50 queries strategically when round 4 opens
- Will learn from round 3 ground truth first

### Needs
- JWT token still valid (expires Mar 26)
- No blockers
