# CV Session Handoff — 2026-03-20 22:15 CET

## Current Best: 0.5756 (baseline YOLO-only, submission #2)

## What Was Proven This Session
- SAHI loses on all tests (-0.039 vs baseline)
- DINOv2 one-shot kNN loses (-0.039 vs baseline)
- Baseline YOLO-only at conf=0.15 is strongest on training data
- All audits ran on GCP with cv_judge.py

## Gemini Generation Running on GCP
cv-train-1 is generating Gemini product photos for all 321 remaining categories.
Check: `gcloud compute ssh cv-train-1 --zone=europe-west1-c --project=ai-nm26osl-1779 --command="tail -5 ~/synthetic_all/generation.log"`
When done: download gallery, rebuild with multiple embeddings per class (not averaged), re-test DINOv2.

## GCP VMs
- cv-train-1: europe-west1-c, RUNNING (Gemini generation + has all weights/data)
- cv-train-2: DELETED

## Key Files
- `agent-cv/submission_sahi.zip` — YOLO+SAHI (don't submit, loses)
- `agent-cv/submission.zip` — DINOv2 pipeline (don't submit, loses)
- Baseline ZIP: `nmiai-2026-main/agent-cv/submissions/submission_yolo11m_v2.zip` (current best)
- All audit results on GCP at `~/audit/`

## Next Steps
1. Check if Gemini generation finished, download results
2. Build multi-sample gallery (many embeddings per class, not one averaged)
3. Re-audit DINOv2 with richer gallery against baseline
4. Try conf threshold sweep (0.10, 0.12, 0.15, 0.20) on baseline
