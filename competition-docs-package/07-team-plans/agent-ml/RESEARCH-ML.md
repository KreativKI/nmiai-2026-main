# RESEARCH-ML.md — Astar Island Norse World Prediction

**Track:** ML (Task 2)
**Agent:** agent-ml
**Date:** 2026-03-19 (Opus refresh at T+2.5h)
**Status:** Phase 2 RESEARCH — OPUS VALIDATED

---

## Problem Type
Spatio-temporal prediction on a 40×40 grid with 6 terrain classes. Black-box Norse civilisation simulator runs 50 time steps. Stochastic — same params yield different outcomes. Budget: 50 queries across 5 seeds. Predict W×H×6 probability tensor.

## Key Parameters
| Parameter | Value |
|-----------|-------|
| Map size | 40×40 cells |
| Terrain classes | 6 |
| Time steps | 50 years per simulation |
| Query budget | 50 total, shared across 5 seeds |
| Max viewport | 15×15 cells per query |
| Seeds per round | 5 (same hidden params, different stochastic) |
| Response time | 60 seconds |
| Metric | Entropy-weighted KL Divergence (0-100, lower is better) |
| API | api.ainm.no/astar-island/ |

## Critical Insight: The Real Challenge
This is NOT a standard ML problem. The key constraint is **50 queries for 5 seeds = extremely limited data**. The problem is really about:
1. **Query strategy** — what to observe to maximize information
2. **Generalization** — predicting unobserved cells from sparse observations
3. **Uncertainty calibration** — entropy-weighted scoring punishes overconfidence

## SOTA Resources

### 1. ConvLSTM for Grid-Based Temporal Prediction ⭐
- **Paper:** "Convolutional LSTM Network: A Machine Learning Approach for Precipitation Nowcasting" (Shi et al.)
- **Related:** 3DCNN+LSTM for spatial-temporal prediction (Tandfonline 2024)
- **Match:** 85% — ConvLSTM was designed for exactly this: spatiotemporal grid prediction
- **Architecture:** Encode spatial+temporal dependencies in a single cell
- **Adaptation:** Feed 40×40×6 one-hot grids, predict next state distribution

### 2. Neural Cellular Automata (NCA)
- **Paper:** "Learning spatio-temporal patterns with Neural Cellular Automata" (PMC 2024)
- **Match:** 70% — Learns local update rules with minimal parameters
- **Key insight:** If the simulator IS a CA (likely, given grid + local rules), NCA has perfect inductive bias
- **Risk:** May underfit if simulator has global/long-range rules (trade routes, alliances)

### 3. Cellular Automata as CNNs
- **Paper:** arXiv:1809.02942 — "Cellular Automata as Convolutional Neural Networks"
- **Key insight:** Any CA can be represented as a CNN with appropriate kernel
- **Approach:** Train small CNN to predict next-state transitions

### 4. Ensemble Methods (Uncertainty Calibration)
- For the entropy-weighted metric, calibrated probabilities are essential
- **Temperature scaling** post-hoc calibration
- **MC Dropout** for uncertainty estimation
- **Ensemble of small models** > one big model for calibration

## Approach Recommendations

### Approach A (Primary): Bayesian CA Estimator + ConvLSTM
1. **Phase 1 (Queries 1-20):** Strategic exploration
   - Query diverse viewports across all 5 seeds
   - Mix of 15×15 (broad coverage) and 5×5 (temporal detail)
   - Sample same locations across seeds to estimate transition probabilities
2. **Phase 2 (Queries 21-40):** Model training
   - Fit ConvLSTM on observed transitions
   - Use observed data as supervised training signal
3. **Phase 3 (Queries 41-50):** Targeted refinement
   - Query high-uncertainty regions (active learning)
   - Update model with new observations
4. **Prediction:** Roll out ConvLSTM for 50 steps, output softmax probabilities
5. **Time:** 6-8 hours
6. **Expected Score:** 70-85

