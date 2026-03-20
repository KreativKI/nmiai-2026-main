#!/usr/bin/env python3
"""
NM i AI 2026 — Live Leaderboard Fetcher (shared/tools/fetch_leaderboard.py)

Fetches live leaderboard data from competition APIs (no auth required)
and writes dashboard-compatible JSON.

Available APIs:
- Astar Island: https://api.ainm.no/astar-island/leaderboard
- Tripletex:    https://api.ainm.no/tripletex/leaderboard
- NorgesGruppen: no public API (must use Playwright or manual entry)

Usage:
    # Fetch and save to dashboard
    python3 shared/tools/fetch_leaderboard.py

    # Fetch specific track
    python3 shared/tools/fetch_leaderboard.py --track ml
    python3 shared/tools/fetch_leaderboard.py --track nlp

    # Custom output path
    python3 shared/tools/fetch_leaderboard.py --output /path/to/leaderboard.json

    # Print to stdout only
    python3 shared/tools/fetch_leaderboard.py --stdout

    # Run in loop (for live feed)
    python3 shared/tools/fetch_leaderboard.py --loop 300

Dependencies: urllib (stdlib only, no pip install needed)
"""

import argparse
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

ML_LEADERBOARD_URL = "https://api.ainm.no/astar-island/leaderboard"
NLP_LEADERBOARD_URL = "https://api.ainm.no/tripletex/leaderboard"

DEFAULT_OUTPUT = "agent-ops/dashboard/public/data/leaderboard.json"
MAX_SNAPSHOTS = 100


def fetch_json(url: str, timeout: int = 15) -> list | dict | None:
    """Fetch JSON from URL. Returns parsed data or None on error."""
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        print(f"  WARNING: Failed to fetch {url}: {e}")
        return None


def fetch_ml_leaderboard() -> list[dict]:
    """Fetch Astar Island leaderboard."""
    data = fetch_json(ML_LEADERBOARD_URL)
    if not data or not isinstance(data, list):
        return []
    return data


def fetch_nlp_leaderboard() -> list[dict]:
    """Fetch Tripletex leaderboard."""
    data = fetch_json(NLP_LEADERBOARD_URL)
    if not data or not isinstance(data, list):
        return []
    return data


def build_combined_snapshot(ml_data: list, nlp_data: list) -> dict:
    """Build a combined leaderboard snapshot compatible with the dashboard.

    The dashboard expects: {timestamp, headers, rows}
    where rows is a list of dicts with keys matching lowercase headers.
    """
    # Build team score lookup: team_name -> {ml_score, nlp_score, cv_score}
    teams = {}

    for entry in ml_data:
        name = entry.get("team_name", "?")
        if name not in teams:
            teams[name] = {"team": name, "astar_island": 0, "tripletex": 0, "norgesgruppen": 0}
        teams[name]["astar_island"] = round(entry.get("weighted_score", 0), 2)
        teams[name]["ml_rounds"] = entry.get("rounds_participated", 0)

    for entry in nlp_data:
        name = entry.get("team_name", "?")
        if name not in teams:
            teams[name] = {"team": name, "astar_island": 0, "tripletex": 0, "norgesgruppen": 0}
        teams[name]["tripletex"] = round(entry.get("weighted_score", entry.get("total_score", 0)), 2)
        teams[name]["nlp_submissions"] = entry.get("total_submissions", 0)

    # Calculate total and rank
    team_list = list(teams.values())
    for t in team_list:
        t["total"] = round(t["astar_island"] + t["tripletex"] + t["norgesgruppen"], 2)

    team_list.sort(key=lambda t: t["total"], reverse=True)

    for i, t in enumerate(team_list, 1):
        t["rank"] = i
        t["#"] = i

    headers = ["#", "Team", "Tripletex", "Astar Island", "NorgesGruppen", "Total"]

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "headers": headers,
        "rows": team_list,
        "sources": {
            "ml": len(ml_data) > 0,
            "nlp": len(nlp_data) > 0,
            "cv": False,
        },
    }


