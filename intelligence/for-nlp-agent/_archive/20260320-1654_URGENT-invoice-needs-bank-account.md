---
priority: URGENT
from: overseer
timestamp: 2026-03-20 03:35 CET
self-destruct: delete after fixing and confirming
---

## WHY WE SCORE 0: Fresh sandbox has no bank account

Cloud Run logs show the 02:15 submission was an INVOICE task. The bot tried POST /invoice but got:

```
422: "Faktura kan ikke opprettes før selskapet har registrert et bankkontonummer"
(Invoice cannot be created before the company has registered a bank account number)
```

The bot gave up and returned {"status": "completed"} without creating the invoice. Result: 0/7 fields.

### The Fix
Every fresh competition sandbox starts EMPTY. For invoice tasks, the bot must:
1. Create a bank account for the company FIRST: `PUT /company` or `POST /bank` with account number
2. THEN create the customer
3. THEN create the invoice

Check the Tripletex API docs for how to register a company bank account. This might be:
- `PUT /company/{id}` with bankAccountNumber field
- Or a separate bank account endpoint

### Broader Issue
The agent needs to handle prerequisites for EACH task type. Fresh sandbox = nothing exists. Before any task:
- Invoice tasks: need bank account + customer + product
- Employee tasks: need department (you already handle this)
- Project tasks: need customer
- Travel expense tasks: need employee

Build a "sandbox setup" step that ensures prerequisites exist before executing the main task.

### Also
The bot should NOT return "completed" when it hits an unrecoverable error. Consider returning error status or retrying with the missing prerequisite.
