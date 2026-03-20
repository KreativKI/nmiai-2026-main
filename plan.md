# Overseer Plan — NM i AI 2026
**Last updated:** 2026-03-20 03:30 CET

## Active Tasks (right now)

### 1. NLP Sandbox Prerequisites (URGENT)
- **Status:** Intelligence message sent, paste prompt into NLP terminal
- **Issue:** Fresh competition sandbox has NO bank account. Invoice tasks fail with 422.
- **Root cause:** Bot doesn't set up prerequisites before executing tasks
- **Fix:** Add "sandbox setup" step: register bank account, ensure department exists, etc.
- **Also:** Bot returns "completed" even on failure, masking the error
- **Next:** Verify fix deployed, resubmit invoice task, check score improves

### 2. CV Parallel Training
- **Status:** Intelligence message sent to spin up 3 VMs
- cv-train-1: YOLO11m running (epoch 58, mAP50 0.895)
- cv-train-2: YOLO26m (needs to be created)
- cv-train-3: RF-DETR (needs to be created)
- **Next:** Monitor training progress, compare models when done

### 3. ML Round 3 Score
- **Status:** Submitted (resubmitted with 13 extra queries). Round closes ~03:53 CET
- **Next:** Check score after round closes, learn from analysis endpoint

### 4. Butler Agent Setup
- **Status:** CLAUDE.md written and improved with cowork process
- **Next:** JC launches butler, it builds Playwright submission bots first, then dashboard

## Queued Tasks

### 5. Cowork-Enhance All Agent CLAUDE.md Files
- Apply same quality improvement process used on butler to CV, ML, NLP agent CLAUDE.md files
- Add session startup protocols, ranked responsibilities, resource tables

### 6. NLP Agent CLAUDE.md Field Name Fix
- The agent-nlp CLAUDE.md had wrong field names in the request example
- Fix to match actual endpoint spec from tripletex-endpoint.md

### 7. Commit and Push
- After NLP fix confirmed, do another commit on main
- Sync worktrees

### 8. Sleep Handoff
- When JC goes to sleep: ensure all agents are autonomous
- Verify monitoring loop is running
- Write SESSION-HANDOFF.md if context is getting full

## Key Deadlines
| Time | What |
|------|------|
| ~03:53 CET | Round 3 closes, first ML score |
| ~07:00 CET | Round 4 or 5 expected (JC sleeping) |
| Friday morning | Tier 2 tasks unlock for NLP |
| Saturday morning | Tier 3 tasks unlock for NLP |
| Sunday 09:00 | FEATURE FREEZE |
| Sunday 14:45 | Repo goes public |
| Sunday 15:00 | COMPETITION ENDS |