def build_track_snapshot(track: str, data: list) -> dict:
    """Build a single-track leaderboard snapshot."""
    rows = []
    for entry in data:
        row = {
            "rank": entry.get("rank", 0),
            "#": entry.get("rank", 0),
            "team": entry.get("team_name", "?"),
        }
        if track == "ml":
            row["weighted_score"] = round(entry.get("weighted_score", 0), 2)
            row["rounds"] = entry.get("rounds_participated", 0)
            row["hot_streak"] = round(entry.get("hot_streak_score", 0), 2)
            row["total"] = row["weighted_score"]
        elif track == "nlp":
            row["weighted_score"] = round(entry.get("weighted_score", entry.get("total_score", 0)), 2)
            row["submissions"] = entry.get("total_submissions", 0)
            row["tasks_touched"] = entry.get("tasks_touched", 0)
            row["total"] = row["weighted_score"]
        rows.append(row)

    track_names = {"ml": "Astar Island", "nlp": "Tripletex"}
    headers = ["#", "Team", "Score", "Total"]

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "headers": headers,
        "rows": rows,
        "track": track_names.get(track, track),
    }


def save_snapshot(output_path: Path, snapshot: dict):
    """Append snapshot to history file, keeping last MAX_SNAPSHOTS."""
    existing = []
    if output_path.exists():
        try:
            existing = json.loads(output_path.read_text())
            if not isinstance(existing, list):
                existing = [existing]
        except (json.JSONDecodeError, ValueError):
            existing = []

    existing.append(snapshot)
    existing = existing[-MAX_SNAPSHOTS:]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
    return len(existing)


def find_repo_root() -> Path:
    cwd = Path.cwd()
    for p in [cwd] + list(cwd.parents):
        if (p / "CLAUDE.md").exists() or (p / "shared").exists():
            return p
    return cwd


def run_once(args) -> dict:
    """Fetch leaderboard data once. Returns the snapshot."""
    if args.track == "ml":
        print("Fetching Astar Island leaderboard...")
        data = fetch_ml_leaderboard()
        snapshot = build_track_snapshot("ml", data)
        print(f"  {len(data)} teams")
    elif args.track == "nlp":
        print("Fetching Tripletex leaderboard...")
        data = fetch_nlp_leaderboard()
        snapshot = build_track_snapshot("nlp", data)
        print(f"  {len(data)} teams")
    else:
        print("Fetching all leaderboards...")
        ml_data = fetch_ml_leaderboard()
        print(f"  Astar Island: {len(ml_data)} teams")
        nlp_data = fetch_nlp_leaderboard()
        print(f"  Tripletex: {len(nlp_data)} teams")
        snapshot = build_combined_snapshot(ml_data, nlp_data)
        print(f"  Combined: {len(snapshot['rows'])} unique teams")

    return snapshot


def print_top10(snapshot: dict):
    """Print top 10 from snapshot."""
    rows = snapshot["rows"][:10]
    print(f"\n  Top 10 ({datetime.now().strftime('%H:%M')}):")
    for r in rows:
        rank = r.get("rank", r.get("#", "?"))
        team = r.get("team", "?")
        total = r.get("total", 0)
        print(f"    {rank:>3}. {team:<35s} {total:>8.2f}")


def main():
    parser = argparse.ArgumentParser(description="Fetch live leaderboard from competition APIs")
    parser.add_argument("--track", choices=["ml", "nlp", "all"], default="all",
                        help="Which track (default: all combined)")
    parser.add_argument("--output", help="Output JSON path")
    parser.add_argument("--stdout", action="store_true", help="Print to stdout only")
    parser.add_argument("--loop", type=int, metavar="SECONDS",
                        help="Run in loop with N second interval")
    args = parser.parse_args()

    repo_root = find_repo_root()
    output_path = Path(args.output) if args.output else repo_root / DEFAULT_OUTPUT

    if args.loop:
        print(f"Running in loop mode (every {args.loop}s). Ctrl+C to stop.")
        print(f"Output: {output_path}\n")
        while True:
            try:
                snapshot = run_once(args)
                if args.stdout:
                    print(json.dumps(snapshot, indent=2))
                else:
                    count = save_snapshot(output_path, snapshot)
                    print(f"  Saved snapshot #{count} to {output_path}")
                print_top10(snapshot)
                print(f"\n  Next fetch in {args.loop}s...")
                time.sleep(args.loop)
            except KeyboardInterrupt:
                print("\nStopped.")
                break
    else:
        snapshot = run_once(args)
        if args.stdout:
            print(json.dumps(snapshot, indent=2))
        else:
            count = save_snapshot(output_path, snapshot)
            print(f"  Saved snapshot #{count} to {output_path}")
        print_top10(snapshot)


if __name__ == "__main__":
    main()
