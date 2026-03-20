# Operations Agent — Plan

## Current Phase: 15 — Dashboard Command Center

## Goal
Build a single-page dashboard that is THE place JC looks during the competition. Inspired by competitor's TUI, but as a web dashboard. ML terrain replay is the hero visual. All tracks visible. Agent idle alerts with sound + popup. Per-track reset countdowns.

## Reference: Competitor's TUI Features (from screenshot)
Left panel: experiment log table (ID, Name, Status, Avg, Delta, Time), per-round sparklines, best score, agent status (running/stopped)
Right panel: 40x40 terrain grid with colored terrain, seed tabs, terrain legend, coverage stats, cell counts, viewport selector, observation count
We match this in a browser, plus: idle agent alerts, per-track timers, NLP/CV data.

---

## Data Inventory (ALL Tracks)

### ML Track
| File | Content |
|------|---------|
| `agent-ml/solutions/data/viz_data.json` (678K) | Round 3 terrain grids, all 5 seeds, 40x40 cells |
| `agent-ml/solutions/data/learned_transitions.npy` | 6x6 transition matrix (rounds 1-2) |
| `agent-ml/status.json` | Agent state, last update, score |
| `shared/tools/ml_results.json` (2K) | Prediction validation log |
| `agent-ml/solutions/map-viewer.html` (17K) | Standalone HTML map viewer (port features) |
| API: GET /my-rounds | Score history per round |
| API: GET /my-predictions/{round_id} | Our submitted predictions |
| API: GET /analysis/{round_id}/{seed_index} | Post-round ground truth |
| API: GET /rounds | Round list with timing (for next-round countdown) |
| API: GET /budget | Queries remaining in current round |

### NLP Track
| File | Content |
|------|---------|
| `shared/tools/nlp_submission_log.json` | Submission scores (checks_passed/total, percentage, daily budget) |
| `agent-nlp/status.json` | Agent state, last update, current task |
| Competition page data | Total score 17.7, rank #110, 15/30 tasks solved, 37/180 daily used |
| Agent logs (Cloud Run) | Error rates, response times |

### CV Track
| File | Content |
|------|---------|
| `shared/tools/cv_results.json` | Validation results (verdict, mAP scores) |
| `agent-cv/status.json` | Agent state, last update, current task |
| Training metrics | YOLO11m: mAP50 0.945 (local), 0 competition submissions |

### Cross-Track
| File | Content |
|------|---------|
| `dashboard/public/data/leaderboard.json` (67K) | Multi-snapshot leaderboard, all teams |
| Each agent's `status.json` | Last activity timestamp (for idle detection) |

### ML Data MISSING (need fetchers)
| Data | Source | Purpose |
|------|--------|---------|
| All rounds ground truth | API /analysis/{round_id}/{seed} | Full history, not just round 3 |
| Our prediction submissions | API /my-predictions/{round_id} | Compare predictions vs ground truth |
| Score progression per round | API /my-rounds | Chart score over time |
| Round timing | API /rounds | Next-round countdown |

---

## Tasks (each is a separate coding unit, Boris workflow)

### Task 1: ML Data Fetcher Script
**What:** Python script that fetches ALL ML data from API and saves dashboard-ready JSON.
**Output:** `shared/tools/fetch_ml_data.py`
**Fetches:**
- GET /rounds -> round IDs, metadata, timing (open/close timestamps for countdown)
- GET /my-rounds -> our scores per round
- GET /my-predictions/{round_id} -> our prediction tensors
- GET /analysis/{round_id}/{seed_index} -> ground truth (completed rounds)
- GET /budget -> queries remaining
**Saves to:**
- `dashboard/public/data/ml_rounds.json` (scores, round timing, budget)
- `dashboard/public/data/ml_terrain.json` (grids, predictions, ground truth per round per seed)
**Run:** On dashboard startup + cron every 30 min via launcher
**Skills:** None (pure Python)
**Boris:** Explore (ML CLAUDE.md API docs) -> Plan -> Code -> Review (code-reviewer agent) -> Validate (run script, verify JSON output) -> Commit

### Task 2: Terrain Tile Asset Generation (Gemini Flash 2.5)
**What:** Generate visual terrain tile sprites using Gemini Flash 2.5 via our GCP account. Replaces flat colored squares with actual game-like terrain art.
**Tiles needed (8 types):**
- Ocean (deep blue water)
- Empty (barren ground)
- Settlement (small houses/village)
- Port (dock/harbor)
- Ruin (crumbled buildings)
- Forest (trees)
- Mountain (rocky peaks)
- Unknown (fog/question mark)
**Tile specs:** 32x32px PNG sprites, top-down isometric style, consistent palette, transparent-friendly.
**Process:**
1. Use `cowork-prompt-enhancer-v3` skill to craft a system prompt for the tile generator
2. Review and iterate the prompt until quality is right
3. Build `shared/tools/generate_terrain_tiles.py` that calls Gemini Flash 2.5 via GCP (`generativelanguage` API, project `ai-nm26osl-1779`)
4. Generate all 8 tiles, save to `dashboard/public/assets/terrain/`
5. May need multiple iterations per tile for quality
**Skills:** `cowork-prompt-enhancer-v3` (prompt design), `kreativki-frontend` (asset integration)
**Boris:** Explore (Gemini image gen API docs) -> Plan (prompt iteration) -> Code (generator script) -> Review -> Validate (visual inspection of all 8 tiles) -> Commit

