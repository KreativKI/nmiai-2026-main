# Ideas Log — 2026-03-21 03:00 CET

## New Tools Proposed
1. **ML "Auto-Researcher" (ADK-style):** A script that generates hypotheses (e.g. "maybe forests have higher settlement probability"), perturbs params, and backtests in seconds. Competitor #1 has 95 experiments; we have ~10.
2. **NLP "Efficiency Analyzer":** Tool to parse Tripletex `run.log` and count 4xx errors vs 2xx writes per task. Target the 14.4 vs 31 efficiency gap.
3. **"Boris Auto-Judge":** A wrapper that runs a code-review (Boris) and blocks submissions if critical bugs (like duplicate customer creation) are found.
4. **"Leaderboard Pulse":** Scraper that updates a global `COMPETITION-PULSE.md` every 15 min so agents see their rank.

## What's Working
- Autonomous parallel training on GCP (CV).
- Communication through the `intelligence/` folder.
- Cloud Run deployment (NLP).

## What's NOT Working
- ML reporting (where is `ml-status.md`?).
- NLP submission utilization (142 slots wasted today).
- Strategic context persistence between agent "thoughts".
