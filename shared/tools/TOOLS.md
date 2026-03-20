# Shared Tools Inventory

**READ THIS** at session start. These tools exist and are ready to use. Don't rebuild what's already here.

## Pre-Submission Toolchains (MANDATORY)

### CV Toolchain (run ALL in order before uploading)
```
1. python3 shared/tools/validate_cv_zip.py submission.zip
2. python3 shared/tools/cv_profiler.py submission.zip
3. python3 shared/tools/cv_judge.py --predictions-json predictions.json
4. python3 shared/tools/ab_compare.py --a prev_best.json --b new.json
```
If any step fails: do NOT submit. Fix the issue first.

### ML Toolchain
```
1. python3 shared/tools/ml_judge.py predictions.json
2. python3 shared/tools/ml_judge.py predictions.json --ground-truth gt.json
3. If validation fails: python3 shared/tools/ml_judge.py predictions.json --fix --output fixed.json
```

### NLP Toolchain
```
1. python3 shared/tools/check_nlp_endpoint.py
2. python3 agent-nlp/scripts/qc-verify.py [endpoint]
```

## QC Judges

| Tool | Command | Purpose |
|------|---------|---------|
| `cv_judge.py` | `python3 shared/tools/cv_judge.py --predictions-json preds.json` | Scores CV: 70% det mAP + 30% cls mAP. Verdict: SUBMIT/SKIP/RISKY |
| `ml_judge.py` | `python3 shared/tools/ml_judge.py preds.json` | Validates + scores ML predictions (KL divergence). Auto-fix mode. |
| `qc-verify.py` | `python3 agent-nlp/scripts/qc-verify.py [endpoint]` | Tests NLP endpoint: 7 task types with field-level sandbox verification |

## Comparison and Analysis

| Tool | Command | Purpose |
|------|---------|---------|
| `ab_compare.py` | `python3 shared/tools/ab_compare.py --a v1.json --b v2.json` | A/B compare two prediction sets with per-image breakdown |
| `batch_eval.py` | `python3 shared/tools/batch_eval.py dir_of_predictions/` | Rank multiple submissions by score |
| `oracle_sim.py` | `python3 shared/tools/oracle_sim.py --track cv` | Theoretical ceiling per track |
| `cv_profiler.py` | `python3 shared/tools/cv_profiler.py submission.zip` | Time each stage of CV inference vs 300s limit |

## Validators (quick checks)

| Tool | Command | Purpose |
|------|---------|---------|
| `validate_cv_zip.py` | `python3 shared/tools/validate_cv_zip.py submission.zip` | ZIP structure, blocked imports, weight sizes, file counts |
| `check_ml_predictions.py` | `python3 shared/tools/check_ml_predictions.py preds.json` | Tensor shape (40x40x6), floors >= 0.01, normalization |
| `check_nlp_endpoint.py` | `python3 shared/tools/check_nlp_endpoint.py` | Health check NLP Cloud Run endpoint |

## Monitoring

| Tool | Command | Purpose |
|------|---------|---------|
| `scrape_leaderboard.py` | `python3 shared/tools/scrape_leaderboard.py` | Scrape top 10 per track, store with timestamps |

## Track-Specific Tools

| Tool | Location | Purpose |
|------|----------|---------|
| `check_blocked_imports.py` | `agent-cv/scripts/` | CV-specific import checker |
| `stats.py` | `shared/` | Statistics utilities |
| `tripletex-mcp server.py` | `tools/tripletex-mcp/` | Tripletex API MCP server for NLP |

## How to Request a New Tool

Write to `intelligence/for-ops-agent/TOOL-REQUEST-[name].md`. Butler checks inbox at :15 and :45.
