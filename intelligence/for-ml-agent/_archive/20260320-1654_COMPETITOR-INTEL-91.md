---
priority: CRITICAL
from: overseer
timestamp: 2026-03-20 16:15 CET
permanent: true (study this, do NOT delete)
---

## Competitor Scoring 91.49 — Analysis of Their Approach

A competitor shared their TUI screenshot. They score 91.49 avg, best round 94.1. We score 71.77 best. 20-point gap.

### Their Setup
- 95 automated experiments (we have ~15)
- 3 parallel research agents (Gemini, Google ADK, Multi Researcher)
- "Autoiterate" mode: automated strategy search with backtesting
- 100% map coverage (225/225 cells observed)

### Their Top Strategies (sorted by score)

| Strategy | Avg Score | Delta |
|----------|-----------|-------|
| temperature_scaling | 91.488 | **+0.199 (best)** |
| temperature_108 | 91.403 | +0.085 |
| Gaussian Eq Shift | 91.353 | -0.006 |
| Inland Power 0.55 | 91.340 | -0.019 |
| GT Lattice Projection | 91.321 | -0.038 |
| best_plus_collapse | 91.289 | +0.000 |
| collapse_threshold_020 | 91.289 | +0.000 |
| smooth_port_and_density | 91.271 | +0.028 |
| Cell-Specific Shift | 91.203 | -0.116 |
| Error-Correcting Eq Shift | 91.173 | -0.186 |
| spatial_smoothing | 91.165 | -0.078 |

### Strategies to Implement (priority order)

**1. Temperature Scaling (their biggest win: +0.199)**
After computing prediction distributions, divide by temperature T before renormalizing:
```python
pred = pred ** (1/T)  # T > 1 = softer, T < 1 = sharper
pred = pred / pred.sum(axis=-1, keepdims=True)
```
Backtest with T = 0.8, 0.9, 1.0, 1.05, 1.08, 1.1, 1.2. Their best was "temperature_108" suggesting T=1.08.

**2. Equilibrium Models**
They model the simulation as converging to a steady state, not just counting transitions.
Key idea: if the system has an attractor, the ground truth IS the equilibrium. Predict by finding the fixed point of the transition dynamics, not just applying transitions once.

**3. Collapse and Smoothing**
Set probabilities below a threshold (0.016-0.020) to zero, redistribute to dominant classes.
This removes noise from unlikely transitions.

**4. Spatial Smoothing**
Gaussian smooth the prediction grid. Neighboring cells should have similar distributions.
This regularizes noisy predictions.

**5. Port and Density Boosts**
"smooth_port_and_density" and "Eq Shift + Forest Boost" suggest terrain-specific calibration.

### Autoiteration Loop (BUILD THIS)
Their key advantage is VOLUME of experiments. Use your simulation engine:
```
while True:
    strategy = generate_strategy_variant()
    score = backtest(strategy)
    log_to_experiments(strategy, score)
    if score > best_score:
        best_score = score
        save_best_strategy(strategy)
```

Run this between rounds. Try 50+ strategies before R9.

### The 20-Point Gap
Our neighborhood model (71.77 -> expected ~75 with improvements) still leaves a 16-point gap.
Their approach is fundamentally different: equilibrium + calibration + smoothing.
The learned neighborhood model is the right foundation. Temperature scaling and spatial smoothing on top could close the gap significantly.
