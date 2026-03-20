# Operations Agent — Dashboard Plan

## What We're Building
A competition dashboard forked from `/Volumes/devdrive/github_dev/NM_I_AI_dash/` adapted for the 3-track NM i AI 2026 competition. JC sees all tracks at a glance: scores, status, visualizations.

## Architecture Decisions

### Keep from existing dashboard
- React 19 + TypeScript + Vite + Tailwind v4
- Recharts for charts
- Zustand for UI state
- MetricCard component (reuse as-is)
- Canvas pan/zoom/resize infrastructure from GameCanvas
- Glass-morphism design language (bg-white/50 backdrop-blur)

### Remove
- Convex (real-time DB) — replaced with local JSON files + fetch() calls
- All grocery-bot-specific types, components, and game logic
- Bot/item rendering from GridRenderer

### New
- TerrainGrid: canvas renderer for 40x40 Astar Island maps (color-coded terrain)
- CVMonitor: training curves from GCP VM logs
- NLPTracker: endpoint health check + task type status
- Tabbed layout: Overview | ML (Astar) | CV (NorgesGruppen) | NLP (Tripletex)

## Data Sources

| Component | Source | Method |
|-----------|--------|--------|
| Terrain grid | `agent-ml/solutions/data/viz_data.json` | Read local file via Vite public or fetch |
| CV training curves | GCP VM `cv-train-1` logs | `gcloud compute ssh` to pull, or expose via a log file |
| NLP endpoint status | `https://tripletex-agent-795548831221.europe-west4.run.app/solve` | Fetch with HEAD/GET (CORS may block — use proxy or server) |
| Leaderboard | Manual entry or API scrape into JSON | Read local JSON |

## Terrain Type Color Map (from ML agent code)

| Raw Value | Terrain | Color | Hex |
|-----------|---------|-------|-----|
| 0 | Empty | Light beige | #f5f0e1 |
| 11 | Plains | Light beige | #f5f0e1 |
| 1 | Settlement | Brown | #a0845c |
| 2 | Port | Blue | #4a9eda |
| 3 | Ruin | Red | #c45c5c |
| 4 | Forest | Green | #5a9e5a |
| 5 | Mountain | Gray | #8a8a8a |
| 10 | Ocean | Dark blue | #2a5a8a |

## Build Sequence

### Phase 1: Scaffold (Priority A-1)
1. Copy package.json, vite.config.ts, tsconfig files from existing dash
2. Strip Convex, keep React/Vite/Tailwind/Recharts/Zustand
3. Create new tab structure: Overview | ML | CV | NLP
4. Adapt MetricCard (copy as-is)
5. Create new DashboardLayout with 4 tabs
6. Verify `npm run dev` works

### Phase 2: Astar Island Grid Viewer (Priority A-2)
1. Write TerrainRenderer.ts (replace GridRenderer.ts)
   - 40x40 grid, color-coded by terrain type
   - Keep pan/zoom/click from GameCanvas
   - Click shows cell info (terrain type, coordinates)
2. Write TerrainGrid.tsx component wrapping the canvas
3. Load viz_data.json (copy to public/ or import directly)
4. Show seed selector (5 seeds), round data, ground truth toggle

### Phase 3: CV Training Monitor (Priority A-3)
1. Create CVMonitor.tsx
2. Pull training logs from GCP VM (write a small shell script)
3. Parse YOLO/training logs into JSON: epoch, mAP50, mAP50-95, P, R
4. Recharts line chart for training curves
5. Auto-refresh mechanism (poll log file every 30s)

### Phase 4: NLP Task Tracker (Priority A-4)
1. Create NLPTracker.tsx
2. Endpoint health check (fetch with timeout)
3. Task type grid: 30 types, showing tested/untested/passing/failing
4. Score display per task type

### Phase 5: Overview Tab (Priority B)
1. Cross-track MetricCards (score per track, overall position)
2. Leaderboard tracker with score progression chart (adapt ScoreProgressionChart)
3. Timeline of submissions

## Priority B: Dashboard Enhancements

### B1. Leaderboard Tracker with Score Progression Chart
- Leaderboard data source: Playwright scraper (adapt leaderboard.py from old dash) saves to `public/data/leaderboard.json`
- Dashboard reads JSON, shows top 10 + our position
- Score progression chart using Recharts (adapt ScoreProgressionChart)
- Columns: Rank, Team, Tripletex, Astar, NorgesGruppen, Total, Delta
- Run scraper manually: `python3 tools/scrape_leaderboard.py` (not automated, JC triggers)

### B2. CV Detection Visualizer
- Load sample images + prediction JSON
- Render bounding boxes on canvas overlay
- Color by confidence, label with category name
- Source: agent-cv outputs predictions.json

### B3. Cross-Track Score Overview
- Combined score card on Overview tab
- Our rank + score per track
- Populated from leaderboard.json

## Status

### Done (Priority A)
- [x] A1: Dashboard scaffold (React 19 + Vite + Tailwind v4)
- [x] A2: Astar Island grid viewer (40x40, color-coded, pan/zoom)
- [x] A3: CV training monitor (Recharts curves from JSON)
- [x] A4: NLP task tracker (endpoint health, 30 task types)
- [x] Overview tab with competition clock
- [x] Code review: 6 issues found and fixed
- [x] Submission investigation: no APIs exist, manual only

### In Progress (Priority B)
- [x] B1: Leaderboard tracker
- [x] B2: CV detection visualizer
- [x] B3: Cross-track score overview

### In Progress (Iteration 2: Branding + ML map fix)
- [ ] C1: Copy logos to dashboard, add to header and all tabs
- [ ] C2: ML map comparison view: initial terrain vs ground truth (argmax)
- [ ] C3: ML diff highlight showing which 1200/1600 cells changed
- [ ] C4: Ground truth is 40x40x6 probability distribution. Show as heatmap or argmax.
- [ ] C5: QC with webapp-testing Playwright visual check

#### ML Ground Truth Data Format
- `ground_truth` is a list of round objects, each with `seeds` array
- Each seed has `initial_grid` (int[][]) and `ground_truth` (float[][][], 6-class probabilities)
- 1200/1600 cells change between initial and ground truth argmax
- Cell [0][0] = [1.0, 0, 0, 0, 0, 0] means 100% Empty
- Cell [5][5] = [0.405, 0.365, 0, 0.05, 0.18, 0] means mixed probabilities

## What JC Will See
A local React dashboard at localhost:5174 with 4 tabs. Open it in browser, see competition status at a glance. No deployment needed during competition — runs locally.

## Component Reuse Map

| Existing Component | Reuse | Adapt How |
|-------------------|-------|-----------|
| DashboardLayout.tsx | Heavy adapt | Strip Convex, new tabs (Overview/ML/CV/NLP) |
| GameCanvas.tsx | Heavy adapt → TerrainGrid.tsx | Replace bot/item rendering with terrain colors |
| GridRenderer.ts | Heavy adapt → TerrainRenderer.ts | Color cells by terrain type instead of walls/floors |
| MetricCard.tsx | Copy as-is | No changes needed |
| ScoreProgressionChart.tsx | Adapt | Remove Convex, use local data |
| LeaderboardComparison.tsx | Adapt | Change columns to 3 tracks |
| colors.ts | Replace | Terrain colors instead of grocery items |
| uiStore.ts | Adapt | New tab types, remove Convex types |
