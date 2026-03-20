# NM i AI 2026 — Status Board

**Timestamp:** 2026-03-19 20:25 CET
**Competition Clock:** T+2h 25m (66h 35m remaining)
**Model:** Claude Opus 4.6 (confirmed)
**Phase:** RESEARCH COMPLETE → Ready for PLAN

---

## 3 Tasks — Scoring is 33.33% each

## Track Overview

| Track | Sponsor | Status | Approach | Priority |
|-------|---------|--------|----------|----------|
| **NLP** | Tripletex | RESEARCH ✅ | LLM Router + Tripletex API, 30 task types, 7 languages | HIGH |
| **ML** | Astar Island | RESEARCH ✅ | ConvLSTM + active learning, 50 queries budget | HIGH |
| **CV** | NorgesGruppen | RESEARCH ✅ | YOLOv8m fine-tune on 248 images, 356 categories | HIGH |

---

## Per-Track Summary

### NLP — Tripletex (33.33%)
- HTTPS endpoint needed (Cloud Run or ngrok)
- 30 task types × 56 variants (7 languages × 8 datasets)
- Gemini for parsing + Tripletex API for execution
- Score range: 0.0-6.0 per task
- **Baseline target:** Top 5 tasks in English + Norwegian (1-2h)

### ML — Astar Island (33.33%)
- Black-box simulator, 40×40 grid, 6 terrain classes
- Only 50 queries across 5 seeds — query strategy is everything
- Entropy-weighted KL divergence scoring
- **Baseline target:** Uniform prior + observed pass-through (1-2h)

### CV — NorgesGruppen (33.33%)
- Offline inference on L4 GPU in Docker (no network)
- 248 training images, 356 categories — few-shot problem
- YOLOv8 fine-tuning, model weights must be in ZIP
- **Baseline target:** YOLOv8n quick train + run.py (1h)

---

## Decisions Needed (JC)

1. **Which track first?** — Astar Island recommended (round-based, time-sensitive)
2. **Resource allocation** — suggested: equal 33/33/33 until baselines done

---

## Research Quality
All 4 research files redone on **Claude Opus 4.6** at T+2.5h.
- CV: RESEARCH-CV.md ✅ (Opus)
- ML: RESEARCH-ML.md ✅ (Opus)
- NLP: RESEARCH-NLP.md ✅ (Opus)
- GAME: RESEARCH-GAME.md ✅ (Opus, NEW)

---

## Infrastructure
- **GCP:** Verified (ai-nm26osl-1779). Vertex AI + L4 ready.
- **Python venvs:** Ready for CV, ML, NLP
- **Game:** Needs websockets + pathfinding packages

---

## Blockers
- [ ] Account suspension (appeal in progress)
- [x] DevDrive synced — Gunnar has write access

---

*All research done on Opus 4.6. Ready for Phase 3 PLAN.*
