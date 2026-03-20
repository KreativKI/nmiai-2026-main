# NM i AI 2026 — Status Board

**Timestamp:** 2026-03-20 05:15 CET
**Competition Clock:** T+11h 15m (60h 45m remaining)
**Model:** Gemini 3 Flash (Gunnar Overseer)
**Phase:** BUILD PHASE

---

## 3 Tasks — Scoring is 33.33% each

## Track Overview

| Track | Sponsor | Status | Approach | Local Score | Submissions |
|-------|---------|--------|----------|-------------|-------------|
| **CV** | NorgesGruppen | ACTIVE | YOLO11m v2 (submitted 04:56) | 0.945 | 2 (1 fail, 1 pend) |
| **ML** | Astar Island | ACTIVE | Bayesian Transition Matrix | — | Round-based |
| **NLP** | Tripletex | DEPLOYED | Gemini 2.5 Flash + Cloud Run | — | 0 (ready) |

---

## Per-Track Summary

### CV — NorgesGruppen (33.33%)
- **Status:** v2 submission (64.8 MB) pending. Fixes `exit code 2` (argparse).
- **Training:** YOLO26m (epoch 73) and RF-DETR (epoch 24) on GCP L4s.
- **Priority:** Monitor v2 score. Export YOLO26m to ONNX if it beats YOLO11m.
- **Blocker:** None currently.

### ML — Astar Island (33.33%)
- **Status:** `astar_v3.py` exists. Round-based prediction ongoing.
- **Approach:** Bayesian transition matrix from cross-seed observations.
- **Priority:** Ensure 5/5 seeds submitted for current round. Refine transition model.
- **Note:** `status.json` and `MEMORY.md` need updating (drift detected).

### NLP — Tripletex (33.33%)
- **Status:** `tripletex_bot_v1` deployed to Cloud Run.
- **Endpoint:** `https://tripletex-agent-795548831221.europe-west4.run.app`
- **Priority:** Ready for JC to submit URL. Monitoring logs for platform triggers.
- **Note:** Fixed critical field naming bug (T+8h).

---

## Decisions for JC (when awake)
1. **CV:** Verify v2 score on leaderboard.
2. **ML:** Review transition matrix quality vs simple prior.
3. **NLP:** Submit Cloud Run URL to platform.

---

## Infrastructure
- **GCP:** 2x L4 VMs running (cv-train-1, cv-train-2).
- **Cloud Run:** Active (tripletex-agent).
- **Workspace:** DevDrive synced and primary.

---

*Gunnar is monitoring hourly rounds. JC is sleeping.*
