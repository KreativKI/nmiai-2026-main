#!/usr/bin/env python3
"""
Fetch all ML (Astar Island) track data from the competition API.

Produces two dashboard-ready JSON files:
  - ml_rounds.json  : round listing with scores, ranks, budget
  - ml_terrain.json : terrain grids, ground truth, predictions

Usage:
  python3 shared/tools/fetch_ml_data.py                # Fetch all data
  python3 shared/tools/fetch_ml_data.py --public-only   # Only public endpoints
  python3 shared/tools/fetch_ml_data.py --rounds-only    # Only ml_rounds.json

Requires: httpx (pip install httpx)
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed.")
    print("Install with: agent-ops/.venv/bin/pip install httpx")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DASHBOARD_DATA = REPO_ROOT / "agent-ops" / "dashboard" / "public" / "data"
AUTH_STATE_PATH = Path("/Volumes/devdrive/github_dev/NM_I_AI_dash/.auth/state.json")
VIZ_DATA_PATH = REPO_ROOT / "agent-ml" / "solutions" / "data" / "viz_data.json"

ROUNDS_OUT = DASHBOARD_DATA / "ml_rounds.json"
TERRAIN_OUT = DASHBOARD_DATA / "ml_terrain.json"

BASE_URL = "https://api.ainm.no/astar-island"
TIMEOUT = 20  # seconds per request

# How many recent rounds to include full tensors for (ground truth + predictions)
MAX_TENSOR_ROUNDS = 3


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def load_token() -> str | None:
    """Extract JWT access_token from Playwright storage state."""
    if not AUTH_STATE_PATH.exists():
        return None
    try:
        state = json.loads(AUTH_STATE_PATH.read_text())
        for cookie in state.get("cookies", []):
            if cookie.get("name") == "access_token" and "ainm.no" in cookie.get("domain", ""):
                return cookie["value"]
    except (json.JSONDecodeError, KeyError):
        pass
    return None


def auth_headers(token: str | None) -> dict:
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------
async def api_get(client: httpx.AsyncClient, path: str, headers: dict | None = None) -> dict | list | None:
    """GET request with error handling. Returns parsed JSON or None on failure."""
    url = f"{BASE_URL}{path}"
    try:
        r = await client.get(url, headers=headers or {}, timeout=TIMEOUT)
        if r.status_code == 401:
            print(f"  [AUTH] 401 for {path} (token expired or invalid)")
            return None
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        print(f"  [WARN] HTTP {e.response.status_code} for {path}")
        return None
    except httpx.RequestError as e:
        print(f"  [WARN] Request failed for {path}: {e}")
        return None


# ---------------------------------------------------------------------------
# Load existing viz_data.json for merging
# ---------------------------------------------------------------------------
def load_existing_viz_data() -> dict:
    """Load existing viz_data.json to merge ground truth we already have."""
    if not VIZ_DATA_PATH.exists():
        return {}
    try:
        return json.loads(VIZ_DATA_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


# ---------------------------------------------------------------------------
# Fetch: rounds listing
# ---------------------------------------------------------------------------
async def fetch_rounds_data(client: httpx.AsyncClient, token: str | None) -> dict:
    """Build ml_rounds.json from /rounds, /my-rounds, /budget."""
    print("[1/2] Fetching round listing...")

    # Public: all rounds
    print("  GET /rounds")
    all_rounds_raw = await api_get(client, "/rounds") or []

    # Auth: our team data per round
    my_rounds_map: dict = {}
    if token:
        print("  GET /my-rounds")
        my_rounds_raw = await api_get(client, "/my-rounds", auth_headers(token)) or []
        for mr in my_rounds_raw:
            my_rounds_map[mr["id"]] = mr

    # Auth: budget for active round
    budget_data = None
    if token:
        print("  GET /budget")
        budget_data = await api_get(client, "/budget", auth_headers(token))

    # Sort rounds by round_number descending (newest first)
    all_rounds_raw.sort(key=lambda r: r.get("round_number", 0), reverse=True)

    rounds_list = []
    active_round = None

    for rd in all_rounds_raw:
        rid = rd["id"]
        rnum = rd["round_number"]
        status = rd.get("status", "unknown")

        # Merge our team data if available
        mr = my_rounds_map.get(rid, {})

        entry = {
            "round_id": rid,
            "round_number": rnum,
            "status": status,
            "opens_at": rd.get("started_at"),
            "closes_at": rd.get("closes_at"),
            "round_weight": rd.get("round_weight"),
            "our_score": mr.get("round_score"),
            "seed_scores": mr.get("seed_scores"),
            "our_rank": mr.get("rank"),
            "total_teams": mr.get("total_teams"),
            "seeds_submitted": mr.get("seeds_submitted", 0),
            "queries_used": mr.get("queries_used"),
            "queries_total": mr.get("queries_max"),
        }
        rounds_list.append(entry)

        if status == "active":
            active_round = {
                "round_id": rid,
                "round_number": rnum,
                "closes_at": rd.get("closes_at"),
                "budget_remaining": None,
            }
            if budget_data and budget_data.get("round_id") == rid:
                used = budget_data.get("queries_used", 0)
                total = budget_data.get("queries_max", 50)
                active_round["budget_remaining"] = total - used

    result = {
        "rounds": rounds_list,
        "active_round": active_round,
        "last_fetched": datetime.now(timezone.utc).isoformat(),
    }

    print(f"  Found {len(rounds_list)} rounds, active: {active_round['round_number'] if active_round else 'none'}")
    return result


# ---------------------------------------------------------------------------
# Fetch: terrain data (grids, ground truth, predictions)
# ---------------------------------------------------------------------------
async def fetch_terrain_data(
    client: httpx.AsyncClient,
    token: str | None,
    all_rounds_raw: list[dict],
) -> dict:
    """Build ml_terrain.json from /rounds/{id}, /analysis, /my-predictions."""
    print("[2/2] Fetching terrain data...")

    # Sort by round_number ascending so we process oldest first
    sorted_rounds = sorted(all_rounds_raw, key=lambda r: r.get("round_number", 0))

    # Determine which rounds get full tensors (latest N completed rounds)
    completed = [r for r in sorted_rounds if r.get("status") != "active"]
    tensor_round_ids = set()
    for r in completed[-MAX_TENSOR_ROUNDS:]:
        tensor_round_ids.add(r["id"])

    # Load existing viz_data for merging
    existing = load_existing_viz_data()
    existing_gt_map: dict = {}  # round_number -> {seed_index -> {initial_grid, ground_truth}}
    for gt_entry in existing.get("ground_truth", []):
        rn = gt_entry.get("round_number")
        if rn is not None:
            seed_map = {}
            for i, seed in enumerate(gt_entry.get("seeds", [])):
                seed_map[i] = seed
            existing_gt_map[rn] = seed_map

    # Also check for round data in existing viz_data (e.g., round3 key)
    existing_round_initials: dict = {}  # round_number -> [seeds with grid]
    for key, val in existing.items():
        if key.startswith("round") and isinstance(val, dict) and "seeds" in val:
            rn = val.get("round_number")
            if rn is not None:
                existing_round_initials[rn] = val["seeds"]

    rounds_out: dict = {}

    for rd in sorted_rounds:
        rid = rd["id"]
        rnum = rd["round_number"]
        status = rd.get("status", "unknown")
        include_tensors = rid in tensor_round_ids

        print(f"  Round {rnum} ({status})" + (" [+tensors]" if include_tensors else ""))

        # Get initial states from round detail
        print(f"    GET /rounds/{rid}")
        detail = await api_get(client, f"/rounds/{rid}")

        seeds_out = []
        initial_states = (detail or {}).get("initial_states", [])

        for si in range(5):
            seed_entry: dict = {
                "initial_grid": None,
                "ground_truth": None,
                "our_prediction": None,
            }

            # Initial grid from API
            if si < len(initial_states):
                seed_entry["initial_grid"] = initial_states[si].get("grid")

            # For tensor rounds, fetch ground truth + predictions from API
            if include_tensors and status != "active" and token:
                print(f"    GET /analysis/{rid}/{si}")
                analysis = await api_get(client, f"/analysis/{rid}/{si}", auth_headers(token))
                if analysis:
                    seed_entry["ground_truth"] = analysis.get("ground_truth")
                    seed_entry["our_prediction"] = analysis.get("prediction")

            # Merge existing viz_data ground truth if we don't have it from API
            if seed_entry["ground_truth"] is None and rnum in existing_gt_map:
                eg = existing_gt_map[rnum].get(si)
                if eg and "ground_truth" in eg:
                    seed_entry["ground_truth"] = eg["ground_truth"]
                    print(f"    [merged] ground truth for seed {si} from viz_data.json")

            # Merge existing initial grid if missing
            if seed_entry["initial_grid"] is None and rnum in existing_gt_map:
                eg = existing_gt_map[rnum].get(si)
                if eg and "initial_grid" in eg:
                    seed_entry["initial_grid"] = eg["initial_grid"]

            if seed_entry["initial_grid"] is None and rnum in existing_round_initials:
                existing_seeds = existing_round_initials[rnum]
                if si < len(existing_seeds) and "grid" in existing_seeds[si]:
                    seed_entry["initial_grid"] = existing_seeds[si]["grid"]

            # For non-tensor rounds, strip heavy data to keep file small
            if not include_tensors:
                seed_entry["ground_truth"] = None
                seed_entry["our_prediction"] = None

            seeds_out.append(seed_entry)

        rounds_out[f"round_{rnum}"] = {
            "round_number": rnum,
            "status": status,
            "seeds": seeds_out,
        }

    result = {
        "rounds": rounds_out,
        "tensor_rounds": [f"round_{r.get('round_number')}" for r in completed[-MAX_TENSOR_ROUNDS:]],
        "last_fetched": datetime.now(timezone.utc).isoformat(),
    }

    total_rounds = len(rounds_out)
    tensor_count = len([k for k, v in rounds_out.items() if any(s.get("ground_truth") for s in v["seeds"])])
    print(f"  {total_rounds} rounds total, {tensor_count} with ground truth tensors")
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main():
    parser = argparse.ArgumentParser(description="Fetch ML (Astar Island) track data")
    parser.add_argument("--public-only", action="store_true", help="Only fetch public endpoints (no auth)")
    parser.add_argument("--rounds-only", action="store_true", help="Only produce ml_rounds.json (fast)")
    args = parser.parse_args()

    # Ensure output directory exists
    DASHBOARD_DATA.mkdir(parents=True, exist_ok=True)

    # Load auth
    token = None
    if not args.public_only:
        token = load_token()
        if token:
            print(f"Auth: loaded token from {AUTH_STATE_PATH.name}")
        else:
            print("Auth: no token found, fetching public data only")
    else:
        print("Auth: skipped (--public-only)")

    async with httpx.AsyncClient() as client:
        # Always fetch rounds listing
        rounds_data = await fetch_rounds_data(client, token)

        # Write ml_rounds.json
        ROUNDS_OUT.write_text(json.dumps(rounds_data, indent=2))
        print(f"Wrote {ROUNDS_OUT}")

        if args.rounds_only:
            print("Done (--rounds-only)")
            return

        # Fetch round list again for terrain data (need full list with IDs)
        all_rounds_raw = await api_get(client, "/rounds") or []

        terrain_data = await fetch_terrain_data(client, token, all_rounds_raw)

        # Write ml_terrain.json
        TERRAIN_OUT.write_text(json.dumps(terrain_data))  # No indent, file is large
        terrain_size = TERRAIN_OUT.stat().st_size
        print(f"Wrote {TERRAIN_OUT} ({terrain_size / 1024:.0f} KB)")

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
