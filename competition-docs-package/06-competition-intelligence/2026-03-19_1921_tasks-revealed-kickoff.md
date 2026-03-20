# NM i AI 2026 — Tasks Revealed at Kickoff

**Fetched:** 2026-03-19 19:21 CET (post-kickoff 18:00)
**Source:** https://app.ainm.no/tasks + task doc pages

---

## Task 1 — Tripletex: AI Accounting Agent

**Sponsor:** Tripletex
**Type:** HTTPS API endpoint (you submit your endpoint URL)
**Response limit:** 300s (5 minutes)
**Metric:** Score per task (rolling avg), range 0.0–6.0
**Scoring:** Field-by-field checks + efficiency bonus, best score per task kept

### How It Works
- Submit your HTTPS endpoint URL on the platform
- Platform provisions a fresh Tripletex sandbox account per submission
- Platform sends a randomly selected accounting task to your /solve endpoint
- Agent reads the prompt, optionally processes attached files (PDFs, images)
- Agent calls the Tripletex API via a proxy to complete the task
- Platform verifies result field-by-field against expected values

### Task Details
- **30 different accounting task types**
- **56 variants per task** (7 languages × 8 datasets)
- **Languages:** Norwegian, English, Spanish, Portuguese, Nynorsk, German, French
- **Tripletex API:** v2 REST via authenticated proxy

### Task Categories
- Employees: Create employees, set roles, update contact info
- Customers & Products: Register customers, create products
- Invoicing: Create invoices, register payments, issue credit notes
- Travel Expenses: Register or delete travel expense reports
- Projects: Create projects linked to customers
- Corrections: Delete or reverse incorrect entries
- Departments: Create departments, enable accounting modules

### Score Range
- 0.0 = failed
- Up to 6.0 = perfect Tier 3 + best efficiency

---

## Task 2 — Astar Island: Norse World Prediction

**Sponsor:** Astar
**Type:** REST API predictions
**Response limit:** 60s
**Metric:** Entropy-weighted KL Divergence (0–100, lower is better)

### How It Works
- Observe a black-box Norse civilisation simulator through a limited viewport
- Simulator runs procedurally generated Norse world for 50 years
- Settlements grow, factions clash, trade routes form, alliances shift, forests reclaim ruins

### Key Parameters
- **Map size:** 40×40 cells
- **Viewport:** Max 15×15 cells per query
- **Queries:** 50 total per round, shared across all 5 seeds
- **Time steps:** 50 years per simulation run
- **Prediction format:** W×H×6 probability tensor (6 terrain classes per cell)
- **API:** api.ainm.no/astar-island/
- **Seeds per round:** 5 (same map+hidden params, different stochastic runs)

### Core Challenge
- Simulation is stochastic: same parameters → different outcomes each run
- With only 50 queries across 5 seeds, must be strategic about what to observe
- Hidden parameters control the world's behavior (same for all seeds in a round)
- Map seed determines terrain layout (fixed per seed, visible to you)

### Concept Table
| Concept | Description |
|---------|-------------|
| Map seed | Determines terrain layout (fixed per seed, visible) |
| Sim seed | Random seed for each simulation run (different every query) |
| Hidden parameters | Values controlling world behavior (same for all seeds in a round) |
| 50 queries | Budget per round, shared across all 5 seeds |
| Viewport | Each query reveals max 15×15 window |
| W×H×6 tensor | Prediction: probability of each of 6 terrain classes per cell |
| 50 years | Each simulation runs for 50 time steps |

---

## Task 3 — NorgesGruppen Data: Object Detection

**Sponsor:** NorgesGruppen Data
**Type:** Code upload (ZIP file)
**Response limit:** 360s
**Metric:** mAP@0.5
**Scoring:** 70% detection (did you find products?) + 30% classification (did you identify the right product?)

### How It Works
- Download training data from competition website (login required)
- Train your object detection model locally
- Write a run.py that takes shelf images as input and outputs predictions
- Zip your code + model weights
- Platform runs your code in a sandboxed Docker container
- GPU provided: NVIDIA L4, 24 GB VRAM, NO network access during inference

### Training Data
**File 1: COCO Dataset** (NM_NGD_coco_dataset.zip, ~864 MB)
- 248 shelf images from Norwegian grocery stores
- ~22,700 COCO-format bounding box annotations
- 356 product categories (category_id 0–355)
- Images from 4 store sections: Egg, Frokost, Knekkebrod, Varmedrikker

**File 2: Product Reference Images** (NM_NGD_product_images.zip, ~60 MB)
- 327 individual products with multi-angle photos (main, front, back, left, right, top, bottom)
- Organized by barcode: {product_code}/main.jpg etc.
- Includes metadata.json with product names and annotation counts

### Annotation Format (COCO)
```json
{
  "images": [{"id": 1, "file_name": "img_00001.jpg", "width": 2000, "height": 1500}],
  "categories": [
    {"id": 0, "name": "VESTLANDSLEFSA TØRRE 10STK 360G", "supercategory": "product"},
    {"id": 356, "name": "unknown_product", "supercategory": "product"}
  ],
  "annotations": [{
    "id": 1, "image_id": 1, "category_id": 42,
    "bbox": [141, 49, 169, 152],
    "area": 25688, "iscrowd": 0,
    "product_code": "8445291513365",
    "product_name": "NESCAFE VANILLA LATTE 136G NESTLE",
    "corrected": true
  }]
}
```
Key: bbox is [x, y, width, height] in pixels (COCO format). product_code is the barcode.

---

## New: Google Cloud Partnership

**Source:** https://app.ainm.no/docs/google-cloud/overview

- Official GCP partner offering free accounts to selected teams
- @gcplab.me Google account + dedicated GCP project
- No credit limits, full access to Cloud Run, Vertex AI, Gemini models
- Also: Gmail, Google Docs, Google Chat, NotebookLM for collaboration
- Priority given to: Vipps-verified teams, active teams, younger participants
- Apply from your team page (all members must be Vipps-verified first)

---

## New: MCP Docs Server

Connect to Claude Code for AI-assisted development:
```
claude mcp add --transport http nmiai https://mcp-docs.ainm.no/mcp
```

---

## "Category X" Clarified

The RULES-DIGEST had "Category X" as a mystery prize. It is the **U23 Prize**:
- 100,000 NOK for the highest-ranking team where ALL members are under 23 at competition end (March 22, 2026)
- Combinable with placement prizes (1st/2nd/3rd)
- Not a mystery category — fully revealed in the public rules

---

*Saved by rules-monitor cron 2026-03-19 19:21 CET*
