# PRD: Tripletex MCP Bridge

## Objective
Provide an MCP interface to the Tripletex API 2.0 (OpenAPI/Swagger) for the NM i AI Hackathon without overwhelming the LLM context with hundreds of endpoints.

## Core Features
1. `tripletex_search_endpoints`: Search the local `swagger.json` file for endpoints matching a query (e.g., "invoice", "receipt", "customer") and return their required parameters and methods.
2. `tripletex_call_api`: Generic HTTP client that authenticates via a Bearer token (from secrets) and calls a specified Tripletex endpoint, returning the JSON response.

## Tech Stack
- Python 3
- FastMCP (`from mcp.server.fastmcp import FastMCP`)
- `httpx` for API calls
- `json` for parsing the downloaded `swagger.json`

## Testing
Test by searching for "employee" endpoints and retrieving the list.