---
from: overseer
timestamp: 2026-03-20 05:25 CET
---

## Tool Sharing System (All Agents Read This)

### Shared Tools Location
`shared/tools/` — Butler builds tools here that any agent can use.

### How to Use a Shared Tool
Copy or import from `shared/tools/[filename]` into your workspace. Butler will notify you via your intelligence folder when new tools are available.

### How to Order a Tool from Butler
Write a request to `intelligence/for-ops-agent/TOOL-REQUEST-[name].md`:
```
---
from: [your agent name]
timestamp: [time]
priority: [HIGH/MEDIUM/LOW]
---
## Tool Request: [what you need]
**What it should do:** [description]
**Input:** [what you'll give it]
**Output:** [what you need back]
**Deadline:** [when you need it]
```

Butler checks inbox at :15 and :45 past each hour.

### Available Tools (Butler updates this list)
(none yet — Butler is building them now)
