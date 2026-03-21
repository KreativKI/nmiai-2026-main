---
priority: CRITICAL
from: overseer (competition Slack announcement)
timestamp: 2026-03-21 00:35 CET
---

## Competition Alert: 403 Errors and Timeout Issues

Three issues from the organizers that may be affecting our scores:

### 1. BETA API endpoints cause 403 (73% of all 403 errors)
Some Tripletex API endpoints are marked [BETA] in the Swagger docs. These return 403.
**Action:** Check EVERY endpoint you call against the Swagger docs. If it says [BETA], find an alternative. One endpoint caused 73% of all 403s across all teams.

### 2. Session tokens are ONE-TIME USE
The platform provides a NEW session token for EACH submission. Your bot must use the token from `tripletex_credentials.session_token` in the request, NOT any cached/stored token. The token STOPS WORKING after you return `{"status": "completed"}`.
**Action:** Verify your code reads `tripletex_credentials.session_token` fresh from each request and never caches it.

### 3. Cloudflare tunnel timeout at 120 seconds (not 300)
The docs said 300s timeout but the Cloudflare tunnel times out at 120 seconds. If your bot takes >120s, score = 0.
**Action:** Check your response times. If any task type takes >120s, optimize it. This is stricter than the documented 300s limit.

### Check your code for these RIGHT NOW:
```python
# Are you caching session tokens? BAD.
# Are you using any [BETA] endpoints? BAD.
# Are any responses taking >120s? BAD.
```

Report findings to intelligence/for-overseer/nlp-status.md.
