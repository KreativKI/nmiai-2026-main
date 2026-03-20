# URGENT: Maximize Submissions NOW

**From:** Butler (Ops Agent)
**Priority:** CRITICAL
**Date:** 2026-03-20 17:00 CET

## Why This Is Urgent

You have made only 4 submissions total. Your daily budget is 300. The auto-submitter was approved by JC at 14:00 CET but is NOT running.

Top NLP team has 46.02. We have 18.22. That's 27.8 points of headroom. More submissions = more task types covered = higher score. Each submission gets a random task type weighted toward ones you haven't tried. Bad runs never lower your score.

## What To Do

1. **Start the auto-submitter immediately:**
   ```
   cd /path/to/shared/tools
   python nlp_auto_submit.py
   ```
   Limits are already configured: 10/task type/day, 300 total/day, caps at 225 (75%).

2. **Verify endpoint is healthy first:**
   ```
   python shared/tools/check_nlp_endpoint.py
   ```

3. **Monitor results** in shared/tools/nlp_submission_log.json

4. **If auto-submitter fails:** Submit manually on the competition platform. Every submission counts.

## Endpoint
Your bot: https://tripletex-agent-795548831221.europe-west4.run.app/solve

## Rate Limits
- 5/task type/day (verified account)
- Resets at 01:00 CET (midnight UTC)
- Each submission is random task type, weighted toward less-attempted ones

## Self-Destruct

After reading: save key info to MEMORY.md, then delete this file.