### Task 3: ML Explorer Page (Hero Feature)
**What:** Full-page ML terrain explorer. Separate page (not embedded in overview).
**Features:**
- 40x40 terrain grid rendered with tile sprites from Task 2 (canvas renderer)
- Seed tabs (Seed 0-4)
- Round selector dropdown (all available rounds)
- View modes: Initial / Ground Truth / Our Prediction / Diff (prediction vs GT) / KL Heatmap
- Terrain legend with per-type counts (like competitor: Settlement: 56, Forest: 332, etc.)
- Coverage stats: observed cells / total, observation coverage %
- Cell hover tooltip: terrain type, probability distribution bar, prediction confidence
- Zoom slider (cell size 16px -> 64px, tile-based rendering scales smoothly)
- Animation: replay Year 0 -> Year 50 with spreading cell-flip effect (already built, enhance with tile transitions)
- KL divergence heatmap overlay (red = bad prediction, green = good, semi-transparent over tiles)
- Side panel: per-round score sparkline, experiment log table (if EXPERIMENTS.md exists)
**Data source:** `ml_terrain.json` + `ml_rounds.json` from Task 1, existing `viz_data.json`
**Depends on:** Task 1 (data), Task 2 (tile assets)
**Skills:** `kreativki-frontend` for design, `webapp-testing` for Playwright verification
**Boris:** Explore (existing TerrainGrid.tsx, TerrainRenderer.ts, map-viewer.html) -> Plan -> Code -> Review (code-reviewer agent) -> Simplify (code-simplifier agent) -> Validate (Playwright: load page, click seeds, verify 40x40 grid renders with tiles, click all view modes, test zoom) -> Commit

### Task 4: Command Center Overview Page
**What:** Rewrite OverviewView.tsx. THE front page. Clear situation overview at a glance.
**Layout (top to bottom):**

1. **Competition clock** (keep, already works)

2. **Agent Status Strip** (3 columns, prominent):
   - Each track: name, status dot (green=active, red=idle, yellow=error), last activity time
   - Source: poll each agent's status.json every 60s
   - Red pulsing border when idle (>30 min since last update)

3. **Per-Track Reset Countdowns** (inline with status strip or below):
   - ML: "Next round in: Xh Ym" (from API /rounds timing)
   - NLP: "Rate limit resets in: Xh Ym" (countdown to 01:00 CET)
   - CV: "Submissions reset in: Xh Ym" (countdown to 01:00 CET)

4. **3-column Track Scorecards** (live numbers):
   - ML: score, rank, rounds participated, queries remaining this round
   - NLP: total score, tasks solved (X/30), submissions today (X/180), daily budget progress bar
   - CV: latest mAP, submissions used (X/10), model version, last error

5. **Mini ML terrain preview** (compact 200x200, auto-animating loop, seed dots, click -> ML Explorer)

6. **NLP submission feed** (last 10 results: score bars green/yellow/red, timestamps CET)

7. **Leaderboard** (keep existing table + score progression chart)

**Skills:** `kreativki-frontend` for design, `webapp-testing` for Playwright verification
**Boris:** Full loop with Playwright visual confirmation that all sections render with data

### Task 5: Agent Idle Detection + Sound/Popup Notifications
**What:** Alert JC when any agent is idle. Sound + browser popup.
**Implementation:**
- Poll each agent's status.json every 60s
- If `last_updated` > 30 min ago: agent is IDLE
- **Visual:** Red "IDLE" badge on agent card, pulsing red border
- **Browser notification:** Use Notification API. Request permission on page load. Push notification: "ML Agent idle for 45 minutes"
- **Sound alert:** Web Audio API oscillator beep (no external files). Short ascending chime when agent goes idle. Play once per transition (not repeatedly).
- Track idle state to avoid spamming: only alert on transition from active -> idle
**Skills:** `webapp-testing` for testing notification trigger (mock old timestamp)
**Boris:** Full loop

### Task 6: NLP Submission Feed Component
**What:** Scrollable list of NLP competition submissions with stats.
**Features:**
- Last 20 submissions in scrollable list
- Each entry: timestamp (CET, converted from UTC+1), checks_passed/total_checks, percentage bar (green >= 75%, yellow >= 25%, red < 25%)
- Summary stats row: avg score %, perfect count (100%), zero count (0%), daily budget progress bar (X/180)
- Auto-refresh: reload nlp_submissions.json every 60s
**Data source:** `dashboard/public/data/nlp_submissions.json`
**Skills:** `kreativki-frontend`, `webapp-testing`
**Boris:** Full loop

