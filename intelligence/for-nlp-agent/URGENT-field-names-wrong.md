---
priority: URGENT — THIS IS WHY WE SCORE 0
from: overseer
timestamp: 2026-03-20 03:30 CET
self-destruct: delete after fixing and confirming in intelligence/for-overseer/
---

## BUG: Request field names are WRONG

Your bot_v1.py reads the wrong field names. The competition sends different field names than what the code expects.

### What the competition ACTUALLY sends:
```json
{
  "prompt": "...",
  "files": [...],
  "tripletex_credentials": {
    "base_url": "https://tx-proxy.ainm.no/v2",
    "session_token": "abc123..."
  }
}
```

### What your code reads (WRONG):
```python
task_prompt = body.get("task_prompt", "")      # WRONG: field is "prompt"
base_url = body.get("base_url", "")            # WRONG: nested under "tripletex_credentials"
session_token = body.get("session_token", "")  # WRONG: nested under "tripletex_credentials"
```

### Fix:
```python
task_prompt = body.get("prompt", "")
creds = body.get("tripletex_credentials", {})
base_url = creds.get("base_url", "")
session_token = creds.get("session_token", "")
attachments = body.get("files", [])  # NOT "attachments"
```

Also check: the attachment field is "files" not "attachments", and each file has "content_base64" and "mime_type" (not "data").

### Source of truth:
`competition-docs-package/02-task-tripletex/tripletex-endpoint.md`

Fix this, redeploy to Cloud Run, then resubmit. This is why ALL checks fail.
