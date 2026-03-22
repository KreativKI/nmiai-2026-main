# NM i AI 2027 Playbook
## Based on Everything We Learned in 2026

---

## Pre-Competition (1 Week Before)

### Day -7: Infrastructure
- [ ] Set up repo with worktree-per-agent pattern
- [ ] Populate ALL agent CLAUDE.md files with correct deadlines, rate limits, rules
- [ ] Populate ALL rules.md files (never leave empty)
- [ ] Test Boris workflow: run `/boris` on a dummy task, verify sequential execution
- [ ] Verify all subagent names work (`feature-dev:code-reviewer`, `code-simplifier:code-simplifier`, `build-validator`)
- [ ] Create Python-specific build-validator if Python track exists

### Day -3: Research
- [ ] Research what shipped in last 6 months for each track's domain
- [ ] For CV: check latest detection models (YOLO versions, DINOv2, GroundingDINO, SAM2)
- [ ] For NLP: check latest agent frameworks, function-calling patterns
- [ ] For ML: check latest prediction/optimization techniques
- [ ] Document findings in `intelligence/cross-track/RESEARCH.md`

### Day -1: Dry Run
- [ ] Run full submission pipeline for each track (dummy data)
- [ ] Verify rate limits against ACTUAL platform (not docs)
- [ ] Verify API credentials and endpoints
- [ ] Test GCP VM creation and SSH connectivity
- [ ] Run health-check.sh and fix any issues
- [ ] Verify intelligence folder hooks work (check_inbox_v2.sh)

---

## Competition Hour 0-6: Foundation

### Priority: Submit baseline, then improve
1. Submit simplest possible baseline for ALL 3 tracks within first 2 hours
2. Get a score on the board, any score
3. Then iterate from a working foundation

### Anti-patterns to avoid
- Don't spend 6 hours setting up infrastructure before submitting
- Don't default to familiar tools without exploring
- Don't start coding before reading task docs thoroughly

### Overseer duties
- Refresh plan.md every 4 hours (set a /loop reminder)
- Monitor all 3 tracks for first submission
- Verify rate limits match platform (not docs)

---

## Competition Hour 6-24: Explore and Iterate

### Priority: Find the right approach
1. Each agent explores 3 alternative approaches (MANDATORY gate)
2. Benchmark alternatives against baseline
3. Pick best approach, commit to it
4. Submit improved version

### Key rules
- **Explore before building:** No agent starts coding until they've filed an exploration report
- **Verify against real data:** Never optimize on simulated/synthetic data when real data exists
- **Throttle submissions:** Max 50% of daily budget per session. Analyze between batches.

### Overseer duties
- QC exploration reports (did agents actually explore, or just pick the familiar option?)
- Cross-pollinate findings between tracks
- Monitor scores and adjust priorities

---

## Competition Hour 24-48: Optimize

### Priority: Squeeze performance from chosen approach
1. Grid search key hyperparameters
2. A/B test improvements (use ab_compare.py)
3. Submit only when improvement is verified on eval
4. Study leaderboard leaders (what are top teams doing differently?)

### Key rules
- **Direction check:** Before deploying any optimization, verify the DIRECTION makes sense. "Lower alpha" might look better on clean data but worse on noisy production data.
- **Use all compute:** Don't leave GCP VMs idle. If local is busy, run experiments on cloud.
- **Boris on every change:** No shortcuts. Review, Simplify, Validate, Commit.

---

## Competition Hour 48-65: Polish

### Priority: Reliability over novelty
1. Stop adding features
2. Fix remaining bugs
3. Ensure all submissions are using best config
4. Run regression tests

### Key rules
- **No new architectures after hour 48.** Refine what works.
- **Submission budget awareness:** Track remaining submissions carefully
- **Pre-submission validation:** Every upload goes through cv_pipeline.sh or equivalent

---

## Competition Hour 65-69: Endgame

