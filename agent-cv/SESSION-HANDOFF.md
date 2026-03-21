# CV Session Handoff — 2026-03-21 02:45 CET

## Leaderboard: 0.6475 (up from 0.5756, +0.072)

## Validated ZIPs Ready for JC
A. `submission_aggressive_v2_final.zip` -- YOLO11m, val 0.767, leaderboard 0.6475 (CONFIRMED)
B. `submission_yolo11l.zip` -- YOLO11l, val 0.780 (best val so far), pipeline+canary PASS

## GCP VMs Running
| VM | Zone | Model | Epoch | Best Val mAP50 | ETA |
|----|------|-------|-------|----------------|-----|
| cv-train-1 | europe-west1-c | YOLO11m maxdata (854 imgs, 200ep) | 57/200 | 0.770 | ~06:00 |
| cv-train-3 | europe-west1-b | YOLO11l | DONE | 0.780 | ZIP ready |
| cv-train-4 | europe-west3-a | YOLO26m (348 imgs, 120ep) | 25/120 | 0.132 (slow) | ~04:00 |

## Check Commands
```bash
# cv-train-1 (maxdata)
gcloud compute ssh cv-train-1 --zone=europe-west1-c --project=ai-nm26osl-1779 --command="grep -oP '\d+/200' ~/train_maxdata.log | tail -1; sort -t, -k8 -rn ~/retrain/yolo11m_maxdata_200ep/results.csv | head -1"

# cv-train-4 (yolo26)
gcloud compute ssh cv-train-4 --zone=europe-west3-a --project=ai-nm26osl-1779 --command="grep -oP '\d+/120' ~/train_yolo26m.log | tail -1; tail -1 ~/retrain/yolo26m_aggressive/results.csv"
```

## When Models Finish
For each model, run quick_submit.sh then canary agent.

## Key Insight
More data = less overfitting = higher leaderboard. Gap shrank from 0.38 to 0.12.

## 6 Saturday Submission Slots (after 01:00 CET reset)
Priority: YOLO11l (0.780 val) > maxdata when ready > YOLO26 if decent
