# CV Session Handoff — 2026-03-21 07:30 CET

## Leaderboard: 0.6584 | 4 submissions left today | 31 hours to deadline

## New Strategy: Realistic Shelf Generation
Low-quality synthetic data barely helped (+0.011). New plan: use Gemini to generate 116 weak products ON REALISTIC SHELVES, then retrain. See plan.md for full details.

## Next Session: Execute Phase 1
1. Read plan.md (the strategy)
2. Write Gemini shelf generation script (10 variations per weak category)
3. Split 116 categories across 3 GCP VMs (cv-train-1, cv-train-3, cv-train-4)
4. Run generation (~2h)
5. Merge data, retrain, evaluate, submit

## GCP VMs (all IDLE)
- cv-train-1: europe-west1-c (has all data, models, Gemini ADC)
- cv-train-3: europe-west1-b
- cv-train-4: europe-west3-a

## Validated ZIPs on Hand
- `submission_maxdata.zip` -- leaderboard 0.6584 (current best)
- `submission_yolo11l.zip` -- val 0.780, untested
- `submission_aggressive_v2_final.zip` -- leaderboard 0.6475
