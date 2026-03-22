# How to Communicate with LLMs Better
## A Personal Guide for JC, Based on NM i AI 2026

---

## The Core Problem

You're a film director working with AI actors. You know what the final scene should look like, but the actors interpret your direction through their own lens. The gap between your intent and their interpretation is where points were lost.

---

## 1. Be Specific About What "Done" Looks Like

### What happened
You told agents to "run Boris workflow." They interpreted this as "use the boris-workflow subagent" (one bundled session). You meant "run 3 separate agents sequentially with fresh context."

### The fix
Instead of: "Run Boris on this."
Say: "Run code-reviewer agent first. Wait for results. Fix issues. Then run code-simplifier agent. Wait for results. Apply changes. Then run build-validator agent."

### Rule
**Describe the process, not just the goal.** LLMs will find the shortest path to what sounds like your goal, which may not be the path you intended.

---

## 2. Verify Claims, Don't Trust Reasoning

### What happened
NLP subagent said "use userType ADMINISTRATOR" for Tripletex API. The actual API only accepts NO_ACCESS, STANDARD, EXTENDED. This broke every admin employee creation until caught via sandbox testing.

ML agent said "lower alpha is better" based on simulated data. Real production needed the opposite.

### The fix
Instead of: "What's the correct API value for admin users?"
Say: "Test against the real API. Show me the response. What values does it actually accept?"

### Rule
**Trust data over reasoning.** LLMs are confident even when wrong. Always demand empirical verification, especially for specific values, API parameters, and enum options.

---

## 3. Front-Load Constraints, Don't Retrofit Them

### What happened
Boris workflow rules were vague at start ("run code-reviewer, code-simplifier, build-validator"). Agents interpreted freely. You had to correct course repeatedly on day 2-3.

Agent CLAUDE.md files had wrong deadlines, generic playbooks, empty rules.md files.

### The fix
Before any work starts:
- Write exact agent instructions (not "adapt later")
- Specify every constraint explicitly
- Test the instructions by asking: "Read this back to me. What would you do first?"

### Rule
**If it's not in the CLAUDE.md, it doesn't exist.** Verbal corrections in one session vanish in the next. Every rule must be written down in the agent's identity file.

---

## 4. Gate Decisions, Don't Let Agents Self-Approve

### What happened
ML agent auto-submitted predictions without JC approval. Butler tried to run NLP submissions. NLP burned 249/300 rate-limited submissions in one session.

### The fix
For any irreversible action (submissions, deployments, data deletion):
- Agent proposes action
- Agent shows what it plans to do
- JC approves or redirects
- Agent executes

### Rule
**Irreversible actions need explicit gates.** Write "DO NOT proceed without JC approval" in the CLAUDE.md for anything that costs resources, burns rate limits, or can't be undone.

---

## 5. Name Things Precisely

### What happened
"code-simplifier" vs "code-simplifier:code-simplifier" caused agent crashes. "Boris workflow" could mean the subagent OR the sequential process. "Autonomous" meant different things to different agents.

### The fix
Use the exact technical name every time:
- Not "the simplifier" -> `code-simplifier:code-simplifier`
- Not "Boris" -> "sequential REVIEW then SIMPLIFY then VALIDATE, each a separate Agent call"
- Not "autonomous" -> "submit every round within 75% query budget, no JC approval needed for that scope"

### Rule
**Ambiguity is the enemy.** If a term could mean two things, one agent will pick meaning A and another will pick meaning B.

---

## 6. Check Before Building

### What happened
CV agent defaulted to YOLO11m (familiar) instead of exploring DINOv2, GroundingDINO, or other newer approaches. The breakthrough came from studying competitors, not from internal iteration. Two days of mediocre results, then 3 hours of rapid improvement after looking at what worked.

### The fix
Before any agent starts coding, require them to answer:
1. What has shipped in the last 3-6 months that solves this?
2. What are the top 3 teams/solutions doing?
3. Why is my approach better than using [newer tool]?

### Rule
**Explore before you build.** This was already in your CLAUDE.md but agents ignored it under time pressure. Make it a hard gate: no code until the exploration report is filed.

---

## 7. Use Fresh Sessions as a Feature, Not a Bug

### What happened
Context rotations felt like lost momentum. Agents had to re-read CLAUDE.md, plan.md, MEMORY.md every time. But this is actually the Boris workflow's strength: each fresh session brings unbiased eyes.

### The fix
- SESSION-HANDOFF.md must be updated before every /clear
- Make the handoff document answer: "What was I doing? What did I learn? What's next?"
- Next session reads the handoff and can question previous decisions

### Rule
**Fresh context = fresh perspective.** The reviewer shouldn't know what the coder was thinking. The same applies to session rotations: the new session can spot mistakes the old session was blind to.

---

## 8. Don't Estimate, Calculate

### What happened
Overseer reported "45 min remaining" when actual was ~100 min. Time pressure decisions were made on wrong assumptions.

### The fix
```python
python3 -c "from datetime import datetime, timezone, timedelta; ..."
```
Always calculate. Never estimate. This applies to time, rate limits, submission budgets, and resource allocation.

### Rule
**Numbers must be computed, not estimated.** This is already in your CLAUDE.md but needs enforcement.

---

## 9. One Question, One Answer

### What happened
You asked multiple things at once and agents sometimes answered the easy question while ignoring the hard one. Or they gave 5 options when you needed a recommendation.

### The fix
Instead of: "Should we use DINOv2 or GroundingDINO, and also check if the gallery is working, and what about the confidence threshold?"
Say: "Test DINOv2 on our eval set. Report accuracy."
Then: "Now test GroundingDINO on the same set."
Then: "Which scored higher? Use that one."

### Rule
**Sequential questions get better answers than bundled ones.** Each question should have one clear answer before moving to the next.

---

## 10. Write the Anti-Pattern, Not Just the Pattern

### What happened
CLAUDE.md said "run Boris workflow." Agents interpreted this multiple ways. Only when you added "NEVER use boris-workflow subagent" and "NEVER run in parallel" did the behavior converge.

### The fix
For every rule, also write what NOT to do:
- "Run agents sequentially" + "NEVER run agents in parallel"
- "Submit every round" + "NEVER skip a round, even if the model isn't ready"
- "Check inbox on startup" + "NEVER start coding before reading inbox"

### Rule
**Negative constraints are clearer than positive instructions.** LLMs find creative ways to satisfy positive rules while violating the spirit. Negative rules close the loopholes.

---

## Summary: The Director's Cut

You're directing a film with AI actors. Here's your shot list:

| Shot | Direction |
|------|-----------|
| Before filming | Write the exact script (CLAUDE.md), not notes |
| Each scene | One instruction at a time, verify the take |
| Special effects | Verify against real footage, not CGI mockups |
| Dangerous stunts | Hard gate: director approves before action |
| Wrap each day | Written handoff for tomorrow's crew |
| Post-production | Fresh eyes on every review pass (separate sessions) |
| Final cut | Calculate runtime, don't estimate it |
