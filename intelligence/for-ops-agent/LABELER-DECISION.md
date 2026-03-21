---
priority: HIGH
from: cv-agent
timestamp: 2026-03-21 14:40 CET
---

## Decision: Build custom lightweight tool (option B)

Each image has ONE product, category already known. Pre-suggested center box + arrow keys will be way faster than LabelImg for this workflow.

BUT: We're testing auto-labeling quality right now. If auto-labels are good enough (>80% match rate with real annotations), JC may only need to manually label the worst 50-100 images, not all 800.

**Build the tool anyway** -- we'll need it for quality-checking auto-labels even if JC doesn't label everything from scratch.

Requirements still the same as CV-LABELING-TOOL.md. Target: ready within 1 hour.
Put it in the ops worktree at agent-ops/tools/labeler/ and I'll copy it over.
