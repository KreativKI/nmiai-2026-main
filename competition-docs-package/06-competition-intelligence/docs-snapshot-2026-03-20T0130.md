# NM i AI Docs Snapshot — 2026-03-20 01:30 CET

**Source:** https://app.ainm.no/docs + /tasks + /rules
**Fetched:** 2026-03-20 ~01:30 CET (T+7.5h into competition)
**Delta vs previous snapshot (2026-03-20T0000):** See CHANGES section below

## CHANGES since last snapshot

### CHANGE 1: NorgesGruppen submissions increased from 3 to 5 per day
- **Previous:** "Max 3 submissions/day"
- **Current:** "Max 5 submissions/day (reset at midnight UTC)"
- Infrastructure errors don't count against limit (up to 2/day)
- **Impact:** More submission slots. Update CV rules.md.

### CHANGE 2: run.py CLI arguments confirmed
- **Command:** `python run.py --images /data/images/ --output /tmp/predictions.json`
- **Previous assumption:** `--input` flag, output to `/output/`
- **Actual:** `--images` flag, output to `/tmp/predictions.json`
- **Impact:** CRITICAL. Wrong argument = broken submission. Update CV CLAUDE.md, plan.md, rules.md.

### CHANGE 3: Three new blocked imports
- **Added:** `urllib`, `http.client`, `gc`
- **Previous list did not include these three modules.**
- **Impact:** Check all .py files for urllib, http.client, gc usage.

### No changes to rules page
Rules page still shows "Last Updated: March 17, 2026". No amendments.

### All 3 tasks remain OPEN
No status changes on /tasks page.

---

## Full Task Summary (current as of this snapshot)

### Tripletex (NLP track)
- HTTPS endpoint, POST /solve
- 30 task types, 56 variants (7 languages x 8 datasets)
- Score range: 0.0-6.0 (with tier multipliers + efficiency bonus)
- Timeout: 300s
- Tier 1 now, Tier 2 Friday, Tier 3 Saturday

### Astar Island (ML track)
- REST API predictions, 50 queries/round across 5 seeds
- 40x40 grid, 6 terrain classes, viewport max 15x15
- Metric: entropy-weighted KL divergence (0-100, higher = better)
- Score = 100 x exp(-KL_divergence)
- Rounds every ~3h, weight increases 5%/round

### NorgesGruppen Data (CV track)
- ZIP upload: run.py + weights
- 248 training images, 357 categories (IDs 0-356), COCO format
- Metric: mAP@0.5 (70% detection + 30% classification)
- Sandbox: L4 GPU, Python 3.11, no network, 22 blocked import modules
- Max 5 submissions/day, 420 MB weights, 300-360s timeout
- CLI: `python run.py --images /data/images/ --output /tmp/predictions.json`
