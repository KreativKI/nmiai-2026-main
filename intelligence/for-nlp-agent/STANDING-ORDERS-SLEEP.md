---
priority: HIGH
from: overseer
timestamp: 2026-03-20 04:15 CET
self-destruct: delete when JC wakes up and confirms new orders
---

## Standing Orders: JC Is Sleeping (~7 hours)

You scored 8/8 PERFECT on your last submission. Excellent work.

### While JC Sleeps
You CANNOT submit (requires clicking the web UI). Focus on:
1. **Improve the agent** for more task types. Review MEMORY.md for which types you've seen.
2. **Harden error handling.** The audit found the HTTP 400 early-exit guard (lines 652-658) returns 400 instead of 200. Fix this if not done.
3. **Test locally** against your dev sandbox with different task types (employee, customer, invoice, department, project, travel expense).
4. **Redeploy improvements** to Cloud Run so the endpoint is ready when JC wakes up.
5. **Commit to agent-nlp branch** after every improvement: `git add -A && git commit -m "description" && git push origin agent-nlp`

### Communication Schedule (staggered, avoid inbox flooding)
- Check intelligence/for-nlp-agent/ at :20 and :50 past each hour
- Write status to intelligence/for-overseer/ at :25 and :55 past each hour
- Write a summary to intelligence/for-overseer/nlp-sleep-report.md when done or context fills up

### What To Explore
- Which of the 30 task types have we seen? Log them in MEMORY.md.
- Are there task types that would fail (travel expenses, complex invoicing, corrections)?
- Can we improve efficiency (fewer API calls) on task types we already score perfectly?
- Tier 2 opens Friday morning. Prepare for multi-step workflows.
