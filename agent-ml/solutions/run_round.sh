#!/bin/bash
# Run complete v6 phased pipeline for a round
# Usage: ./run_round.sh [--dry-run]

set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate

TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwMmYzM2RmYy0wYzRlLTRmMjctOTcxYS00MjY1M2RhNjQzNzQiLCJlbWFpbCI6ImpjQGtyZWF0aXZraS5ubyIsImlzX2FkbWluIjpmYWxzZSwiZXhwIjoxNzc0NTY5NTg0fQ.eYCrNZ-IWK2_dZML40dlos8tvub0mEQfB0-N1tRgr5k"

echo "=== Phase 1: Overview ==="
python3 solutions/astar_v6.py --token "$TOKEN" --phase overview

echo ""
echo "=== Phase 2: Analyze ==="
python3 solutions/astar_v6.py --token "$TOKEN" --phase analyze

echo ""
echo "=== Phase 3: Stack ==="
python3 solutions/astar_v6.py --token "$TOKEN" --phase stack --max-stack 24

echo ""
echo "=== Phase 4: Secondary ==="
python3 solutions/astar_v6.py --token "$TOKEN" --phase secondary --max-secondary 17

echo ""
echo "=== Phase 5: Submit ==="
if [ "$1" = "--dry-run" ]; then
    python3 solutions/astar_v6.py --token "$TOKEN" --phase submit --dry-run
else
    python3 solutions/astar_v6.py --token "$TOKEN" --phase submit
fi

echo ""
echo "=== Done ==="
