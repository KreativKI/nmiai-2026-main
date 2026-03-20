---
from: butler
timestamp: 2026-03-20 13:40 CET
---
## New Tool: oracle_sim.py
**Location:** shared/tools/oracle_sim.py
**What it does:** Shows how far your predictions are from perfect. Uniform baseline is ~0.5/100. Tells you your headroom and whether more effort is worthwhile.

```bash
# With ground truth
python3 shared/tools/oracle_sim.py ml --predictions preds.json --ground-truth gt.json

# Without ground truth (just baseline calculation)
python3 shared/tools/oracle_sim.py ml --predictions preds.json
```
