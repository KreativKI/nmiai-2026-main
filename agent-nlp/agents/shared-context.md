# Shared Context: NLP Track Agents

## Competition
- NM i AI 2026, Tripletex track (AI Accounting Agent)
- Endpoint: https://tripletex-agent-795548831221.europe-west4.run.app/solve
- Bot: agent-nlp/solutions/tripletex_bot_v4.py
- 30 task types, 7 languages, field-by-field scoring
- Best score per task retained (bad runs never lower score)
- Submission limit: 180/day (confirmed from platform)
- Resets: 01:00 CET daily
- Competition ends: Sunday 15:00 CET

## Architecture
POST /solve -> Gemini extracts {task_type, fields} -> Python executor -> Tripletex API -> {"status": "completed"}

## Current State (end of day 1)
- Score: 24.5, Rank: #107/307, Tasks solved: 18/30
- 19 task types implemented, 180 submissions used
- Rev 42 deployed

## Boris Workflow (mandatory, every code change)
```
EXPLORE: What is the current bottleneck? (read logs, check scores)
PLAN:    What change addresses this? (2-3 sentences)
CODE:    Implement the change
REVIEW:  Verify: no regressions, correct field names, valid syntax
SIMPLIFY: Remove unnecessary complexity
VALIDATE: python3 -c "import ast; ast.parse(...)" + deploy + smoke test
COMMIT:  git commit with score delta
```
No exceptions. Every change follows this loop.

## Key Files
- agent-nlp/solutions/tripletex_bot_v4.py (the bot, 19 executors)
- agent-nlp/solutions/FIELD-FIXES.md (analysis reports)
- agent-nlp/scripts/pre-submit.sh (smoke test)
- agent-nlp/scripts/qc-verify.py (QC against dev sandbox)
- shared/tools/nlp_auto_submit.py (Playwright auto-submitter, in ops worktree)
- agent-nlp/EXPERIMENTS.md (experiment log)
- agent-nlp/status.json (current state)

## GCP
- Project: ai-nm26osl-1779
- Deploy: cd agent-nlp && gcloud run deploy tripletex-agent --source . --region europe-west4 --allow-unauthenticated --memory 1Gi --timeout 300
- Logs: gcloud run services logs read tripletex-agent --region europe-west4 --project ai-nm26osl-1779 --limit 300
