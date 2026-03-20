#!/usr/bin/env python3
"""
Manually add a leaderboard snapshot from JC's observations.
JC reads the leaderboard on app.ainm.no and enters scores here.

Usage:
    python3 tools/add_leaderboard_entry.py

Prompts for team scores interactively, saves to public/data/leaderboard.json.
"""

import json
from datetime import datetime
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent.parent / "public" / "data" / "leaderboard.json"


def main():
    # Load existing
    existing = []
    if OUTPUT.exists():
        try:
            existing = json.loads(OUTPUT.read_text())
        except (json.JSONDecodeError, ValueError):
            existing = []

    print("=== Leaderboard Entry ===")
    print("Enter team scores. Leave blank to finish.\n")

    rows = []
    rank = 1
    while True:
        team = input(f"  Team #{rank} name (blank to finish): ").strip()
        if not team:
            break
        try:
            tripletex = float(input(f"    Tripletex score: ").strip() or "0")
            astar = float(input(f"    Astar Island score: ").strip() or "0")
            norgesgruppen = float(input(f"    NorgesGruppen score: ").strip() or "0")
        except ValueError:
            print("    Invalid number, skipping this team.")
            continue

        total = tripletex + astar + norgesgruppen
        rows.append({
            "rank": rank,
            "team": team,
            "tripletex": tripletex,
            "astar": astar,
            "norgesgruppen": norgesgruppen,
            "total": round(total, 2),
        })
        rank += 1

    if not rows:
        print("No entries. Nothing saved.")
        return

    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "headers": ["#", "Team", "Tripletex", "Astar", "NorgesGruppen", "Total"],
        "rows": rows,
    }

    existing.append(snapshot)
    existing = existing[-50:]  # Keep last 50

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(existing, indent=2, ensure_ascii=False))

    print(f"\nSaved snapshot #{len(existing)} with {len(rows)} teams.")
    print(f"File: {OUTPUT}")


if __name__ == "__main__":
    main()