### Timeline
| Time | Action |
|------|--------|
| -4h (11:00) | Feature freeze. No new code. |
| -3h (12:00) | Final submissions queued |
| -1h (14:00) | Select best submission for private leaderboard |
| -15min (14:45) | Final commits on all branches |
| 15:00 | Submissions lock |
| 15:00-15:15 | Make repo public, submit URL |

### Anti-patterns
- DON'T deploy untested changes in the last hour
- DON'T commit after 15:00 (learned the hard way)
- DON'T forget to select your submission for private leaderboard
- DON'T forget Vipps verification (do this on day 1)

---

## Automation to Build Before Competition

### A. Score anomaly detector
Alert if any submission scores >10% worse than previous best. Pause auto-submissions.

### B. Rate limit tracker
Visual budget meter: "145/180 used. 35 remaining. Pace: runs out at 14:30."

### C. Agent heartbeat monitor
Alert if agent hasn't committed in >3 hours.

### D. Session handoff enforcer
Block /clear until SESSION-HANDOFF.md is updated.

### E. Pre-submission gate
Mandatory validation pipeline. No bypass.

---

## Agent CLAUDE.md Template (2027)

```markdown
# NM i AI 2027 -- {TRACK} Agent

## Identity
You are the {TRACK} agent. You own this track completely.

## Competition Clock
Deadline: [EXACT DATE TIME CET]. Always calculate, never estimate.

## Boris Workflow (mandatory, every change)
1. EXPLORE: launch feature-dev:code-explorer (fresh context)
2. PLAN: JC approves before proceeding
3. CODE: implement approved plan
4. REVIEW: launch feature-dev:code-reviewer (fresh context)
5. SIMPLIFY: launch code-simplifier:code-simplifier (fresh context)
6. VALIDATE: launch build-validator (fresh context)
7. COMMIT: only after validation passes

NEVER run steps 4-5-6 in parallel. Sequential, one at a time.

## Hard Gates (require JC approval)
- Submitting to competition
- Changing model architecture
- Any action that burns rate-limited resources

## What You NEVER Do
- Skip Boris workflow for any change
- Trust subagent claims about API values without testing
- Estimate time instead of calculating
- Run Boris steps in parallel
- Auto-submit without throttling
- Start coding before filing an exploration report

## Session Startup
1. Read this CLAUDE.md
2. Read rules.md
3. Read plan.md
4. Check intelligence/for-{TRACK}-agent/ for new orders
5. Read MEMORY.md (last 20 entries)
6. State: "Track: {TRACK}. Score: {X}. Approach: {Y}. Next: {Z}."

## Session End
1. Update SESSION-HANDOFF.md (max 20 lines)
2. Update MEMORY.md
3. Commit with score delta in message
```

---

## Key Numbers to Verify Pre-Competition

| Item | Where to check | Why |
|------|----------------|-----|
| Rate limits per track | Platform API, not docs | Docs said 300, platform enforced 180 |
| Submission limit per day | Platform UI | Changed during 2026 (3 to 5 to 10 to 6) |
| Scoring formula | Task docs + empirical testing | ML formula had 3x multiplier we missed |
| Blocked imports | Task docs | CV: os, sys, subprocess, socket, etc. |
| Timeout per submission | Task docs | CV: 300s, NLP: 300s |
| GPU specs in sandbox | Task docs | CV: L4 24GB, affects model size decisions |

---

## The 5 Most Expensive Mistakes of 2026

| Rank | Mistake | Cost | Prevention |
|------|---------|------|------------|
| 1 | ML alpha search on wrong data source | ~20 pts on final round | Always optimize on production-like data |
| 2 | CV stuck on YOLO-only for 2 days | ~48h of potential improvement | Explore alternatives on day 1 |
| 3 | NLP trusted subagent API values | Broke admin employee creation | Verify against real API always |
| 4 | Boris running in parallel | Quality gates defeated | /boris command with sequential enforcement |
| 5 | Commits after 15:00 deadline | Potential disqualification risk | Set alarm at 14:45, commit then |
