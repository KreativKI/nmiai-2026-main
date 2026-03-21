## CV Status — Overnight Autonomous Report #1
**Timestamp:** 2026-03-21 02:15 CET

**LEADERBOARD: 0.6475** (was 0.5756, +0.072)

**Validated ZIPs ready for JC (pipeline + canary PASS):**
A. `submission_aggressive_v2_final.zip` -- YOLO11m, val 0.767, leaderboard 0.6475
B. `submission_yolo11l.zip` -- YOLO11l, val 0.780 (best so far), untested on leaderboard

**Parallel training runs:**
| VM | Model | Epoch | Val mAP50 | ETA |
|----|-------|-------|-----------|-----|
| cv-train-1 | YOLO11m maxdata (854 imgs, 200ep) | ~5/200 | - | ~06:00 |
| cv-train-3 | YOLO11l (348 imgs, 120ep) | DONE | 0.780 | ZIP ready |
| cv-train-4 | YOLO26m (348 imgs, 120ep) | 2/120 | - | ~04:00 |

**Key metrics:**
- YOLO11l surpassed YOLO11m (0.780 vs 0.767 val mAP50)
- 3 GCP VMs running in parallel on free compute
- 6 fresh submission slots available (reset at 01:00)

**Next check: ~04:00 CET**
