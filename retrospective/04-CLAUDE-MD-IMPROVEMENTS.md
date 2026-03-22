# CLAUDE.md Improvements — What to Fix for Next Time

---

## Global CLAUDE.md (~/.claude/CLAUDE.md)

### What's good
- Boris workflow defined
- Safety protocols clear
- Development environment well documented
- Learned rules section captures mistakes

### What to improve

**A. Boris workflow needs the agent names**
Current: "code-reviewer, code-simplifier, build-validator"
Better: The exact subagent_type names, the sequential requirement, and the anti-pattern (never parallel, never bundled).
Status: Fixed during competition. Current version is correct.

**B. Add "verify before trusting" rule**
Missing: A rule that says "never trust subagent claims about specific API values, enum options, or configuration details. Always test against the real system."
This cost us the userType regression in NLP.

**C. Add "explore before building" enforcement**
The rule exists ("Research what shipped in last 3-6 months") but agents ignored it under time pressure. Needs to be a hard gate: "DO NOT write code until you've filed an exploration report listing 3 alternatives you considered."

**D. Add negative constraints for every positive rule**
For every "do X" rule, add "NEVER do Y" to close the loophole. LLMs find creative ways to satisfy the letter of a rule while violating the spirit.

---

## Project CLAUDE.md (/Volumes/devdrive/github_dev/.claude/CLAUDE.md)

### Issues found
- Very long (300+ lines). Agents may not read the whole thing.
- Film analogies are helpful for JC but add length for agents.
- Project status section (Q1-Q4 2026 priorities) is outdated.
- Multiple sections repeat information from global CLAUDE.md.

### Recommendations
- Trim to <150 lines for agent-facing content
- Move film analogies to a separate reference doc
- Keep project status in a separate STATUS.md (not CLAUDE.md)
- Remove anything duplicated from global CLAUDE.md

---

## Agent CLAUDE.md Files (Competition-Specific)

### Pattern that worked
Each agent CLAUDE.md had:
1. Identity (who you are, what you own)
2. Session startup protocol (what to read first)
3. Boris workflow (mandatory steps)
4. Task description (what the competition asks)
5. Architecture (current state)
6. Resources (tools, paths, APIs)
7. What you NEVER do (anti-patterns)

### What was missing at competition start
- **Deadlines were wrong** in initial CLAUDE.md files
- **rules.md files were empty** (should have been populated pre-competition)
- **Submission ownership was ambiguous** (who submits what)
- **Rate limits weren't verified** against platform
- **Boris workflow was vague** (no agent names, no sequential requirement)

### Template improvements for 2027

Add these sections to every agent CLAUDE.md:

```markdown
## Hard Gates (actions that require JC approval)
- Submitting to competition
- Changing model architecture
- Deploying to production
- Any action that burns rate-limited resources

## Anti-Patterns (things you NEVER do)
- Run Boris steps in parallel
- Trust subagent claims about API values without testing
- Estimate time instead of calculating
- Skip exploration to "save time"
- Auto-submit without throttling

## Verification Checklist (before every submission)
1. Run validation pipeline
2. Check for blocked imports
3. Verify file sizes within limits
4. Test against real data, not simulated
5. Confirm score direction matches expectation
```

---

## Intelligence Folder Protocol

### What worked
- Per-agent inboxes (`intelligence/for-{agent}-agent/`)
- Structured format (frontmatter with priority, from, timestamp)
- Archive subfolder for read messages

### What to add
- **Read receipts:** Agent writes `.last_read` timestamp so overseer knows what's been seen
- **Priority levels:** CRITICAL (read immediately), HIGH (read on startup), LOW (read when idle)
- **Expiry:** Messages older than 12h get auto-archived
- **Cross-agent visibility:** Agents should see each other's status (read-only), not just overseer's messages

---

## Session Handoff Protocol

### What worked
- SESSION-HANDOFF.md with current state, what was done, what's next

### What to improve
- **Mandatory fields:** Score, approach, blockers, next 3 actions
- **Max 20 lines.** Session handoffs were sometimes 100+ lines. The next session won't read all of it.
- **Include the "why":** Not just "changed alpha to 6" but "changed alpha to 6 because backtest showed +2.1 pts on simulated data (WARNING: simulated, not real)"
