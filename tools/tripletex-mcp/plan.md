# Plan: Tripletex MCP Bridge & SOTA Monitor

## Phase 1: Tripletex MCP Bridge
1. Download `swagger.json` from `https://tripletex.no/v2/swagger.json` and save locally.
2. Build `projects/tripletex-mcp/server.py` using FastMCP.
3. Add `@mcp.tool` `tripletex_search_endpoints(query: str)` which greps through the JSON paths and summaries.
4. Add `@mcp.tool` `tripletex_call_api(method: str, path: str, payload: dict)` which makes authenticated requests.
5. Create a `tripletex-mcp-key` stub in `~/.openclaw/.secrets/`.
6. Add the server to `~/.openclaw/openclaw.json` (mcp config).

## Phase 2: SOTA AI Monitor
1. Write `scripts/nmiai-sota-monitor.py`.
2. Query `https://huggingface.co/api/models?sort=likes&direction=-1&limit=15&filter=document-question-answering`
3. Query `time-series-forecasting`
4. Query `zero-shot-object-detection`
5. Generate a markdown report and save to `projects/sota-monitor/SOTA_REPORT.md`.

## Phase 3: Review & Deliver
- Review code against `mcp-builder` guidelines.
- Announce to JC.