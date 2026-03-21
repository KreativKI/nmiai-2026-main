#!/bin/bash
# Refresh all dashboard data in one shot
# Usage: bash agent-ops/refresh_dashboard_data.sh [--loop SECONDS]

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$REPO_ROOT/agent-ops/.venv/bin/python3"
DASH_DATA="$REPO_ROOT/agent-ops/dashboard/public/data"

refresh() {
    echo "$(date '+%H:%M:%S') Refreshing dashboard data..."

    # 1. ML data from API
    $VENV "$REPO_ROOT/shared/tools/fetch_ml_data.py" 2>/dev/null | tail -2

    # 2. NLP task scores from competition page
    $VENV "$REPO_ROOT/shared/tools/fetch_nlp_tasks.py" 2>/dev/null | tail -3

    # 3. Leaderboard from competition APIs
    $VENV "$REPO_ROOT/shared/tools/fetch_leaderboard.py" 2>/dev/null | tail -3

    # 4. Copy agent status files
    for agent in cv ml nlp; do
        cp "$REPO_ROOT/agent-$agent/status.json" "$DASH_DATA/${agent}_status.json" 2>/dev/null
    done

    # 5. Copy NLP submission log
    cp "$REPO_ROOT/shared/tools/nlp_submission_log.json" "$DASH_DATA/nlp_submissions.json" 2>/dev/null

    echo "$(date '+%H:%M:%S') Done."
}

if [ "$1" = "--loop" ] && [ -n "$2" ]; then
    echo "Refreshing every $2 seconds. Ctrl+C to stop."
    while true; do
        refresh
        echo "Next refresh in $2s..."
        sleep "$2"
    done
else
    refresh
fi
