# Simulation Engine Plan

## Problem
We test query strategies live (1 attempt per round, 50 queries, ~3h wait).
We need to test hundreds of strategies offline using data we already have.

## Core Insight
Ground truth = probability distributions per cell. The API "observes" by
sampling from these distributions. We can do the same with numpy.random.choice.
This lets us simulate any query strategy against any completed round.

## Architecture

### SimulationEngine (simulate.py)
```
SimulationEngine
  |-- takes: ground_truth (round data with 40x40x6 distributions per seed)
  |-- can: simulate_observation(seed, viewport) -> sampled terrain grid
  |-- can: run_strategy(strategy_config) -> score
  |-- can: monte_carlo(strategy_config, n_trials=100) -> avg_score, std
```

### QueryStrategy (configurable pipeline)
A strategy is a sequence of steps:
```python
strategy = {
    "batches": [
        {"queries": 9, "target": "overview", "seed": 0},       # Full map overview
        {"queries": 0, "target": "hindsight", "seed": 0},       # Analyze, re-target
        {"queries": 10, "target": "surprise", "seed": 0},       # Target high-surprise
        {"queries": 0, "target": "hindsight", "seed": 0},       # Analyze again
        {"queries": 10, "target": "surprise", "seed": 0},       # More stacking
        {"queries": 0, "target": "hindsight", "seed": 0},
        {"queries": 10, "target": "surprise", "seed": 0},
        {"queries": 0, "target": "hindsight", "seed": 0},
        {"queries": 11, "target": "surprise", "seed": 0},       # Final batch
    ],
    "prediction_model_params": {...},
}
```

### Strategies to Test
A. Current v6: 9 overview + 41 blind stacking (no mid-round analysis)
B. Adaptive 4x10: 9 overview + 4 batches of 10 with hindsight between each
C. Adaptive 8x5: 9 overview + 8 batches of 5 with hindsight between each
D. Settlement-focused: 9 overview, then ONLY stack on settlement/port cells
E. Multi-seed: 9 overview seed 0, 9 overview seed 1, stack 32 on both
F. Greedy: after each batch, pick the viewport with highest predicted error

### Learning Loop
1. Run all strategies on all 6 rounds (100 Monte Carlo trials each)
2. Score each strategy's mean and variance
3. Identify which round characteristics favor which strategies
4. Build a simple rule: "if round has >200 changes, use strategy X; else use Y"

### Reinforcement: Positive/Negative Weights
For each query, compute its contribution to final score:
- Positive: query reduced prediction error for a high-entropy cell
- Negative: query increased error or targeted a low-entropy cell
- Neutral: query had no effect (static terrain, already well-predicted)

Accumulate weights per cell type, per distance from settlement, per observation count.
These weights become the "learned" query targeting policy.

## Output
- strategies_ranked.json: all strategies ranked by avg score across rounds
- learned_weights.json: per-cell-type query value weights
- best_strategy.json: the winning strategy config, ready to plug into v6

## Implementation: ~1 file, ~300 lines
Builds on existing backtest.py (PredictionModel, score_prediction) and
hindsight.py (compute_surprise, analyze_query_value).
