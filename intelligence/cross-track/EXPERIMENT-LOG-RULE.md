---
priority: CRITICAL
from: overseer
timestamp: 2026-03-20 06:30 CET
permanent: true (do NOT delete)
---

## Rule: Every Agent Must Keep an EXPERIMENTS.md Log

Context resets will happen. New sessions won't know what you already tried. The ONLY way to prevent repeating work is a persistent log file.

### File: agent-{track}/EXPERIMENTS.md

Format:
```
# Experiments Log

## [YYYY-MM-DD HH:MM] Experiment Name
- **What:** One-line description
- **Result:** Score or outcome (numbers, not feelings)
- **Verdict:** KEEP / DISCARD / INCONCLUSIVE
- **Commit:** git hash

## [YYYY-MM-DD HH:MM] Next Experiment
...
```

### Rules
1. Log EVERY experiment, submission, model training, and approach tried
2. Log BEFORE starting work (what you plan to test)
3. Log AFTER finishing (what happened, with numbers)
4. Include the git commit hash so future sessions can find the code
5. Never delete entries. This is append-only.
6. Read EXPERIMENTS.md at the START of every session (add to startup protocol)

### For CV Agent Specifically
Log every submission with score:
```
## [2026-03-20 04:55] Submission: YOLO11m v2
- **What:** YOLO11m fine-tuned, ONNX, conf=0.15
- **Result:** 0.5735
- **Verdict:** Baseline established

## [2026-03-20 05:30] Submission: YOLO11m v3 TTA
- **What:** Added horizontal flip TTA, conf=0.05
- **Result:** 0.5756 (+0.002)
- **Verdict:** DISCARD. TTA barely helps. Detection is not the bottleneck.

## [2026-03-20 06:00] Submission: Ensemble v1 (YOLO11m + YOLO26m WBF)
- **What:** Two-model ensemble with Weighted Boxes Fusion
- **Result:** 0.5756 (+0.000 vs TTA)
- **Verdict:** DISCARD. More detection models don't help. Classification is the bottleneck.
```

This way Saturday's session reads EXPERIMENTS.md and immediately knows: don't bother with TTA, don't bother with detection ensembles, focus on classification.
