# NM i AI Docs Snapshot — 2026-03-20 00:00 CET

**Source:** https://app.ainm.no/docs + /tasks + /rules
**Fetched:** 2026-03-20 ~00:00 CET (T+6h into competition)
**Delta vs previous snapshot (2026-03-19T2024):** See CHANGES section below

## CHANGES since last snapshot

### New detail: Tripletex /solve endpoint spec
Full request body now documented:
```json
{
  "task_prompt": "Norwegian accounting task description",
  "task_type": "create_employee|create_customer|create_invoice|...",
  "attachments": [{"filename": "...", "data": "base64..."}],
  "base_url": "https://...",
  "session_token": "..."
}
```
- Auth: Basic Auth, username "0", password = session_token
- Return: `{"status": "completed"}` with HTTP 200

### New detail: Tier multipliers confirmed
- Tier 1 (foundational): 1.0x
- Tier 2 (multi-step): 2.0x — opens early Friday
- Tier 3 (complex): 3.0x — opens early Saturday

### New detail: Efficiency bonus formula
- Only applies to perfect correctness submissions
- Fewer API calls = higher bonus
- 4xx errors reduce bonus
- Bonus can up to 2x the tier score

### New detail: Astar Island terrain classes
- 0 = Empty (also Ocean, Plains)
- 1 = Settlement
- 2 = Port
- 3 = Ruin
- 4 = Forest
- 5 = Mountain (static)

### New detail: Astar Island world dynamics
5 annual phases: Growth → Conflict → Trade → Winter → Environment
- Mountains static, ocean static
- Forests mostly static
- Settlements grow, can collapse to ruins
- Ports develop from settlements near water

### New detail: Astar Island scoring formula
Score = 100 × exp(-KL_divergence)
- Only dynamic cells (changing between runs) contribute
- Weighted by entropy (higher entropy = more weight)
- CRITICAL: Never probability 0.0. Floor at 0.01, renormalize.

### New detail: NorgesGruppen weight limits
- Max 420 MB total weights
- Max 3 weight files
- Max 10 .py files
- FP16 quantization recommended

### Possible discrepancy: NorgesGruppen timeout
- Tasks page says 360s
- Docs page mentions 300s
- Use 300s as the safe limit

### No changes to rules
Rules page content matches previous snapshot. No new rule additions.

### All 3 tasks remain OPEN
No status changes on /tasks page.

---

## Full Task Summary (current as of this snapshot)

### Tripletex (NLP track)
- HTTPS endpoint, POST /solve
- 30 task types, 56 variants (7 languages × 8 datasets)
- Score range: 0.0–6.0 (with tier multipliers + efficiency bonus)
- Timeout: 300s
- Tier 1 now, Tier 2 Friday, Tier 3 Saturday

### Astar Island (ML track)
- REST API predictions, 50 queries/round across 5 seeds
- 40×40 grid, 6 terrain classes, viewport max 15×15
- Metric: entropy-weighted KL divergence (0–100, higher = better)
- Score = 100 × exp(-KL_divergence)
- Rounds every ~3h, weight increases 5%/round

### NorgesGruppen Data (CV track)
- ZIP upload: run.py + weights
- 248 training images, 356 categories, COCO format
- Metric: mAP@0.5 (70% detection + 30% classification)
- Sandbox: L4 GPU, Python 3.11, no network, blocked imports
- Max 3 submissions/day, 420 MB weights, 300-360s timeout
