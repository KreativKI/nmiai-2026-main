---
from: butler
timestamp: 2026-03-20 06:15 CET
---
## New Tool: check_nlp_endpoint.py
**Location:** shared/tools/check_nlp_endpoint.py
**What it does:** Tests the Tripletex AI agent endpoint with sample prompts. Reports status (up/down), latency, response format compliance. Runs 2 checks: basic health ping and a create_customer test.
**How to use:** `python3 shared/tools/check_nlp_endpoint.py`
**Custom URL:** `python3 shared/tools/check_nlp_endpoint.py --url https://your-endpoint.run.app/solve`
