---
priority: HIGH
from: overseer
timestamp: 2026-03-20 15:00 CET
permanent: true (do NOT delete)
---

## Overnight Automation Rules

JC sleeps. You must NOT miss rounds. Every round missed = points lost forever.

### How to Never Miss a Round
1. When you finish submitting a round, immediately set a background bash task:
```bash
# Wait for next round (check every 2 min, timeout 4 hours)
for i in $(seq 1 120); do
  ACTIVE=$(curl -s "https://api.ainm.no/astar-island/rounds" -H "Cookie: session=$TOKEN" | python3 -c "import sys,json; rounds=json.load(sys.stdin); active=[r for r in rounds if r['status']=='active']; print(active[0]['round_number'] if active else 'none')" 2>/dev/null)
  if [ "$ACTIVE" != "none" ] && [ "$ACTIVE" != "$LAST_ROUND" ]; then
    echo "NEW_ROUND:$ACTIVE"
    break
  fi
  sleep 120
done
```
2. When the background task returns NEW_ROUND: execute your query strategy and submit.
3. Between rounds: do productive work (improve model, train CNN, analyze data).
4. Commit after every round submission.

### Every Round = More Training Data
After each round completes, fetch ground truth via analysis endpoint. Add to training set. Retrain/update models.

### What Accumulates
- Round N ground truth -> 1,600 new cell transitions
- Better transition tables -> better predictions
- CNN gets retrained with more data -> better next round

### Full Autonomy Granted
- Submit every round without asking JC
- Use queries according to best strategy from simulator
- Retrain models between rounds
- Only STOP if something breaks (API error, auth failure)
