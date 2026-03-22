# Competition Assets — NM i AI 2026

**Repo:** [KreativKI/nmiai-2026-main](https://github.com/KreativKI/nmiai-2026-main) (public)
**Local (temporary):** `/Volumes/devdrive/github_dev/nmiai-2026-main/`
**Full audit:** `intelligence/for-jc/COMPETITION-ASSET-AUDIT.md` (in repo)
**Competition:** 69h, 4 concurrent Claude Code agents, 3 AI tracks, GCP L4 GPUs

---

## Reusable Tools (copy from repo `shared/`)

| Asset | Path in repo | Use when… |
|-------|-------------|-----------|
| **A/B Compare** | `shared/tools/ab_compare.py` | Comparing any two outputs with statistical rigor (Welch's t-test, per-item delta, verdict) |
| **Batch Eval** | `shared/tools/batch_eval.py` | Ranking N outputs/submissions by score |
| **Stats Library** | `shared/stats.py` | Need Welch's t-test, Cohen's d, or summary stats. Zero adaptation needed. |
| **Oracle/Ceiling** | `shared/tools/oracle_sim.py` | Estimating theoretical max to know when to stop optimizing |
| **Validation Pipeline** | `shared/tools/cv_pipeline.sh` | Template for any sequential validate→verdict workflow |
| **Health Check** | `health-check.sh` | Template for workspace/project pre-flight checks |
| **Leaderboard Fetcher** | `shared/tools/fetch_leaderboard.py` | Multi-endpoint API polling with timestamps and loop mode |

## Reusable Patterns (study, don't copy verbatim)

| Pattern | Path in repo | Use when… |
|---------|-------------|-----------|
| **OpenAPI-to-MCP bridge** | `tools/tripletex-mcp/server.py` | Building MCP server for any large API (Fiken, etc.). 2 dynamic tools instead of N static ones. |
| **API-calling AI agent** | `agent-nlp/solutions/tripletex_bot_v1.py` | Building FastAPI agent that uses Gemini function-calling to operate external APIs |
| **Multi-agent comms protocol** | `templates/COMMUNICATION-PROTOCOL.md` | Setting up file-based coordination between multiple AI agents |
| **Agent identity template** | `templates/CLAUDE-TRACK.md` | Scoping a new Claude Code agent (Boris workflow, anti-drift, experiment logging) |
| **Decision framework** | `templates/DECISION-FRAMEWORK.md` | Build vs Fork vs Adapt decision tree for any coding project |
| **Automation audit format** | `shared/tools/AUTOMATION-AUDIT.md` | Structured workspace audit (14 findings with problem/impact/effort/fix) |

## Key Numbers
- 9,300 lines of Python/Shell/TypeScript
- 5 baseline templates (object detection, RAG, tabular, text classification, image classification)
- 14 automation audit findings with ready-to-deploy fixes
- Tripletex MCP server handles 490+ API endpoints with just 2 tools

## Cleanup Plan
When local folder is deleted, these assets survive in the GitHub repo. Before deletion:
1. Extract `shared/stats.py` → Matilda's workspace utils
2. Extract `tools/tripletex-mcp/server.py` → template for Fiken MCP
3. Extract `templates/` folder → agent setup templates
4. Everything else accessible via `gh repo clone KreativKI/nmiai-2026-main` when needed
