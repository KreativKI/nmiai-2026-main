---
priority: HIGH
from: agent-ml
timestamp: 2026-03-20 19:55 UTC
---

## Build: Astar Island Map Visualization

JC wants to SEE what's happening on the maps. Build an HTML visualization that shows:

### What to visualize
A. **Initial terrain map** (40x40 grid, color-coded by terrain type)
B. **Prediction map** (40x40, colored by most likely predicted terrain, opacity = confidence)
C. **Observation coverage** (which cells were observed, how many times)
D. **Ground truth** (for completed rounds, the actual outcome)
E. **Error map** (where our predictions were wrong, highlighted in red)

### Color scheme
- Empty: light gray
- Settlement: red
- Port: blue
- Ruin: brown/dark gray
- Forest: green
- Mountain: dark gray
- Ocean: dark blue

### Data sources
All data is in `agent-ml/solutions/data/`:
- Ground truth cache: `ground_truth_cache/round_*.json`
- Observation data: `obs_counts_r*_seed0_*.npy`, `obs_total_r*_seed0_*.npy`
- Tile values: `tile_value_map.json`

### Requirements
- Single HTML file with embedded JavaScript (no server needed)
- Dropdown to select round and seed
- Toggle between: initial / prediction / ground truth / error / observation coverage / tile value
- Cell hover shows: terrain type, probabilities, observation count
- Save to: `agent-ops/dashboard/map-viewer.html` or similar

### Context
The map is 40x40 cells. Row 0 and row 39 are ocean. Mountains are scattered.
Settlements, ports, forests, and empty cells are the dynamic terrain.
JC is non-technical, needs visual understanding of what the model is doing.
