# Reusable Tools from Grocery Bot Archive

**Location:** `~/projects/_archive-nmiai-grocery-bot/`

These tools were built for a previous competition iteration. Many components are reusable or can inspire solutions for the current 3 tasks. **Do NOT copy blindly — adapt what's useful.**

---

## Authentication & API

| Tool | Path | What it does |
|------|------|-------------|
| **login.py** | `tools/login.py` | Fetches game tokens from app.ainm.no using persistent browser session (Playwright). First run opens browser for Google OAuth, subsequent runs reuse saved cookies headlessly. **Directly reusable for Astar Island API auth.** |
| **lib.py** | `tools/lib.py` | Shared functions: auth token management, HTTP helpers, constants. Used by pipeline, batch, ab_compare. |

## Data & Leaderboard

| Tool | Path | What it does |
|------|------|-------------|
| **leaderboard.py** | `tools/leaderboard.py` | Scrapes NM i AI leaderboard, outputs CSV. **Reusable as-is for tracking competitor scores.** |
| **extract-maps.py** | `tools/extract-maps.py` | Connects via WebSocket, grabs game state JSON, saves locally. Pattern reusable for Astar Island data extraction. |
| **render-exact-maps.py** | `tools/render-exact-maps.py` | Renders game maps as PNG from captured JSON data. |

## Game Execution

| Tool | Path | What it does |
|------|------|-------------|
| **play_game.py** | `tools/play_game.py` | Plays a single game via HTTP/WebSocket, captures replay. Pure HTTP auth (no browser needed). |
| **play_campaign.py** | `tools/play_campaign.py` | Runs bot against game server with logging. CLI: `--bot file.py --url wss://... --map medium` |
| **pipeline.py** | `tools/pipeline.py` | One-command pipeline: auth → leaderboard → play games → import results. **Pattern reusable for any automated submission pipeline.** |

## Testing & Comparison

| Tool | Path | What it does |
|------|------|-------------|
| **batch.py** | `tools/batch.py` | Run N games of a mode, collect stats. Usage: `python3 tools/batch.py nightmare 10 --tag v42` |
| **run_batch.py** | `tools/run_batch.py` | Simpler batch runner with cooldown between games (45s default). |
| **ab_compare.py** | `tools/ab_compare.py` | A/B test two bot versions with statistical analysis. **Pattern directly reusable for comparing model versions on any track.** |
| **determinism_test.py** | `tools/determinism_test.py` | Tests whether bot produces deterministic actions given different inputs. |

## Analysis & Profiling

| Tool | Path | What it does |
|------|------|-------------|
| **analyze_replay.py** | `tools/analyze_replay.py` | Deep replay analysis for game runs — timing, bottlenecks, per-round breakdowns. |
| **game_analyzer.py** | `tools/game_analyzer.py` | Combined replay profiler + hindsight analysis. Calculates theoretical max score by modeling optimal bot behavior. |
| **oracle_sim.py** | `tools/oracle_sim.py` | Collision-free oracle simulator — shows what a perfect bot could score with same inputs. **Pattern reusable for calculating theoretical ceiling on any track.** |
| **hindsight_analyzer.py** | `tools/hindsight_analyzer.py` | Post-game analysis: what could we have done better? |
| **stuck_analyzer.py** | `tools/stuck_analyzer.py` | Identifies when/where bots get stuck (deadlocks, congestion). |
| **bot_profiler.py** | `tools/bot_profiler.py` | Performance profiler for bot code — identifies slow functions. |
| **map_analysis.py** | `tools/map_analysis.py` | Full map structure analysis (wall layout, one-way aisles, bottleneck detection). |

## Solver Components (Advanced)

| Tool | Path | What it does |
|------|------|-------------|
| **sta_star.py** | `solver/sta_star.py` | Space-Time A* pathfinder with reservation table. Collision-free paths in (x,y,t) space. |
| **simulator.py** | `solver/simulator.py` | Forward simulation engine for MCTS rollouts — lightweight game rules engine. |
| **mcts.py** | `solver/mcts.py` | UCB1 multi-armed bandit over goal assignments. ~127 evaluations in budget. |
| **game_state.py** | `solver/game_state.py` | Simulation state dataclasses (StaticMap, SimState). Clean separation of mutable/immutable state. |
| **converter.py** | `solver/converter.py` | Converts between real game state and simulation state. |
| **dor_solver.py** | `solver/dor_solver.py` | Offline solver with STA* — uses future knowledge for optimal assignment. |
| **nightmare_solver.py** | `solver/nightmare_solver.py` | DOR brain + PIBT legs — greedy assignment with full order knowledge. |
| **service.py** | `solver/service.py` | FastAPI wrapper for solver — exposes solver as HTTP API at localhost:8100. **Pattern reusable for Tripletex endpoint.** |
| **mapf_adapter.py** | `solver/mapf_adapter.py` | Bridge to MAPF-GPT neural solver (AAAI-2025). |

## What's Most Reusable Per Track

**Astar Island (ML):**
- `login.py` — auth token management
- `lib.py` — HTTP helpers
- `batch.py` / `ab_compare.py` — patterns for running experiments and comparing approaches

**Tripletex (NLP):**
- `solver/service.py` — FastAPI service pattern (adapt for /solve endpoint)
- `pipeline.py` — automated submission pipeline pattern
- `login.py` — auth flow

**NorgesGruppen (CV):**
- `ab_compare.py` — A/B comparison pattern for model versions
- `oracle_sim.py` — theoretical ceiling calculation pattern
- `batch.py` — batch evaluation pattern
