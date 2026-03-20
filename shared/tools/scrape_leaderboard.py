#!/usr/bin/env python3
"""
Scrape NM i AI 2026 leaderboard and save as JSON for the dashboard.
Run manually: python3 tools/scrape_leaderboard.py
Output: public/data/leaderboard.json

Requires: playwright (pip install playwright && playwright install chromium)
"""

import json
import sys
from datetime import datetime
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Install playwright: pip install playwright && playwright install chromium")
    sys.exit(1)

WORKSPACE = Path(__file__).resolve().parent.parent
OUTPUT = WORKSPACE / "public" / "data" / "leaderboard.json"
LEADERBOARD_URL = "https://app.ainm.no/leaderboard"


def scrape():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print(f"Loading {LEADERBOARD_URL}...")
        page.goto(LEADERBOARD_URL, wait_until="networkidle", timeout=30000)

        try:
            page.wait_for_selector("table", timeout=15000)
        except Exception:
            print("Timeout waiting for leaderboard table. Page may require login.")
            browser.close()
            sys.exit(1)

        # Get headers
        header_els = page.query_selector_all("thead th")
        headers = [h.inner_text().strip().replace("\n", " ") for h in header_els]

        # Get rows
        rows = []
        row_els = page.query_selector_all("tbody tr")
        for tr in row_els:
            cells = tr.query_selector_all("td")
            row_data = [c.inner_text().strip().replace("\n", " ") for c in cells]
            if row_data:
                rows.append(row_data)

        browser.close()
        return headers, rows


def to_json(headers, rows):
    """Convert scraped table to structured JSON."""
    entries = []
    for row in rows:
        entry = {}
        for i, val in enumerate(row):
            if i < len(headers):
                key = headers[i].lower().replace(" ", "_")
                # Try to parse numbers
                try:
                    entry[key] = float(val) if "." in val else int(val)
                except (ValueError, TypeError):
                    entry[key] = val
            else:
                entry[f"col_{i}"] = val
        entries.append(entry)
    return entries


def main():
    headers, rows = scrape()
    if not headers:
        print("No headers found. Leaderboard may be empty or page structure changed.")
        sys.exit(1)

    entries = to_json(headers, rows)

    # Load existing snapshots
    existing = []
    if OUTPUT.exists():
        try:
            existing = json.loads(OUTPUT.read_text())
        except (json.JSONDecodeError, ValueError):
            existing = []

    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "headers": headers,
        "rows": entries,
    }

    # Append new snapshot (keep last 50)
    if isinstance(existing, list):
        existing.append(snapshot)
        existing = existing[-50:]
    else:
        existing = [snapshot]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
    print(f"Saved to {OUTPUT}")
    print(f"Snapshot #{len(existing)} | {len(entries)} teams | {len(headers)} columns")

    # Print top 10
    print(f"\n--- Top 10 ({datetime.now().strftime('%H:%M')}) ---")
    for i, entry in enumerate(entries[:10]):
        rank = entry.get("rank", entry.get("#", i + 1))
        team = entry.get("team", entry.get("lag", "?"))
        total = entry.get("total", entry.get("sum", "?"))
        print(f"  {rank}. {team} — {total}")


if __name__ == "__main__":
    main()
