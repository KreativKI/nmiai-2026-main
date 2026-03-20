---
priority: URGENT
from: agent-ml
timestamp: 2026-03-20 20:55 UTC
---

## Build: Astar Island Visual Round Viewer

JC wants a VISUAL dashboard to watch rounds play out, not just numbers.

### What to build
A single HTML file that shows the 40x40 map as a color grid. JC double-clicks to open.

### Views (toggle buttons at top)
A. **Initial terrain** — what the map looked like at year 0
B. **Ground truth** — what actually happened (colored by most likely terrain, opacity = confidence)
C. **Our prediction** — what we predicted (same coloring)
D. **Error map** — red = we were wrong, green = we were right, brightness = how wrong
E. **Observation coverage** — blue intensity = how many times we observed each cell
F. **Tile value** — yellow intensity = how valuable each cell is for scoring

### Controls
- Dropdown: select round (1-9)
- Dropdown: select seed (0-4)
- Toggle buttons for views A-F
- Hover on any cell: show terrain type, probabilities, observation count

### Color scheme
- Ocean: #1a3a5c (dark blue)
- Empty: #d4d4d4 (light gray)
- Settlement: #e74c3c (red)
- Port: #3498db (blue)
- Ruin: #7f8c8d (brown-gray)
- Forest: #27ae60 (green)
- Mountain: #555555 (dark gray)

### Data
The data is JSON. Load from these paths (or embed):
- `agent-ml/solutions/data/ground_truth_cache/round_*.json` — has initial_states and ground_truth
- `agent-ml/solutions/data/tile_value_map.json` — tile values

### Technical
- Single HTML file, no server, no npm. Vanilla JS + Canvas or SVG.
- Each cell = 12x12 pixels (480x480 grid).
- Save to: `agent-ops/dashboard/map-viewer.html`
- Create desktop shortcut: `/Users/jcfrugaard/Desktop/Github_shortcuts/launch-map-viewer.command`

### Priority
JC is watching the competition live. This helps him understand what's happening.
