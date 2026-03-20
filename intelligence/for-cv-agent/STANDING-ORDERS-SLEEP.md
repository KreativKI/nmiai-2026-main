---
priority: HIGH
from: overseer
timestamp: 2026-03-20 04:15 CET
self-destruct: delete when JC wakes up and confirms new orders
---

## Standing Orders: JC Is Sleeping (~7 hours)

YOLO11m submission FAILED (exit code 2). This is your top priority.

### Immediate Actions
1. **Debug the exit code 2.** Unzip the submission, run it in your Docker sandbox, find the error.
2. **Fix and revalidate.** Common causes: ONNX model not at ZIP root, version mismatch, missing file.
3. **Prepare a fixed ZIP** but do NOT upload (JC must do that manually).
4. **Continue YOLO26m training** on cv-train-1. When done, export to ONNX, Docker-validate, prepare second ZIP.
5. **Start RF-DETR on cv-train-2** if not done: `gcloud compute instances create cv-train-2 --zone=europe-west2-a --machine-type=g2-standard-8 --accelerator=type=nvidia-l4,count=1 --image-family=pytorch-latest-gpu --image-project=deeplearning-platform-release --boot-disk-size=100GB --maintenance-policy=TERMINATE --project=ai-nm26osl-1779`
6. **Commit to agent-cv branch** after every task.

### Communication Schedule (staggered)
- Check intelligence/for-cv-agent/ at :10 and :40 past each hour
- Write status to intelligence/for-overseer/ at :15 and :45 past each hour
- Write summary to intelligence/for-overseer/cv-sleep-report.md when done or context fills up

### When JC Wakes Up
Have ready: fixed YOLO11m ZIP + YOLO26m ZIP (if training done) + comparison of both models. JC will upload the best one.
