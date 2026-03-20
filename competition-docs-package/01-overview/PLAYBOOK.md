# NM i AI 2026 -- Competition Playbook

**Competition:** March 19 (Thursday 18:00 CET) through March 22 (Sunday 18:00 CET)
**Format:** 3 simultaneous tracks (CV, ML, NLP). Score = average of all 3.
**Prize:** 1M NOK pool
**Key rule:** Zero on any track is catastrophic. All 3 must have submissions.

---

## Pre-Flight (Thursday before 16:00, JC does this)

```
[ ] Convex + OrbStack running and verified
[ ] Dashboard accessible at localhost:6791
[ ] 3 terminal windows pre-configured (one per agent)
[ ] Matilda running on Mac mini
[ ] GCP Vertex L4 access verified
[ ] Git repo initialized with SSH remote
[ ] Python venvs exist (verify: ls agent-cv/.venv/bin/python; if missing run setup-venvs.sh)
[ ] Pip packages verified (run: agent-cv/.venv/bin/python -c "import torch, sklearn, xgboost; print('OK')")
[ ] Model cache populated (shared/models/)
[ ] Claude remote connection tested (can send from phone)
[ ] Each agent terminal has Claude Code session started
```

JC leaves for launch event at 16:00. Systems running, ready to receive specs.

---

## Phase 1: RECON (18:00-19:00) -- AUTONOMOUS

JC is remote. Agents proceed without JC approval.

### Spec Delivery (18:00-18:10)
- JC reads specs on phone, sends raw text to agent folders via remote connection
- Backup: Matilda checks competition page, distributes specs

### Per-Track Agent Checklist
```
[ ] Read full spec (save verbatim to spec-raw.md)
[ ] Write rules.md with ALL mandatory fields (use templates/RULES-TEMPLATE.md)
[ ] Write initial-assessment.md: problem type, difficulty, pre-trained model availability
[ ] Technical spike: connect to API, get first data sample, submit dummy response
[ ] Determine: deterministic? real-time? batch? feedback loop type?
[ ] Map scoring function: exact formula, what gives most points per unit effort
[ ] Update status.json: state="recon_complete"
```

### Matilda Checklist
```
[ ] Read all 3 specs simultaneously
[ ] Write intelligence/cross-track/SPEC-DIGEST.md
[ ] Classify each track: standard / needs-research / novel
[ ] Identify shared infrastructure needs
[ ] Write PRIORITY-RECOMMENDATION.md (JC reviews at 19:30)
[ ] Flag trivially solvable (quick-win) or impossible (cut-loss) tracks
[ ] Default allocation: equal 33/33/33 until JC arrives
```

**RECON GATE:** No agent proceeds until rules.md has all mandatory fields. Unknown = blocker.
Matilda makes the call on ambiguous fields (documents assumption, JC reviews at 19:30).

---

## Phase 2: RESEARCH (18:45-19:45, overlaps late recon) -- AUTONOMOUS

### Per-Track Agent Checklist
```
[ ] Read Matilda's RESEARCH briefing from intelligence/for-{track}-agent/
[ ] GitHub search: "{problem description} solution", "{metric} baseline"
[ ] Kaggle search: similar competition kernels
[ ] HuggingFace search: pre-trained models for this domain
[ ] Papers With Code: SOTA on this task type
[ ] Check NM i AI 2025 solutions (Race Car, Tumor Segmentation, Healthcare RAG)
[ ] For each resource: score match %, adaptation effort, license
[ ] DECISION: FORK (>70% match) or BUILD (no good match)
[ ] Update status.json: state="research_complete", approach="fork:{url}" or "build"
```

### Matilda Research Checklist
```
[ ] Search 5 sources per track (GitHub, Kaggle, HF, PapersWithCode, NM i AI 2025)
[ ] Write RESEARCH-{track}.md to each agent's intelligence folder
[ ] Flag "champion code" (ready-to-fork solutions)
[ ] Cross-reference: do any tracks share models/libraries?
```

---

## Phase 3: PLAN (19:30-20:30) -- JC ARRIVES

