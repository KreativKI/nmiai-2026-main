---
priority: HIGH
from: overseer
timestamp: 2026-03-20 05:05 CET
self-destruct: delete when JC wakes up and confirms new orders
---

## Standing Orders: JC Is Sleeping

You scored 8/8 PERFECT on create_customer. Bot is live. Cannot submit while JC sleeps.

### IMPORTANT FOR WHEN JC WAKES UP
The platform allows 3 CONCURRENT submissions. JC should click Submit 3 times quickly each batch for maximum task type coverage. Rate limit: 5 per task type per day, resets 01:00 CET.

### FIRST: Update Your plan.md

Before doing any work, update your plan.md with a phased work plan. Use the phases below as a starting point but adapt based on your audit of the 30 task types.

**Structure your plan.md like this:**
```
## Current Phase: [N]
## Phases
### Phase 1: [name] — Status: [done/active/pending]
- Tasks...
- Commit: "Phase 1: [description]"

### Phase 2: [name] — Status: [pending]
...
```

Update "Current Phase" as you progress. If context resets, the next session reads plan.md and continues.

**Commit plan.md first:** `git add plan.md && git commit -m "Updated phased plan for sleep mode" && git push origin agent-nlp`

### Suggested Phases (adapt as needed)

**Phase 1:** Audit all 30 task types. Categorize: A) confident, B) should work, C) needs code, D) unknown.
**Phase 2:** Harden top 10 Tier 1 tasks. Test each locally against dev sandbox. Fix failures.
**Phase 3:** Prepare for Tier 2 (opens Friday). Multi-step workflows: invoices, payments, travel expenses.
**Phase 4:** Efficiency optimization. Minimize API calls, zero 4xx errors on perfect scores.
**Phase 5:** Redeploy to Cloud Run. Verify endpoint responds 200.
**Phase 6:** Write sleep report to intelligence/for-overseer/nlp-sleep-report.md.

After Phase 6: loop back, keep testing more task types locally.

### Key Rules
- Do NOT try to submit (requires web UI)
- Commit after EVERY phase
- Update status.json after every phase
- Redeploy to Cloud Run after any code changes
- Check intelligence/for-nlp-agent/ at :20 and :50 past each hour
