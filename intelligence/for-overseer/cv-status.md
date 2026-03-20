## CV Status — Phase 0 Complete
**Timestamp:** 2026-03-21 ~00:30 CET

**What:** Created proper 80/20 train/val split (208/40). Verified category ID mapping: no off-by-one, IDs 0-355 match COCO annotations exactly. Ran honest eval on val (model still overfits because it was trained on all 248 images): det 0.84, cls 0.96, combined 0.88. These numbers are still inflated. True honest eval requires retraining with the split (Phase 3).

**Score delta:** No change yet. Leaderboard still 0.5756. Split enables honest future evaluation.

**Next:** Phase 1 — Copy-paste augmentation on GCP. Checking Gemini generation progress first.