### JC Arrival Protocol (19:30, 15 min)
```
[ ] Read intelligence/for-jc/STATUS-BOARD.md (3-minute overview)
[ ] Read all 3 rules.md (verify no wrong assumptions)
[ ] Read intelligence/cross-track/PRIORITY-RECOMMENDATION.md
[ ] Correct any wrong assumptions in rules.md
```

### Per-Track Agent Checklist
```
[ ] RE-READ rules.md (mandatory before planning)
[ ] Read research findings
[ ] Write plan.md with:
    - Approach A (primary): description, expected score, time estimate
    - Approach B (fallback): different algorithm/strategy
    - Approach C (simple baseline): dumbest thing that works
    - Ceiling analysis: what separates good from #1?
    - Validation strategy: train/val split, CV folds, local scoring
    - Test loop: exact command to test
    - Submission loop: exact command to submit
    - Dependencies: pip packages, models, data downloads
[ ] Implement Approach C FIRST (valid submission within 30 min)
[ ] Update status.json: state="planning_complete", baseline_score=X
```

### JC Decision Point (20:15)
```
[ ] Review all 3 plan.md files
[ ] Allocate priority: highest score-per-hour potential?
[ ] Decide GPU allocation (which track gets Vertex L4?)
[ ] Confirm all 3 tracks have a submittable baseline
```

---

## Phase 4: BUILD (20:30 Thursday through Sunday 18:00)

### Per-Agent Build Loop (Boris workflow, every change)
```
EXPLORE: What is the current bottleneck? (read MEMORY.md, check scores)
PLAN:    What change addresses this? (2-3 sentences in MEMORY.md)
CODE:    Implement the change
REVIEW:  code-reviewer validates (bugs, security, logic)
SIMPLIFY: code-simplifier cleans up
VALIDATE: build-validator + run test suite, check score delta
COMMIT:  If improved, commit with score delta in message
```

### Build Discipline
```
- RE-READ rules.md every 4 hours (non-negotiable)
- RE-READ rules.md BEFORE: changing approach, changing output format,
  adding features, investigating regressions, final submission
- Log EVERY experiment in MEMORY.md (success AND failure)
- Check intelligence/ folder at start of every build cycle
- Update status.json every 30 minutes
```

---

## Rules Re-Reading Schedule

| Time | Event |
|------|-------|
| T+0h (18:00 Thu) | RECON (initial read) |
| T+2h (20:00 Thu) | After first build cycle |
| T+4h (22:00 Thu) | Before sleep |
| T+12h (06:00 Fri) | Morning start |
| T+18h (12:00 Fri) | Friday midday |
| T+30h (00:00 Sat) | Saturday start |
| T+42h (12:00 Sat) | Saturday midday |
| T+54h (00:00 Sun) | Sunday start |
| T+66h (12:00 Sun) | Final sprint |

---

## Resource Allocation

### Hardware
| Machine | Primary | Secondary |
|---------|---------|-----------|
| MacBook Pro M3 Pro 36GB | ML Agent (compute-heavy) | NLP Agent (if API-based) |
| Mac mini M4 16GB | CV Agent | Matilda orchestrator |
| GCP Vertex L4 ($32 budget) | Whichever track needs GPU | Reserve, allocate by Friday morning |

### Time Allocation
- First 12 hours: Equal 33/33/33 (need baselines on all 3)
- After baselines: 40% highest-ceiling / 35% middle / 25% lowest
- Revisit every 12 hours

### Pivot Triggers
| Signal | Action |
|--------|--------|
| No baseline after 3 hours | JC investigates. Simplify or reallocate. |
| Within 5% of ceiling | Shift to other tracks (diminishing returns). |
| Stuck 4+ hours, no improvement | DECISION-NEEDED. Pivot approach or cut losses. |
| All 3 weak | Emergency: focus ONE track to top-20%. |

---

## Critical Deadlines

| Deadline | What |
|----------|------|
| **Saturday 12:00** | CUT-LOSS: Any track with no submission = submit baseline NOW |
| **Sunday 12:00** | FEATURE FREEZE: No new approaches. Bug fixes and tuning only. |
| **Sunday 16:00** | Submission verification. All 3 tracks submitted and confirmed. |
| **Sunday 17:00** | Final submission. |
| **Sunday 18:00** | COMPETITION ENDS |

---

## Contingency Plans

