# Shared Tools Inventory

**READ THIS** at session start. These tools exist and are ready to use. Don't rebuild what's already here.

## QC Judges (MANDATORY before any submission)

| Tool | Command | Purpose |
|------|---------|---------|
| `cv_judge.py` | `python3 shared/tools/cv_judge.py --zip path/to/submission.zip` | Scores CV submission: 70% det mAP + 30% cls mAP. Verdict: SUBMIT/SKIP/RISKY |
| `ml_judge.py` | `python3 shared/tools/ml_judge.py --predictions path/to/preds.json` | Validates ML predictions, calculates KL divergence and predicted score |
| `qc-verify.py` | `python3 agent-nlp/scripts/qc-verify.py [endpoint]` | Tests NLP endpoint against 7 task types with field-level sandbox verification |

## Validators (quick checks)

| Tool | Command | Purpose |
|------|---------|---------|
| `validate_cv_zip.py` | `python3 shared/tools/validate_cv_zip.py path/to/submission.zip` | ZIP structure, blocked imports, weight sizes, file counts |
| `check_ml_predictions.py` | `python3 shared/tools/check_ml_predictions.py path/to/preds.json` | Tensor shape (40x40x6), floors >= 0.01, normalization |
| `check_nlp_endpoint.py` | `python3 shared/tools/check_nlp_endpoint.py` | Health check NLP Cloud Run endpoint |

## Monitoring

| Tool | Command | Purpose |
|------|---------|---------|
| `scrape_leaderboard.py` | `python3 shared/tools/scrape_leaderboard.py` | Scrape top 10 per track, store with timestamps |

## Archive Tools (adapt if needed, DO NOT use as-is)

Located in `/Volumes/devdrive/github_dev/NM_I_AI_dash/tools/`:

| Tool | What it does | Adapt for |
|------|-------------|-----------|
| `ab_compare.py` | A/B test two versions with stats | Comparing model variants (CV, ML) |
| `batch.py` | Run N experiments, collect stats | Batch evaluation across submissions |
| `oracle_sim.py` | Theoretical score ceiling calculator | Estimating max possible score per track |
| `bot_profiler.py` | Performance profiler for slow functions | Verify CV run.py stays under 300s timeout |

## Track-Specific Tools

| Tool | Location | Purpose |
|------|----------|---------|
| `check_blocked_imports.py` | `agent-cv/scripts/` | CV-specific import checker |
| `stats.py` | `shared/` | Statistics utilities |
| `tripletex-mcp server.py` | `tools/tripletex-mcp/` | Tripletex API MCP server for NLP |

## How to Request a New Tool

Write to `intelligence/for-ops-agent/TOOL-REQUEST-[name].md`. Butler checks inbox at :15 and :45.
