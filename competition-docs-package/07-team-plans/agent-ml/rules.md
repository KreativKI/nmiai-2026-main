# Rules — Astar Island Norse World Prediction (ML Track)

**Task:** Predict terrain probability distribution over 50-year simulation  
**Metric:** Entropy-weighted KL Divergence (0-100 scale, higher is better)  
**Deadline:** Sunday 22 March 2026, 15:00 CET  

---

## Mandatory Fields

### Input
- **Map Size:** 40×40 grid (full map)
- **Viewport:** Max 15×15 per query
- **Queries:** 50 per round (shared across 5 seeds)
- **Terrain Classes:** 6 (probability distribution per cell)
- **Simulation:** 50 time steps (years)
- **Seeds:** 5 visible seeds, different sim seeds per query
- **Hidden Params:** Control world behavior (same for all seeds in round)

### Output
- **Format:** W×H×6 probability tensor per queried viewport
- **Delivery:** REST API predictions
- **Timeout:** 60 seconds per response
- **Probability:** Softmax over 6 classes per cell

### Scoring
- **Metric:** Entropy-weighted KL Divergence
- **Formula:** KL(P || Q) weighted by entropy of P (ground truth)
- **Scale:** 0-100 (higher is better)
- **Updates:** After each query (live scoring)

### Constraints
- **50 queries max:** Budget across 5 seeds
- **15×15 viewport:** Cannot query full 40×40 at once
- **Black box:** Simulator is opaque, learn from observations

---

## Approach Summary

### Approach C (Baseline): Heuristic Extrapolation
- Query grid in fixed pattern
- Linear interpolation for unqueried cells
- No ML model
- Expected: 30-40 score

### Approach B (Primary): CNN State Predictor
- 3×3 CNN predicting next state from neighbors
- Assume Markov property (state(t+1) depends only on state(t))
- Roll out 50 steps
- Expected: 50-60 score

### Approach A (Stretch): ConvLSTM + Active Learning
- ConvLSTM for spatio-temporal modeling
- Active learning: query high-entropy regions first
- Learn hidden parameters from behavior across seeds
- Expected: 75-85 score

---

## Query Strategy (Critical!)
- **Adaptive sampling:** Focus on boundaries between terrain types
- **Multi-scale:** Mix of 15×15 (context) and focused 5×5 (detail)
- **Information gain:** Prioritize cells with highest prediction uncertainty
- **Budget allocation:** 10 queries per seed, distributed temporally

## Validation Strategy
- Use visible seeds (0-4) for training/validation
- Cross-validation: train on 4 seeds, validate on 1
- Simulate 50 steps, compare to ground truth at each step

## Submission Loop
```python
# API interaction
for query in range(50):
    viewport_coords = select_viewport()  # Active learning
    response = api.query(viewport_coords)
    ground_truth = response.ground_truth  # For validation only
    score = response.score  # Live KL divergence
```

## Rules Last Read
2026-03-19 20:30 CET (Gunnar)
