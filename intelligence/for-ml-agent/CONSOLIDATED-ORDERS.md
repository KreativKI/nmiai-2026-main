---
priority: CRITICAL
from: overseer
timestamp: 2026-03-20 16:30 CET
permanent: true
---

## Consolidated Orders: What Moves Your Score

Your score: 71.77. Competitor: 91.49. Gap: 20 points.
Delete all other standing orders. This is the only plan.

### Phase 1: Temperature Scaling (quick win)
After computing predictions, apply: `pred = pred ** (1/T)` then renormalize.
Backtest with T = 0.9, 1.0, 1.05, 1.08, 1.1, 1.2.
Competitor's best gain was T=1.08 (+0.199 on their scale).
Commit result.

### Phase 2: Spatial Smoothing
Gaussian-smooth the prediction grid (sigma=0.5, 1.0, 1.5).
Neighboring cells should have correlated distributions.
Backtest each sigma. Commit best.

### Phase 3: Collapse Thresholding
Set probabilities below threshold (0.016, 0.020, 0.025) to zero.
Redistribute mass to remaining classes. Renormalize.
Backtest. Commit best.

### Phase 4: Autoiteration Loop
```python
best_score = current_backtest_score
for variant in generate_variants(base_config, n=50):
    score = backtest(variant)
    log_experiment(variant, score)
    if score > best_score:
        best_score = score
        save_best(variant)
```
Generate variants by randomly perturbing: temperature, smoothing sigma, collapse threshold, observation weights, near weights.
Run between rounds. Commit after every improvement.

### Phase 5: Submit Best to Next Round
Apply best config from autoiteration to live round.
Never miss a round. Background poll every 2 min.
After round, fetch ground truth, retrain model, repeat.

### Communication
After each phase, write a 3-line status to:
`/Volumes/devdrive/github_dev/nmiai-2026-main/intelligence/for-overseer/ml-status.md`
Format: phase completed, score delta, next action.

### Rules
- Commit after every phase
- Log everything in EXPERIMENTS.md
- Never estimate time
- Run backtester before every submission
