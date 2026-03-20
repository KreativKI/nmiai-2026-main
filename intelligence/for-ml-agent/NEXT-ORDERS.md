---
priority: CRITICAL
from: overseer
timestamp: 2026-03-20 19:28 CET
---

## Next Steps (post-equilibrium)

Good discipline abandoning equilibrium when data said no.

### 1. R8 still open (closes ~19:46 CET)
If you've improved anything since last R8 submission, resubmit now. Free to overwrite.

### 2. Fetch R7 ground truth
R7 is completed. Retrain learned model with new data. More ground truth = better transitions.

### 3. Execute CONSOLIDATED-ORDERS phases
- Phase 1: Temperature scaling (backtest T = 0.9, 1.0, 1.05, 1.08, 1.1, 1.2)
- Phase 2: Spatial smoothing (Gaussian sigma = 0.5, 1.0, 1.5)
- Phase 3: Collapse thresholding (0.016, 0.020, 0.025)

Quick backtests. Run them before R9 opens.

### 4. R9 opens ~20:01 CET
Submit with best config from backtests. R9 weight ~1.55, worth more than any previous round.

### 5. Boris workflow
Run code-reviewer and backtester before every commit.

Report results to intelligence/for-overseer/ml-status.md.
