# TUI Plan — NM i AI 2026 Command Center

## Context
- JC uses a 27" horizontal monitor (~200-260 cols x 50-70 rows)
- Goal: mission control for full automation oversight
- See what each agent is doing in real time: current step, previous, next
- Reference: split-pane TUI with tabs, terrain grid, experiment tables
- kreativki-frontend aesthetic (dark bg, sky-blue accents)
- Gemini Flash available via GCP ADC for generation
- Built with Python `textual` 8.1.1

## Tab Layout (10 tabs, numbered hotkeys)

```
⚡ 0:Dashboard  1:Agents  2:Leaderboard  3:ML  4:CV  5:NLP  6:Submit  7:Tools  8:Logs  9:Settings
```

### Tab 0: Dashboard (default)
The "at a glance" view. Everything JC needs in one screen.

```
┌─────────────────┬─────────────────┬─────────────────┬──────────────────────┐
│ ⏱ DEADLINE      │ 🏔 ML Track     │ 📦 CV Track     │ 📝 NLP Track         │
│ FREEZE: 16h23m  │ Score: --       │ Best mAP: 0.945 │ Score: 18.4  #62     │
│ END:    22h12m  │ Rank: --        │ Subs: 3/10      │ Tasks: 13/30         │
│                 │ Rounds: 0       │ Verdict: NO-GO  │ Subs: 15/300         │
│ Budget          │ Obs: 0/50       │ (DINOv2 timeout)│ T1:7.3 T2:11.1 T3:0 │
│ ML: unlimited   │                 │                 │                      │
│ CV: 7/10 left   │ Last: waiting   │ Last: ensemble  │ Last: 7/7 (100%)     │
│ NLP: 285/300    │ Next: baseline  │ Next: fix conf  │ Next: more tasks     │
├─────────────────┴─────────────────┴─────────────────┴──────────────────────┤
│ LEADERBOARD TOP 10                                        OUR POS: #62     │
│  1. Kult Byrå          39.01  115.22   0.00  154.23                        │
│  2. Guru Meditation    16.89  117.35   3.75  137.99                        │
│  3. Slop Overflow      22.80  115.11   0.00  137.91                        │
│  ...                                                                       │
│ 62. Kreativ KI         18.44    0.00   0.00   18.44   ◀ US                 │
│                                                                             │
│ Score Over Time: ▁▂▃▃▅▆▇  (sparkline)                                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Tab 1: Agents (real-time agent monitoring)
Shows all 4 agents' live status. This is the automation oversight panel.

```
┌─ CV Agent ──────────────────────┬─ ML Agent ──────────────────────┐
│ State: ACTIVE                   │ State: WAITING                  │
│ Phase: ensemble-ready           │ Phase: waiting                  │
│ Confidence: 85%                 │ Confidence: --                  │
│                                 │                                 │
│ Previous: YOLO11m v2 submitted  │ Previous: --                    │
│ Current:  Ensemble ZIP ready    │ Current:  Waiting for round     │
│ Next:     Fix DINOv2 conf thres │ Next:     Submit baseline       │
│                                 │                                 │
│ GCP VMs:                        │ Obs budget: 0/50                │
│  cv-train-1: YOLO26m ep73      │ Rounds participated: 0          │
│  cv-train-2: RF-DETR ep24      │                                 │
│ Submissions: 3/10 today         │                                 │
├─ NLP Agent ─────────────────────┼─ Ops Agent (Butler) ────────────┤
│ State: ACTIVE                   │ State: ACTIVE                   │
│ Phase: deployed                 │ Phase: TUI build                │
│ Confidence: 75%                 │                                 │
│                                 │ Previous: CV validator fix      │
│ Previous: Bot deployed          │ Current:  Building TUI          │
│ Current:  Submitting tasks      │ Next:     Polish + commit       │
│ Next:     Cover more task types │                                 │
│                                 │ Tools built: 10                 │
│ Endpoint: HEALTHY               │ Last commit: 2m ago             │
│ Bot: tripletex_bot_v1           │                                 │
│ Tasks: 13/30 scored             │ Intelligence msgs: 2 unread     │
└─────────────────────────────────┴─────────────────────────────────┘
│ INTELLIGENCE FEED (latest messages across all agents)              │
│ 15:52 overseer->ops: UPDATE-CV-VALIDATOR.md                       │
│ 15:42 overseer->ops: UPDATE-AUTO-SUBMITTER-LIMIT.md               │
│ 14:02 overseer->ops: BUILD-NLP-AUTO-SUBMITTER.md                  │
│ 13:40 butler->ml: NEW-TOOL-oracle-sim.md                          │
│ 13:15 butler->cv: NEW-TOOL-ab-compare.md                          │
└───────────────────────────────────────────────────────────────────┘
```

Data sources:
- `agent-{cv,ml,nlp,ops}/status.json` (polled every 30s)
- `agent-{cv,ml,nlp}/plan.md` (parsed for current phase/tasks)
- `intelligence/for-*/` (file listing for message feed)

### Tab 2: Leaderboard
Full competition leaderboard with per-track breakdown.

```
┌─────────────────────────────────────────────────────────────────────┐
│  #   Team                      Tripletex  Astar   NorgesGr  Total  │
│  1   Kult Byrå                   39.01   115.22     0.00  154.23   │
│  2   Guru Meditation             16.89   117.35     3.75  137.99   │
│  ...                                                                │
│ 62   Kreativ KI ◀               18.44     0.00     0.00   18.44   │
│                                                                     │
│ Filter: [All] [ML only] [NLP only] [CV only]                       │
│ Search: _______________                                             │
└─────────────────────────────────────────────────────────────────────┘
```

### Tab 3: ML Explorer
Terrain grid with proper resolution + round history.

```
┌── Round History ────────────┬── Terrain Grid (Seed 0) ──────────────────────┐
│ Round  Score   Weight  Time │                                                │
│ (no rounds yet)             │  0123456789012345678901234567890123456789       │
│                             │ 0▲▲♠♠·⌂⌂·♠♠▲▲♠·⌂···♠♠▲▲♠♠·⌂⌂·♠♠▲▲♠♠·⌂⌂·♠♠▲▲│
│ Per-seed breakdown:         │ 1♠·⌂⌂·♠♠▲▲♠♠·⌂⌂·♠♠▲▲♠♠·⌂⌂·♠♠▲▲♠♠·⌂⌂·♠♠▲▲♠♠│
│ (submit to see scores)      │ 2·⌂⌂·♠♠▲▲♠♠·⌂⌂·♠♠▲▲♠♠·⌂⌂·♠♠▲▲♠♠·⌂⌂·♠♠▲▲♠♠·│
│                             │ ...                                            │
│ Observation budget:         │39·⌂⌂·♠♠▲▲♠♠·⌂⌂·♠♠▲▲♠♠·⌂⌂·♠♠▲▲♠♠·⌂⌂·♠♠▲▲♠♠·│
│  Used: 0/50                 │                                                │
│  Remaining: 50              │ [1]Seed0 [2]Seed1 [3]Seed2 [4]Seed3 [5]Seed4  │
│                             │ View: [I]nitial [P]redicted [G]round truth     │
│ Legend:                     │                                                │
│  ▲ Mountain (gray)          ├── Viewport Stats ─────────────────────────────│
│  ♠ Forest (green)           │ Coverage: 100%  Viewport: (0,0)               │
│  ⌂ Settlement (yellow)      │ Mountain:32 Forest:332 Settlement:56           │
│  ⚓ Port (blue)              │ Port:4 Ruin:0 Empty:218                       │
│  ✦ Ruin (red)               │ Settlements: 60 (60 alive)                    │
│  · Empty (dim)              │                                                │
└─────────────────────────────┴────────────────────────────────────────────────┘
```

Terrain symbols (single-char, colored, 1:1 mapping):
- `▲` Mountain (gray/white)
- `♠` Forest (bright green)
- `⌂` Settlement (yellow)
- `⚓` Port (cyan/blue)
- `✦` Ruin (red)
- `·` Empty (dark gray)
- `?` Unknown (dim magenta)

### Tab 4: CV Status
Submissions, profiler, training progress.

```
┌── Submissions ──────────────────────────────────────┬── Training ──────────┐
│  #  ZIP Name                  Det   Cls  Combined V │ YOLO11m (cv-train-1) │
│  1  submission_yolo11m_v1    FAIL                   │ Epoch: 100/100 DONE  │
│  2  submission_yolo11m_v2    pend                   │ mAP50: 0.945         │
│  3  submission_yolo11m_v3    pend                   │                      │
│  4  submission_dinov2_v1     NO-GO (timeout 49x)    │ YOLO26m (cv-train-1) │
│  5  submission_ensemble_v1   pend                   │ Epoch: 73/100        │
│                                                      │ mAP50: 0.914         │
│ Remaining today: 7/10                                │                      │
│                                                      │ RF-DETR (cv-train-2) │
│ Profiler: DINOv2 = 4882% over budget                │ Epoch: 39/?          │
│ Root cause: 1303 detections/image at conf=0.05       │ mAP50: 0.572         │
│ Fix needed: raise CONF_THRESHOLD                     │                      │
│                                                      │ DELETE VMs when done │
│ QC Judge: run cv_judge.py before any submission      │                      │
└──────────────────────────────────────────────────────┴──────────────────────┘
```

### Tab 5: NLP Submit
30-task grid + interactive submission.

```
┌── Task Coverage (13/30) ───────────────────────────┬── Recent Results ──────┐
│ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐  │ 7/7  (100%)  16.2s   │
│ │ T01 │ │ T02 │ │ T03 │ │ T04 │ │ T05 │ │ T06 │  │ 7/7  (100%)  14.3s   │
│ │ 2.0 │ │ 1.5 │ │ --  │ │ 0.8 │ │ --  │ │ 3.0 │  │ 4/8  ( 50%)  29.5s   │
│ │ 2x  │ │ 1x  │ │     │ │ 3x  │ │     │ │ 1x  │  │ 0/8  (  0%)   7.9s   │
│ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘  │ 6/7  ( 86%)   7.0s   │
│ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐  │ 8/8  (100%)  16.7s   │
│ │ T07 │ │ T08 │ │ T09 │ │ T10 │ │ T11 │ │ T12 │  │ ...                   │
│ │ ... │ │ ... │ │ ... │ │ ... │ │ ... │ │ ... │  │                       │
│ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘  │ Endpoint: HEALTHY    │
│ ...3 more rows of 6...                             │ Bot: tripletex_v1     │
│                                                     │                       │
│ Total: 18.4 | Solved: 13/30 | Rank: #62            │ Daily: 15/300         │
│ Tier1: 7.31 | Tier2: 11.13 | Tier3: 0.00           │                       │
│ vs #1 Kult Byrå: 39.01 across 18 tasks             │ [S]ubmit  [R]efresh  │
│ GREEN=scored GREY=unattempted RED=0 YELLOW=low      │                       │
└─────────────────────────────────────────────────────┴───────────────────────┘
```

### Tab 6: Submit (cross-track submission control)
Unified submission panel for all tracks.

```
┌── NLP Submissions ──────────┬── CV Submissions ──────────┬── ML Submissions ─┐
│ Budget: 285/300 remaining   │ Budget: 7/10 remaining     │ API: automatic     │
│ Endpoint: HEALTHY           │ Last: ensemble (pending)   │ Next round: TBD    │
│                             │                             │                    │
│ [S] Submit now              │ Validate first:             │ Status: waiting    │
│ [A] Auto-submit (225 max)   │  1. validate_cv_zip.py     │                    │
│                             │  2. cv_profiler.py          │                    │
│ Last: 7/7 (100%) 16.2s     │  3. cv_judge.py             │                    │
│                             │  4. ab_compare.py           │                    │
└─────────────────────────────┴────────────────────────────┴────────────────────┘
```

### Tab 7: Tools
Launch shared tools from TUI.

```
┌── Shared Tools ─────────────────────────────────────────────────────────────┐
│  [1] cv_judge.py        Score CV submission (det + cls mAP)                │
│  [2] ml_judge.py        Validate + score ML predictions                    │
│  [3] cv_profiler.py     Check if submission fits 300s timeout              │
│  [4] ab_compare.py      Compare two prediction sets                        │
│  [5] batch_eval.py      Rank all CV submissions                            │
│  [6] oracle_sim.py      Theoretical ceiling per track                      │
│  [7] fetch_leaderboard  Fetch live leaderboard from API                    │
│  [8] nlp_auto_submit    NLP auto-submitter (interactive)                   │
│  [9] validate_cv_zip    Validate CV ZIP structure                          │
│                                                                             │
│ Press number to launch. Output appears below.                               │
├── Output ───────────────────────────────────────────────────────────────────┤
│                                                                             │
│ (no tool running)                                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Tab 8: Logs
Combined filterable log viewer.