### Task 7: Navigation + Routing Update
**What:** Add ML Explorer as new tab. Restructure navigation.
**New tabs:**
- Overview (command center, front page)
- ML Explorer (full terrain viewer, Task 2)
- Astar Island (keep existing MLView as "ML Summary" or merge into Explorer)
- NorgesGruppen (CV, keep)
- Tripletex (NLP, keep)
**Update:** DashboardTab type, DashboardLayout.tsx, tab pills
**Skills:** None
**Boris:** Full loop

### Task 8: Data Pipeline + Launcher Update
**What:** Update launcher to copy ALL track data and run fetchers.
**Changes to `launch-nmiai-ops-dashboard.command`:**
```bash
# Copy ML data
cp agent-ml/solutions/data/viz_data.json dashboard/public/data/
# Copy NLP submissions
cp shared/tools/nlp_submission_log.json dashboard/public/data/nlp_submissions.json
# Copy CV results
cp shared/tools/cv_results.json dashboard/public/data/ 2>/dev/null
# Copy ML results
cp shared/tools/ml_results.json dashboard/public/data/ 2>/dev/null
# Copy agent status files
for agent in cv ml nlp; do
  cp agent-$agent/status.json dashboard/public/data/${agent}_status.json 2>/dev/null
done
# Run ML data fetcher (if auth available)
agent-ops/.venv/bin/python3 shared/tools/fetch_ml_data.py 2>/dev/null
# Run leaderboard scraper
agent-ops/.venv/bin/python3 shared/tools/fetch_leaderboard.py 2>/dev/null
```
**Skills:** None (bash)
**Boris:** Full loop

### Task 9: Visual QA Pass (Playwright)
**What:** Full Playwright test suite. Every button, every data load, visual confirmation.
**Tests:**
- Overview: clock visible, 3 agent status cards render, 3 track scorecards render, countdown timers show, leaderboard renders, mini terrain preview animates
- ML Explorer: 40x40 grid renders (count cells), all 5 seed tabs clickable, all view modes work, zoom slider changes cell size, hover shows tooltip
- NLP feed: submissions list loads, score bars render with correct colors, budget bar accurate
- Agent idle: inject old timestamp, verify red badge + pulsing border appear
- Notifications: verify Notification.requestPermission called
- Responsive: 1920x1080 and 1440x900 viewports
**Skills:** `webapp-testing` for ALL tests
**Boris:** This IS the validation step for the whole dashboard

---

## Execution Order
```
Task 1 (ML data fetcher)     ─┬─ parallel ─── Task 2 (Terrain tile assets via Gemini)
                              │                       │
Task 6 (NLP feed component)  ─┘                       │
                              │                       │
Task 8 (Launcher update)     ─┘                       │
                              │                       │
Task 3 (ML Explorer page)   ─┤  depends on Tasks 1+2  │
                              │                       │
Task 4 (Command Center)     ─┤  depends on Tasks 3+6  │
                              │                       │
Task 5 (Idle detection)     ─┤  parallel with Task 4  │
                              │                       │
Task 7 (Navigation update)  ─┤  after Tasks 3+4       │
                              │                       │
Task 9 (Visual QA)          ─┘  last, validates all   │
```

## Skills Used
| Skill | Where |
|-------|-------|
| `cowork-prompt-enhancer-v3` | Task 2 (craft Gemini tile generation prompt) |
| `kreativki-frontend` | Tasks 3, 4, 6 (UI design + implementation) |
| `webapp-testing` | Tasks 3, 4, 5, 6, 9 (Playwright visual verification) |
| code-reviewer agent | Every task (Boris review step) |
| code-simplifier agent | Every task (Boris simplify step) |
| build-validator agent | Every task (Boris validate step) |

## Decisions Made

A. **Sound:** Subtle, wind-like ambient chime. Plays once per idle transition, not repeating.
B. **Priority:** Data pipeline first (Tasks 1, 5, 7), then visuals (Tasks 2, 3).
C. **map-viewer.html:** Port features into React dashboard. Single source of truth.
D. **Dev mode:** Vite hot reload on localhost:5174 so JC can watch progress live.

---

## Completed Phases (1-14)

### Phase 1-4: Dashboard Foundation (done)
Dashboard scaffold (React 19 + Vite + Tailwind v4), terrain grid viewer, ML animation, CV training monitor, NLP health check, leaderboard tracker, Kreativ KI branding, desktop launcher.

### Phase 5: Sleep Report (done)

### Phase 6: QC Judge Tools (done)
cv_judge.py, ml_judge.py with verdict system (SUBMIT/SKIP/RISKY).

### Phase 7: CV Submission Profiler (done)
cv_profiler.py: timing analysis, GO/NO-GO verdict against 300s timeout.

### Phase 8: A/B Compare Tool (done)
ab_compare.py: side-by-side prediction comparison with Welch's t-test.

### Phase 9: Batch Eval Tool (done)
batch_eval.py: rank all CV submissions in one run.

### Phase 10: Oracle/Ceiling Estimator (done)
oracle_sim.py: theoretical ceiling per track.

### Phase 11-13: TUI + Monitoring (done)
Real-time agent monitoring, scoreboard, sparklines, keyboard hints.

### Phase 14: Emergency Intelligence Briefings (done)
Briefings to all 3 agents: CV submit NOW, ML wake up, NLP maximize submissions.
