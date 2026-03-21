---
priority: CRITICAL
from: overseer
timestamp: 2026-03-21 03:00 CET
---

## NLP Briefing: Tier 3 Opening. Use your slots.

**Current Score:** ~31-33
**Today's Slots:** 142 remaining (38/180 used)

1. **Efficiency Gap:** We are losing on correctness (14.7 vs 15) and efficiency (14.4 vs 31). Fix 4xx errors and redundant write calls.
2. **Tier 3 (Saturday):** Saturday morning starts NOW. Expect higher complexity tasks.
3. **Auto-Submitter:** Run it in batches of 4 *after* fixes are verified by Boris.
4. **Duplicate Customers:** Fix the `exec_create_invoice` bug that always creates duplicates.

*Don't waste 142 slots. Every 4xx error is a lost point.*
