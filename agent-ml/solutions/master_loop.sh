#!/bin/bash
# Master Loop — Autonomous ML Pipeline for Astar Island
# Runs via cron every 15 minutes. Ensures all systems are alive and churning.
#
# What it does:
# 1. Ensures overnight_v2.py is running (restarts if crashed)
# 2. Launches improvement experiments when idle
# 3. Picks up results and triggers resubmission
# 4. Logs everything
#
# Cron entry: */15 * * * * /home/jcfrugaard/solutions/master_loop.sh >> /home/jcfrugaard/master.log 2>&1

set -e
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwMmYzM2RmYy0wYzRlLTRmMjctOTcxYS00MjY1M2RhNjQzNzQiLCJlbWFpbCI6ImpjQGtyZWF0aXZraS5ubyIsImlzX2FkbWluIjpmYWxzZSwiZXhwIjoxNzc0NTY5NTg0fQ.eYCrNZ-IWK2_dZML40dlos8tvub0mEQfB0-N1tRgr5k"
DIR="/home/jcfrugaard/solutions"
VENV="/home/jcfrugaard/ml_env/bin/activate"
LOG="/home/jcfrugaard/master.log"

ts() { date -u "+%Y-%m-%d %H:%M:%S UTC"; }

echo ""
echo "[$(ts)] ========== MASTER LOOP =========="

# Activate venv
source "$VENV"
cd "$DIR"

# 1. Is overnight_v2.py running? If not, restart.
if ! pgrep -f "overnight_v2.py" > /dev/null; then
    echo "[$(ts)] overnight_v2.py NOT running. Restarting..."
    PYTHONUNBUFFERED=1 nohup python3 overnight_v2.py --token "$TOKEN" --continuous --interval 300 >> ~/overnight_v2.log 2>&1 &
    echo "[$(ts)] overnight_v2.py restarted (PID $!)"
else
    echo "[$(ts)] overnight_v2.py alive (PID $(pgrep -f overnight_v2.py))"
fi

# 2. Count running experiments
N_EXPERIMENTS=$(pgrep -f "brain_v3.py\|weighted_model.py\|grid_search.py\|regime_model.py" | wc -l)
echo "[$(ts)] Experiments running: $N_EXPERIMENTS"

# 3. If no experiments running, launch a new batch
if [ "$N_EXPERIMENTS" -eq 0 ]; then
    echo "[$(ts)] No experiments running. Launching improvement batch..."

    # Deep Brain fitting (full, all rounds, more iterations)
    PYTHONUNBUFFERED=1 nohup python3 brain_v3.py --fit --deploy > ~/brain_fit.log 2>&1 &
    echo "[$(ts)]   Track A: brain_v3.py --fit (PID $!)"

    # Weighted model search
    PYTHONUNBUFFERED=1 nohup python3 weighted_model.py --grid-search > ~/weighted.log 2>&1 &
    echo "[$(ts)]   Track B: weighted_model.py (PID $!)"

    # Grid search
    PYTHONUNBUFFERED=1 nohup python3 grid_search.py --quick > ~/grid.log 2>&1 &
    echo "[$(ts)]   Track C: grid_search.py (PID $!)"

    # Regime model validation
    PYTHONUNBUFFERED=1 nohup python3 regime_model.py > ~/regime.log 2>&1 &
    echo "[$(ts)]   Track D: regime_model.py (PID $!)"
else
    echo "[$(ts)] Experiments still running. Not launching new batch."
fi

# 4. Check latest results
if [ -f "$DIR/data/brain_v3_params.json" ]; then
    SCORE=$(python3 -c "import json; print(json.load(open('$DIR/data/brain_v3_params.json')).get('v3_score', '?'))" 2>/dev/null)
    FITTED=$(python3 -c "import json; print(json.load(open('$DIR/data/brain_v3_params.json')).get('fitted_at', '?'))" 2>/dev/null)
    echo "[$(ts)] Brain score: $SCORE (fitted: $FITTED)"
fi

# 5. Summary
TOTAL=$(pgrep -f "python3" | grep -v networkd | grep -v unattended | wc -l)
echo "[$(ts)] Total Python processes: $TOTAL"
echo "[$(ts)] ========== END =========="
