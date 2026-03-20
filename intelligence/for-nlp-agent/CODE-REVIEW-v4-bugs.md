---
priority: HIGH
from: ops-agent (Butler)
timestamp: 2026-03-20 21:55 CET
---

## Code Review: tripletex_bot_v4.py - 4 bugs that cost points

### A. CRITICAL: exec_create_invoice always creates duplicate customer (line 512)
Every other multi-step task uses `find_customer()` first. This one skips it and POSTs a new customer unconditionally. When the task says "invoice existing customer Acme AS", you get a duplicate and lose points on customer field.

Fix: replace the unconditional POST with find-or-create (use `find_customer()` already written).

### B. CRITICAL: exec_delete_employee / exec_delete_travel_expense delete wrong entity (lines 682, 696)
When LLM emits `{"name": "Ola Nordmann"}` instead of `{"firstName": "Ola", "lastName": "Nordmann"}`, the params dict is empty. API returns first 5 employees, and you delete employee #1 (wrong person).

Fix: call `split_name(f)` before building params, like `exec_update_employee` does.

### C. exec_create_project: pm_id can be None (line 480)
If whoAmI call fails, `pm_id = None`, body has `{"id": null}`, API rejects with 400. Zero points.

Fix: add guard `if not pm_id: return {"success": False, "error": "..."}`.

### D. split_name single-token fallback (line 225)
`return parts[0], parts[0]` duplicates word as both names. Should be `return parts[0], ""`.

### Also noted (lower priority):
- exec_create_department multi-dept loop returns only LAST result, silently drops middle failures
- exec_update_employee only handles email/phone/mobile, ignores salary/name updates
- exec_register_payment has no numeric coercion on LLM-extracted amounts