```
┌── Filters: [A]ll [M]L [C]V [N]LP [O]ps  Search: _________ ─────────────────┐
│ 15:52 [OPS] CV validator updated: .npz added to allowed extensions          │
│ 15:42 [OPS] NLP submitter updated: 300/day, 10/type                         │
│ 15:30 [NLP] Submission 15: Task (7/7) 100% in 16.2s                         │
│ 15:29 [NLP] Submission 14: Task (7/7) 100% in 14.3s                         │
│ 14:16 [OPS] NLP auto-submitter: first test submission                        │
│ 14:02 [OVR] New order: BUILD-NLP-AUTO-SUBMITTER                             │
│ 13:55 [OPS] Leaderboard fetch: 287 teams, #1 Kult Byrå 154.23              │
│ 13:40 [OPS] Phase 9-10: batch_eval + oracle_sim committed                   │
│ 13:15 [OPS] Phase 8: ab_compare committed                                   │
│ 12:45 [OPS] DINOv2 profiler: NO-GO (4882% over timeout)                     │
│ 12:10 [OPS] Phase 6: cv_judge + ml_judge committed                          │
│ ...                                                                          │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Tab 9: Settings
Configuration panel.

```
┌── Refresh Intervals ────────┬── API Status ──────────────┬── Paths ──────────┐
│ Leaderboard: 60s            │ ML API:  CONNECTED         │ Repo: nmiai-2026  │
│ Agent status: 30s           │ NLP API: CONNECTED         │ Branch: agent-ops │
│ File watch: 5s              │ NLP Bot: HEALTHY           │ Worktree: yes     │
│                             │ GCP:     AUTHENTICATED     │                    │
│ Auto-submit: OFF            │                             │ Tools: shared/    │
│ Max submissions: 225        │ Last fetch: 2s ago          │ Logs: tui/logs/   │
└─────────────────────────────┴────────────────────────────┴────────────────────┘
```

## Status Bar (always visible)
```
⚡connected · Rank #62 · Score 18.4 · NLP 13/30 · CV 7/10 · ML R0 · ⏱ FREEZE 16h23m · END 22h12m
```

## File Structure
```
agent-ops/tui/
├── app.py              # Main CompetitionTUI app class
├── style.tcss          # Kreativki theme CSS
├── data.py             # All data fetching: APIs, files, agent status
├── terrain.py          # Terrain grid rendering with single-char unicode
├── plan.md             # This file
├── views/
│   ├── __init__.py
│   ├── dashboard.py    # Tab 0: at-a-glance overview
│   ├── agents.py       # Tab 1: real-time agent monitoring
│   ├── leaderboard.py  # Tab 2: full leaderboard
│   ├── ml_explorer.py  # Tab 3: terrain grid + rounds
│   ├── cv_status.py    # Tab 4: submissions + training
│   ├── nlp_submit.py   # Tab 5: 30-task grid + results
│   ├── submit.py       # Tab 6: cross-track submission control
│   ├── tools.py        # Tab 7: tool launcher
│   ├── logs.py         # Tab 8: combined log viewer
│   └── settings.py     # Tab 9: configuration
```

## Terrain Rendering (single-char, colored)
```python
TERRAIN_CHARS = {
    "Mountain": ("▲", "bright_white"),
    "Forest":   ("♠", "green"),
    "Settlement": ("⌂", "yellow"),
    "Port":     ("⚓", "cyan"),
    "Ruin":     ("✦", "red"),
    "Empty":    ("·", "bright_black"),
    "Unknown":  ("?", "magenta"),
}
```
40 columns x 40 rows = 40 chars wide. On 27" screen this fits comfortably in the right pane with room to spare.

## Data Sources
| Source | Method | Refresh |
|--------|--------|---------|
| ML leaderboard | api.ainm.no GET | 60s |
| NLP leaderboard | api.ainm.no GET | 60s |
| Agent status | agent-*/status.json file read | 30s |
| Agent plans | agent-*/plan.md file parse | 60s |
| Intelligence msgs | intelligence/for-*/ file listing | 30s |
| ML terrain | viz_data.json | file watch |
| CV results | cv_results.json | file watch |
| NLP submissions | nlp_submission_log.json | file watch |
| Leaderboard history | leaderboard.json | file watch |

## Build Sequence (Boris for each)
1. **Skeleton**: app.py + style.tcss + tab scaffolds. Verify it launches.
2. **Data layer**: data.py with all fetchers + file watchers.
3. **Dashboard tab**: 3 track cards + mini leaderboard + deadline countdown.
4. **Agents tab**: 4 agent panels with status + plan parsing + intelligence feed.
5. **Leaderboard tab**: full DataTable with filtering.
6. **ML Explorer tab**: terrain grid + round history panel.
7. **NLP tab**: 30-task colored grid + recent results.
8. **CV tab**: submission table + profiler + training status.
9. **Submit tab**: cross-track submission controls.
10. **Tools tab**: tool launcher with output panel.
11. **Logs tab**: combined log with filters.
12. **Settings tab**: config display.
13. **Polish**: responsive sizing, status bar, keyboard shortcuts, kreativki colors.

## Design Principles
- Information density over decoration (27" screen = lots of space, use it)
- Color carries meaning: green=good, red=bad, yellow=warning, gray=inactive
- Every number should have context (X/Y format, percentages, deltas)
- Real-time: if data is stale >2min, show warning
- Keyboard-first: every action has a hotkey
