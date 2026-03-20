#!/usr/bin/env python3
"""
MCP Server for Tripletex API v2.

Provides two dynamic tools:
  1. tripletex_search_endpoints — search the local swagger.json for endpoints
  2. tripletex_call_api — make authenticated HTTP requests to the Tripletex API

This avoids registering 490+ individual tools by letting the LLM discover
endpoints on demand and call them generically.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SWAGGER_PATH = Path(__file__).parent / "swagger.json"
SECRETS_PATH = Path.home() / ".openclaw" / ".secrets" / "tripletex-mcp-key"
API_BASE_URL = "https://tripletex.no/v2"

# ---------------------------------------------------------------------------
# Swagger index (built once at import time)
# ---------------------------------------------------------------------------

def _build_index(swagger_path: Path) -> List[Dict[str, Any]]:
    """Parse swagger.json into a flat list of searchable endpoint records."""
    with open(swagger_path, "r") as f:
        spec = json.load(f)

    entries: List[Dict[str, Any]] = []
    for path, methods in spec.get("paths", {}).items():
        for method, details in methods.items():
            if method in ("get", "post", "put", "delete", "patch"):
                params = []
                for p in details.get("parameters", []):
                    params.append({
                        "name": p.get("name"),
                        "in": p.get("in"),
                        "required": p.get("required", False),
                        "type": p.get("type", p.get("schema", {}).get("type", "object")),
                    })
                entries.append({
                    "method": method.upper(),
                    "path": path,
                    "summary": details.get("summary", ""),
                    "description": details.get("description", ""),
                    "tags": details.get("tags", []),
                    "parameters": params,
                })
    return entries


ENDPOINT_INDEX = _build_index(SWAGGER_PATH)

# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def _get_token() -> str:
    """Read the bearer token from the secrets file."""
    if SECRETS_PATH.exists():
        return SECRETS_PATH.read_text().strip()
    env_token = os.environ.get("TRIPLETEX_TOKEN", "")
    if env_token:
        return env_token
    raise RuntimeError(
        f"No Tripletex token found. Place it in {SECRETS_PATH} or set TRIPLETEX_TOKEN env var."
    )

# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP("tripletex_mcp")

# ---------------------------------------------------------------------------
# Tool 1: Search endpoints
# ---------------------------------------------------------------------------

class SearchEndpointsInput(BaseModel):
    """Input for searching Tripletex API endpoints."""
    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(
        ...,
        description=(
            "Search term to match against endpoint paths, summaries, descriptions, "
            "and tags. Case-insensitive. Examples: 'invoice', 'employee', 'customer'."
        ),
        min_length=1,
        max_length=200,
    )
    limit: int = Field(
        default=20,
        description="Maximum number of results to return.",
        ge=1,
        le=100,
    )

    @field_validator("query")
    @classmethod
    def clean_query(cls, v: str) -> str:
        return v.strip().lower()


@mcp.tool(
    name="tripletex_search_endpoints",
    annotations={
        "title": "Search Tripletex API Endpoints",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def tripletex_search_endpoints(params: SearchEndpointsInput) -> str:
    """Search the Tripletex OpenAPI spec for endpoints matching a query.

    Returns matching endpoints with their HTTP method, path, summary, and
    required parameters so you know exactly how to call them.

    Args:
        params: Validated search input with query string and optional limit.

    Returns:
        JSON array of matching endpoint records, or a message if none found.
    """
    q = params.query
    hits: List[Dict[str, Any]] = []

    for entry in ENDPOINT_INDEX:
        searchable = " ".join([
            entry["path"],
            entry["summary"],
            entry["description"],
            " ".join(entry["tags"]),
        ]).lower()
        if q in searchable:
            hits.append(entry)
        if len(hits) >= params.limit:
            break

    if not hits:
        return json.dumps({"message": f"No endpoints found matching '{params.query}'.", "total": 0})

    return json.dumps({"total": len(hits), "endpoints": hits}, indent=2)


# ---------------------------------------------------------------------------
# Tool 2: Call API
# ---------------------------------------------------------------------------

class CallApiInput(BaseModel):
    """Input for making a Tripletex API call."""
    model_config = ConfigDict(str_strip_whitespace=True)

    method: str = Field(
        ...,
        description="HTTP method: GET, POST, PUT, DELETE, or PATCH.",
        pattern=r"^(GET|POST|PUT|DELETE|PATCH)$",
    )
    path: str = Field(
        ...,
        description=(
            "API path relative to /v2, e.g. '/employee' or '/invoice/123'. "
            "Include path parameters already substituted."
        ),
        min_length=1,
    )
    query_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Query string parameters as key-value pairs.",
    )
    body: Optional[Dict[str, Any]] = Field(
        default=None,
        description="JSON request body for POST/PUT/PATCH requests.",
    )
    timeout: int = Field(
        default=30,
        description="Request timeout in seconds.",
        ge=5,
        le=120,
    )

    @field_validator("path")
    @classmethod
    def ensure_leading_slash(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith("/"):
            v = "/" + v
        return v


@mcp.tool(
    name="tripletex_call_api",
    annotations={
        "title": "Call Tripletex API",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def tripletex_call_api(params: CallApiInput) -> str:
    """Make an authenticated HTTP request to the Tripletex API.

    Use tripletex_search_endpoints first to discover the correct path and
    required parameters, then call this tool to execute the request.

    Args:
        params: Validated input with method, path, optional query params, and body.

    Returns:
        JSON response from the Tripletex API, or an error message.
    """
    try:
        token = _get_token()
    except RuntimeError as e:
        return json.dumps({"error": str(e)})

    url = f"{API_BASE_URL}{params.path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=params.method,
                url=url,
                headers=headers,
                params=params.query_params,
                json=params.body if params.method in ("POST", "PUT", "PATCH") else None,
                timeout=float(params.timeout),
            )
            response.raise_for_status()
            return json.dumps(response.json(), indent=2, ensure_ascii=False)
    except httpx.HTTPStatusError as e:
        return _handle_http_error(e)
    except httpx.TimeoutException:
        return json.dumps({"error": "Request timed out. Try increasing the timeout or simplifying the query."})
    except Exception as e:
        return json.dumps({"error": f"Unexpected error: {type(e).__name__}: {e}"})


def _handle_http_error(e: httpx.HTTPStatusError) -> str:
    """Format HTTP errors into actionable messages."""
    status = e.response.status_code
    try:
        detail = e.response.json()
    except Exception:
        detail = e.response.text[:500]

    messages = {
        400: "Bad request. Check your parameters against the endpoint specification.",
        401: "Authentication failed. Verify your Tripletex token is valid and not expired.",
        403: "Permission denied. Your token may lack the required scope.",
        404: "Endpoint or resource not found. Verify the path and any IDs.",
        429: "Rate limited. Wait a moment before retrying.",
    }
    hint = messages.get(status, f"API returned status {status}.")

    return json.dumps({"error": hint, "status": status, "detail": detail}, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