### Approach B (Fallback): Transition Matrix + Spatial Interpolation
1. Observe transition probabilities from queries
2. Build per-terrain transition matrix (6×6)
3. Apply Markov chain for temporal prediction
4. Spatial interpolation (Gaussian process or kriging) for unobserved cells
5. **Time:** 3-4 hours
6. **Expected Score:** 45-60

### Approach C (Baseline — MUST SHIP FIRST): Uniform Prior + Observation Pass-through
1. Default prediction: uniform distribution [1/6, 1/6, 1/6, 1/6, 1/6, 1/6] per cell
2. For observed cells: use empirical distribution from queries
3. Smooth between observed and unobserved with distance-weighted average
4. **Time:** 1-2 hours
5. **Expected Score:** 25-35
6. **Purpose:** Valid submission, non-catastrophic baseline

## Query Strategy (CRITICAL)

### Budget Allocation
- 50 queries / 5 seeds = 10 queries per seed (if evenly distributed)
- BUT: better to over-sample 2-3 seeds deeply and extrapolate to others
- **Recommended:** 15 queries on seed 0, 15 on seed 1, 10 on seed 2, 5 each on seeds 3-4

### Viewport Strategy
- **Broad sweeps (15×15):** Cover 56% of map in 4 queries. Use early.
- **Focused probes (5×5 or 3×3):** Temporal detail on key regions. Use late.
- **Temporal coverage:** Query same viewport at different time steps to observe dynamics

### Information-Theoretic Querying
1. Start with 4 large viewports (15×15) to cover map
2. Identify high-variance regions
3. Focus remaining queries on high-uncertainty zones
4. Use entropy of current predictions to guide next query location

## Scoring Deep Dive

### Entropy-Weighted KL Divergence
- **KL divergence:** Measures how different your prediction is from truth
- **Entropy-weighted:** High-entropy cells (uncertain truth) matter LESS
- **Implication:** Focus accuracy on deterministic/low-entropy regions (cells that consistently become the same terrain)
- **Strategic insight:** It's better to be calibrated-uncertain than confidently wrong

### Calibration Strategy
- Use temperature scaling on output logits
- If using ensemble: average predictions across models
- **Never output hard labels** — always softmax probabilities
- Smooth predictions toward uniform where uncertain

## Critical Implementation Notes

### Data Flow
```
1. GET /round → get round_id, seed list, hidden params (opaque)
2. POST /query → viewport coordinates + seed_id → observed cells
3. POST /predict → submit W×H×6 tensor for each seed
```

### What "Hidden Parameters" Means
- Same for all 5 seeds in a round
- Controls simulator behavior (growth rates, conflict thresholds, etc.)
- Cannot be directly observed — must be inferred from query results
- **Key strategy:** Queries across seeds reveal hidden params (since map varies but params don't)

### Model Size Constraint
- 60s time limit — model must be fast at inference
- ConvLSTM with small hidden dim (32-64) should be fine
- No need for GPU during competition API calls (CPU inference OK for 40×40)

## Ceiling Analysis
- **What separates good from #1:**
  - Smart query strategy (information gain per query)
  - Correctly inferring hidden parameters
  - Calibrated uncertainty (don't be overconfident)
  - Cross-seed generalization (use all seeds to learn shared dynamics)
- **Theoretical ceiling:** 90+ (if you perfectly learn the simulator)
- **Realistic ceiling:** 75-85 (limited queries constrain learning)

## Next Steps (Priority Order)
1. Connect to Astar API, explore endpoints, get first observation
2. Understand exact query/predict API format
3. Implement Approach C (uniform prior + observed pass-through) — submit within 2h
4. Design query strategy (viewport selection logic)
5. Implement Approach B (transition matrix + interpolation) — 3-4h
6. If time: Approach A (ConvLSTM) — 6-8h

## References
- ConvLSTM: Shi et al. (NeurIPS 2015) — "Convolutional LSTM Network"
- NCA: PMC 2024 — "Learning spatio-temporal patterns with Neural Cellular Automata"
- CA-as-CNN: arXiv:1809.02942
- PyTorch Geometric Temporal: https://github.com/benedekrozemberczki/pytorch_geometric_temporal
