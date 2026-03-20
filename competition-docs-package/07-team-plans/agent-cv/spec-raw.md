# NM i AI 2026 — Task Specs (Post-Kickoff)

**Fetched:** 2026-03-19 19:03 CET (after 18:00 kickoff)
**Source:** https://app.ainm.no/tasks + task docs

---

## Task 1: Tripletex — AI Accounting Agent
**Sponsor:** Tripletex | **Type:** HTTPS API endpoint | **Status:** OPEN

- Submit /solve endpoint; platform provisions fresh Tripletex sandbox each time
- **Timeout:** 5 minutes (300s) per submission
- **30 task types**, 56 variants per task (7 languages × 8 datasets)
- **Languages:** Norwegian, English, Spanish, Portuguese, Nynorsk, German, French
- **Score range:** 0.0 (failed) — up to 6.0 (perfect Tier 3 + best efficiency)
- **Scoring:** Field-by-field checks + efficiency bonus; best score per task kept
- Some tasks include PDF/image attachments
- Tripletex API: https://kkpqfuj-amager.tripletex.dev/v2-docs/

### Task Categories
- Employees (create, set roles, contact info)
- Customers & Products (register customers, create products)
- Invoicing (create invoices, register payments, credit notes)
- Travel Expenses (register or delete expense reports)
- Projects (create projects linked to customers)
- Corrections (delete or reverse incorrect entries)
- Departments (create, enable accounting modules)

---

## Task 2: Astar Island — Norse World Prediction
**Sponsor:** Astar | **Type:** REST API predictions | **Status:** OPEN

- **Timeout:** 60s response limit
- **Metric:** KL Divergence (0–100 scale)
- Black-box Norse civilisation simulator; 50-year simulation runs
- **50 queries per round**, shared across 5 seeds
- **Viewport:** max 15×15 cells per query (map is 40×40)
- **Output:** W×H×6 probability tensor (6 terrain classes per cell)
- Scoring: entropy-weighted KL divergence vs ground truth
- API: api.ainm.no/astar-island/

### Key Concepts
| Concept | Description |
|---------|-------------|
| Map seed | Terrain layout (fixed per seed, visible) |
| Sim seed | Random seed per run (different every query) |
| Hidden parameters | Control world behavior (same for all seeds in a round) |
| 50 queries | Budget per round, shared across 5 seeds |
| Viewport | Max 15×15 window per query |
| W×H×6 tensor | Prediction — probability of each of 6 terrain classes per cell |
| 50 years | Each sim runs 50 time steps |

---

## Task 3: NorgesGruppen Data — Object Detection
**Sponsor:** NorgesGruppen Data | **Type:** Code upload (ZIP) | **Status:** OPEN

- **Timeout:** 360s response limit
- **Metric:** mAP@0.5
- **Scoring:** 70% detection (found products?) + 30% classification (right product?)
- Runs in sandboxed Docker: **NVIDIA L4 GPU, 24 GB VRAM** (no network access)
- Upload run.py + model weights as .zip

### Training Data Available (login required to download)
1. **COCO Dataset** (NM_NGD_coco_dataset.zip, ~864 MB)
   - 248 shelf images from Norwegian grocery stores
   - ~22,700 COCO-format bounding box annotations
   - 356 product categories (category_id 0–355)
   - 4 store sections: Egg, Frokost, Knekkebrod, Varmedrikker
   - bbox format: [x, y, width, height] in pixels (COCO format)
   
2. **Product Reference Images** (NM_NGD_product_images.zip, ~60 MB)
   - 327 individual products, multi-angle photos
   - Organized by barcode: {product_code}/main.jpg, front.jpg, back.jpg, left.jpg, right.jpg, top.jpg, bottom.jpg
   - Includes metadata.json with product names + annotation counts

---

## Google Cloud (GCP) — Free Accounts Available
- Selected teams get free GCP project (no credit limits)
- Access: Gemini models, Cloud Run, Vertex AI, Gmail, Docs, NotebookLM, Google Chat
- **Requirement:** All members must be Vipps-verified before applying
- Apply from team page at app.ainm.no
- NOT required — any cloud provider works

---

## MCP Server
Connect docs to Claude Code:
```
claude mcp add --transport http nmiai https://mcp-docs.ainm.no/mcp
```

---

## Eligibility Bonus Finding
**Verified teams** get:
- Higher submission rate limits
- Confirmed Google account eligibility (GCP)
- Prize eligibility protection
