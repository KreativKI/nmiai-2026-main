---
from: butler
timestamp: 2026-03-20 13:40 CET
---
## New Tools: batch_eval.py + oracle_sim.py

### batch_eval.py
**Location:** shared/tools/batch_eval.py
**What it does:** Scores all your predictions.json files at once, prints a ranked table.

```bash
python3 shared/tools/batch_eval.py --predictions preds_v1.json preds_v2.json preds_v3.json
```

### oracle_sim.py
**Location:** shared/tools/oracle_sim.py
**What it does:** Shows your theoretical ceiling. If detection mAP is 0.12, no amount of classification improvement will push combined past 0.12. Focus on detection first.

```bash
python3 shared/tools/oracle_sim.py cv --predictions your_predictions.json
```
