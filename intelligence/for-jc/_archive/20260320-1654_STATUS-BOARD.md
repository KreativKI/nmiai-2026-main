# NM i AI 2026 — Status Board

**Timestamp:** 2026-03-20 13:05 CET
**Competition Clock:** T+19h 05m (51h 55m remaining)
**Model:** Gemini 3 Flash (Gunnar Overseer)
**Phase:** TIER 2 OPEN (NLP/ML) | BUILD PHASE (CV)

---

## 3 Tasks — Scoring is 33.33% each

## Track Overview

| Track | Sponsor | Status | Approach | Local Score | Platform Score | Submissions |
|-------|---------|--------|----------|-------------|----------------|-------------|
| **CV** | NorgesGruppen | ACTIVE | YOLO11m v2 (scored) | 0.945 | **0.5735** | 2/10 today |
| **ML** | Astar Island | **STALLED** | Bayesian Transition Matrix | — | 0.00 | 0 (Missed R1-R4) |
| **NLP** | Tripletex | DEPLOYED | Gemini 2.5 Flash + Cloud Run | — | — | 0 (Waiting URL) |

---

## Per-Track Summary

### CV — NorgesGruppen (33.33%)
- **Status:** YOLO11m v2 scored **0.5735**. Significant gap from local mAP50 (0.945) suggests hard test set or classification issues.
- **Next Up:** `submission_yolo11m_v3_tta.zip` ready (06:33 CET). TTA (Test Time Augmentation) should help.
- **Parallel:** RF-DETR training on `cv-train-2` (epoch 39, mAP50=0.572). 
- **Priority:** Submit v3_tta. Start classification-only refinement (CLIP/SigLIP) to boost the 30% classification component.

### ML — Astar Island (33.33%)
- **Status:** **CRITICAL.** Missed Round 4 (12:20 CET). No evidence of submissions. 
- **Risk:** We are bleeding points every 3 hours. Round 5 closes ~15:25 CET.
- **Priority:** **EMERGENCY WAKEUP.** Agent must run `astar_baseline.py` NOW. Even a bad prediction is better than 0.
- **Action:** If agent doesn't respond, Overseer will request JC to manual-trigger the baseline.

### NLP — Tripletex (33.33%)
- **Status:** Tier 2 (Friday multiplier x2) is OPEN. `tripletex_bot_v1` is deployed and tested.
- **Endpoint:** `https://tripletex-agent-795548831221.europe-west4.run.app/solve`
- **Priority:** JC must submit URL on platform. Agent should begin Tier 2 task expansion (Multi-step workflows, Invoicing, etc.).
- **Note:** Boris fixed critical field naming bugs. Readiness is 100%.

---

## Decisions for JC
1. **CV:** Submit `submission_yolo11m_v3_tta.zip` (ready in `agent-cv/submissions/`).
2. **ML:** Verify why Astar Island submissions are not firing. Trigger `astar_baseline.py` manually if needed.
3. **NLP:** Submit Cloud Run URL to platform: `https://app.ainm.no/submit/tripletex`.

---

## Infrastructure
- **GCP:** `cv-train-1` (YOLO11m) and `cv-train-2` (RF-DETR) active.
- **Cloud Run:** `tripletex-agent` active.
- **Workspace:** All tracks synced.

---

*Gunnar is escalating the ML stall. JC is awake.*
