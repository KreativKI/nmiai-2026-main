---
priority: HIGH
from: overseer
timestamp: 2026-03-20 04:15 CET
self-destruct: delete when JC wakes up and confirms new orders
---

## Standing Orders: JC Is Sleeping (~7 hours)

### Your Tasks
1. **Fix dashboard loading issues.** Use Playwright to validate all dashboard views load correctly. Fix anything broken.
2. **Add CV submission viewer.** JC wants to be able to view/inspect submission ZIPs (like submission_yolo11m_v1.zip) in the dashboard: show detected bounding boxes on images, model info, validation status.
3. **Improve existing tools.** Review tools from /Volumes/devdrive/github_dev/NM_I_AI_dash/tools/ and adapt useful ones.
4. **Build pre-submission validation tools:**
   - CV: validate ZIP structure (run.py at root, no blocked imports, weight size < 420MB)
   - NLP: endpoint health check with test request
5. **Commit to agent-ops branch** after every task.

### Communication Schedule (staggered)
- Check intelligence/for-ops-agent/ at :15 and :45 past each hour
- Write status to intelligence/for-overseer/ at :20 and :50 past each hour
- Write summary to intelligence/for-overseer/ops-sleep-report.md when done or context fills up

### What NOT To Do
- Do NOT touch solution code in agent-cv/, agent-ml/, agent-nlp/
- Do NOT make any competition submissions
- Do NOT automate platform UI clicks
