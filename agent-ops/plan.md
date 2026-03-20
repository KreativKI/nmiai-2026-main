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

## What JC Will See
A local React dashboard at localhost:5173 with 4 tabs. Open it in browser, see competition status at a glance. No deployment needed during competition — runs locally.

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
