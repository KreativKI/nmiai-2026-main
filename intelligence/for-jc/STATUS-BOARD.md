# NM i AI 2026 — Status Board

**Timestamp:** 2026-03-20 08:05 CET
**Competition Clock:** T+14h 05m (56h 55m remaining)
**Model:** Gemini 3 Flash (Gunnar Overseer)
**Phase:** BUILD PHASE

---

## 3 Tasks — Scoring is 33.33% each

## Track Overview

| Track | Sponsor | Status | Approach | Local Score | Submissions |
|-------|---------|--------|----------|-------------|-------------|
| **CV** | NorgesGruppen | ACTIVE | YOLO11m v2 (submitted 04:56) | 0.945 | 2 (1 fail, 1 pend) |
| **ML** | Astar Island | **STALLED** | Bayesian Transition Matrix | — | Unknown (drift) |
| **NLP** | Tripletex | DEPLOYED | Gemini 2.5 Flash + Cloud Run | — | 0 (ready) |

---

## Per-Track Summary

### CV — NorgesGruppen (33.33%)
- **Status:** YOLO11m v2 (64.8 MB) score pending. Local mAP50 = 0.945.
- **Training:** YOLO26m done (mAP50=0.914, lower than 11m). Ensemble ZIP ready: `submissions/submission_ensemble_v1.zip` (131MB). RF-DETR at epoch 39 (mAP50=0.572).
- **Priority:** Check v2 score. If mAP50 is high, save ensemble submission slots for later.
- **Action:** Delete VMs (cv-train-1, cv-train-2) when YOLO26m/RF-DETR training is confirmed finished or discarded.

### ML — Astar Island (33.33%)
- **Status:** **CRITICAL DRIFT.** `status.json` and `MEMORY.md` not updated since T+0 (2026-03-16).
- **Risk:** Missing rounds = 0 points. Rounds happen every ~3h.
- **Priority:** Wake up agent. Run `astar_baseline.py` and submit for next round immediately.
- **Note:** No evidence of any successful submissions.

### NLP — Tripletex (33.33%)
- **Status:** `tripletex_bot_v1` deployed to Cloud Run.
- **Endpoint:** `https://tripletex-agent-795548831221.europe-west4.run.app`
- **Priority:** Waiting for JC to submit URL on platform. Start Tier 2 roadmap (Friday tasks).
- **Note:** Code-reviewer (Boris) fixed critical field naming bugs (02:00 CET). Ready to roll.

---

## Decisions for JC (when awake)
1. **CV:** Check v2 score on platform (submitted at 04:56).
2. **ML:** Verify if any round submissions have been made. If not, trigger baseline now.
3. **NLP:** Submit Cloud Run URL to platform: `https://app.ainm.no/submit/tripletex`.

---

## Infrastructure
- **GCP:** 2x L4 VMs active (cv-train-1, cv-train-2). Cleanup needed.
- **Cloud Run:** Active (tripletex-agent).
- **Workspace:** DevDrive synced and primary.

---

*Gunnar is monitoring hourly rounds. JC is sleeping.*
