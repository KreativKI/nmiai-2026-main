---
priority: INFO
from: ml-agent
timestamp: 2026-03-20 13:15 CET
self-destruct: delete after integrating into dashboard
---

## ML Track Replay & Hindsight Data Available

Replay and hindsight analysis JSON files are now available for dashboard integration.

### File Locations (relative to repo root)
```
agent-ml/solutions/data/replays/
  latest_round.json           <- pointer to latest round
  query_rules.json            <- derived query allocation rules
  round_4_replay.json         <- per-seed: initial grid, ground truth, predictions, query heatmap
  round_4_hindsight.json      <- per-seed: info gain, wasted queries, missed opportunities
  round_5_replay.json
  round_5_hindsight.json
  round_6_replay.json
  round_6_hindsight.json
```

### Replay JSON format (for grid viewer)
Each `round_N_replay.json` contains per-seed:
- `initial_grid`: 40x40 terrain IDs
- `ground_truth_argmax`: 40x40 most-likely terrain
- `ground_truth_probs`: 40x40x6 probability tensor
- `prediction_argmax`: 40x40 our predicted terrain
- `prediction_confidence`: 40x40 confidence values
- `query_heatmap`: 40x40 observation count per cell
- `score`: seed score
- `diff_cells`: list of cells where prediction != ground truth

### Hindsight JSON format (for analysis view)
Each `round_N_hindsight.json` contains per-seed:
- `score_no_obs` / `score_with_obs` / `observation_boost`
- `terrain_summary`: per-terrain-class error and info gain
- `top_helpful` / `top_wasted`: best and worst queries
- `missed_opportunities`: high-error cells we never queried
- `optimal_overlap_pct`: how well our queries targeted highest-error cells

### Dashboard Integration Suggestions
A. MLView could load `latest_round.json` to auto-show most recent round
B. Add a "Query Heatmap" overlay to the terrain grid (use `query_heatmap`)
C. Add a "Hindsight" tab showing per-terrain error breakdown
D. The `query_rules.json` has derived rules for the strategy panel
