---
priority: MEDIUM
from: overseer
timestamp: 2026-03-20 12:00 CET
self-destruct: after adapting and committing, delete
---

## Adapt These Archive Tools

Source: `/Volumes/devdrive/github_dev/NM_I_AI_dash/tools/`
Destination: `shared/tools/`

### 1. ab_compare.py -> shared/tools/ab_compare.py
Adapt for comparing two CV submission ZIPs or ML prediction files.
Input: two paths (version A, version B) + test data.
Output: which version is better, by how much, with confidence.

### 2. batch.py -> shared/tools/batch_eval.py
Adapt for running cv_judge.py or ml_judge.py across multiple submissions.
Input: directory of ZIPs or prediction files.
Output: ranked table of all submissions with scores.

### 3. oracle_sim.py -> shared/tools/oracle_sim.py
Adapt for estimating theoretical max score per track.
CV: what's the max possible given our detection mAP?
ML: what's the max given our observation budget?
NLP: what's the max given task type coverage?

### 4. bot_profiler.py -> shared/tools/profiler.py
Adapt for profiling CV run.py inference time.
Must verify total stays under 300s on L4 GPU.
Critical for DINOv2 submission (two ONNX models now).

Boris workflow for each. Update TOOLS.md after each adaptation.