**A. API is REST/file-upload, not WebSocket:**
Phase 1 spike catches this in 30 min. Agent writes shared API client, all 3 import it.

**B. Track requires model we don't have cached:**
Check shared/models/ -> HuggingFace download -> fallback to smaller cached model -> classical ML.

**C. One track is trivial:**
Speed-run (<2h), mark "maintenance mode", reallocate agent to harder track.

**D. One track is near-impossible:**
Submit Approach C baseline. Spend max 2 more hours. If no progress: maintenance mode, compensate on other 2.

**E. Platform down:**
Continue local dev. Queue submissions.

**F. Context window fills up:**
Write SESSION-HANDOFF.md. New session reads: CLAUDE.md > rules.md > plan.md > MEMORY.md > SESSION-HANDOFF.md.

**G. Agent stuck in rabbit hole:**
Matilda monitors hours_since_improvement. After 4h with no improvement: auto-escalate to JC.

---

## Communication Quick Reference

```
intelligence/
  cross-track/          Matilda -> All agents
  for-cv-agent/         Matilda -> CV
  for-ml-agent/         Matilda -> ML
  for-nlp-agent/        Matilda -> NLP
  for-matilda/          Any agent -> Matilda
  for-jc/               Matilda -> JC
    STATUS-BOARD.md     (read this first)
    DECISION-NEEDED-*   (urgent)
```

Agents NEVER communicate directly. All flows through intelligence/.

---

## Session Handoff Protocol

When starting a new session (context rotation, new day):
1. Read CLAUDE.md (agent identity + workflow)
2. Read rules.md (competition rules, SINGLE SOURCE OF TRUTH)
3. Read plan.md (current approach)
4. Read MEMORY.md (experiment history)
5. Check intelligence/for-{track}-agent/ (new intel)
6. Read status.json (where you left off)
7. State: "Track: {X}. Score: {Y}. Approach: {Z}. Next step: {W}. Rules last read: now."

---

## Decision Framework (quick reference)

```
Public solution >70% match?  -> FORK (1-3h)
Pre-trained model available? -> ADAPT (2-4h)
Known problem type?          -> BUILD from template (3-6h)
Novel problem?               -> BUILD from scratch (6-12h), flag to Matilda
```

When in doubt, FORK first.

---

## Thursday Timeline

| Time | Activity | Who |
|------|----------|-----|
| 14:00-15:30 | Pre-flight checks | JC |
| 16:00 | JC leaves for event | JC |
| **18:00** | **SPECS DROP** | -- |
| 18:00-18:10 | Spec delivery (remote) | JC/Matilda |
| 18:10-19:00 | RECON (autonomous) | All agents |
| 19:00-19:15 | GATE: Matilda reviews rules.md | Matilda |
| 19:15-19:45 | RESEARCH (autonomous) | All + Matilda |
| **19:30** | **JC arrives at office** | JC |
| 19:30-19:45 | JC reads STATUS-BOARD, all rules.md | JC |
| 19:45-20:15 | PLAN + baselines | All agents + JC |
| 20:15-20:30 | GATE: All baselines submittable? | JC + Matilda |
| 20:30-00:00 | BUILD sprint 1 | All agents |

---

## File Map

```
nmiai_multiagent/
+-- PLAYBOOK.md               <- YOU ARE HERE
+-- setup.sh                  <- Folder structure setup
+-- setup-venvs.sh            <- Python venv creation
+-- .gitignore
+-- agent-cv/                  <- CV track workspace
|   +-- CLAUDE.md, rules.md, plan.md, MEMORY.md, status.json
|   +-- solutions/, data/, models/, tests/
+-- agent-ml/                  <- ML track workspace
|   +-- (same structure)
+-- agent-nlp/                 <- NLP track workspace
|   +-- (same structure)
+-- intelligence/              <- Cross-agent communication
|   +-- cross-track/, for-cv-agent/, for-ml-agent/,
|   +-- for-nlp-agent/, for-matilda/, for-jc/
+-- shared/
|   +-- templates/             <- 5 baseline templates
|   +-- models/                <- Pre-cached model weights
|   +-- api/                   <- Shared API client (created day-of)
+-- templates/                 <- Doc templates (CLAUDE, RULES, etc.)
+-- submissions/               <- Final submission archive
```
