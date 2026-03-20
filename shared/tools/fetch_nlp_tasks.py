#!/usr/bin/env python3
"""
NM i AI 2026 -- Tripletex Per-Task Score Scraper (shared/tools/fetch_nlp_tasks.py)

Opens the Tripletex submission page using saved auth cookies and scrapes:
- Total Score, Rank, Tasks Solved, Submissions count
- All entries from the "Recent Results" section with task details
- Groups by total_checks to approximate unique task types
- Tracks best score per unique task type

Output: agent-ops/dashboard/public/data/nlp_task_scores.json

Usage:
    python3 shared/tools/fetch_nlp_tasks.py              # Headless scrape
    python3 shared/tools/fetch_nlp_tasks.py --headed      # Visible browser for debugging
    python3 shared/tools/fetch_nlp_tasks.py --debug       # Dump raw page text for inspection

Dependencies: playwright (sync API)
Auth: Playwright storage state at /Volumes/devdrive/github_dev/NM_I_AI_dash/.auth/state.json
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("ERROR: playwright required. Install: pip install playwright && playwright install chromium")
    sys.exit(1)

# Paths
AUTH_STATE = Path("/Volumes/devdrive/github_dev/NM_I_AI_dash/.auth/state.json")
SUBMIT_URL = "https://app.ainm.no/submit/tripletex"

# Output path (resolve relative to repo root)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT = REPO_ROOT / "agent-ops" / "dashboard" / "public" / "data" / "nlp_task_scores.json"


def parse_summary_stats(text: str) -> dict:
    """Parse the summary stats block at the top of the page.

    Expected patterns in the page text:
        Total Score
        17.7
        sum of best per task
        Rank
        #110
        of 289 teams
        Tasks Solved
        15/30
        unique tasks scored
        Submissions
        37
        total attempts
    Also looks for daily submission counter like "37 / 180 daily submissions used"
    """
    stats = {
        "total_score": None,
        "rank": None,
        "rank_of": None,
        "tasks_solved": None,
        "submissions_total": None,
        "daily_used": None,
        "daily_limit": None,
    }

    # Total Score: number after "Total Score" line
    m = re.search(r"Total\s+Score\s*\n\s*([\d.]+)", text)
    if m:
        stats["total_score"] = float(m.group(1))

    # Rank: #N
    m = re.search(r"Rank\s*\n\s*#(\d+)", text)
    if m:
        stats["rank"] = int(m.group(1))

    # Rank of: "of N teams"
    m = re.search(r"of\s+(\d+)\s+teams", text)
    if m:
        stats["rank_of"] = int(m.group(1))

    # Tasks Solved: "X/30"
    m = re.search(r"Tasks\s+Solved\s*\n\s*(\d+/\d+)", text)
    if m:
        stats["tasks_solved"] = m.group(1)

    # Submissions: total number
    m = re.search(r"Submissions\s*\n\s*(\d+)\s*\n\s*total\s+attempts", text)
    if m:
        stats["submissions_total"] = int(m.group(1))

    # Daily submission counter: "X / Y daily submissions used"
    m = re.search(r"(\d+)\s*/\s*(\d+)\s+daily\s+submissions?\s+used", text)
    if m:
        stats["daily_used"] = int(m.group(1))
        stats["daily_limit"] = int(m.group(2))

    return stats


def parse_recent_results(text: str) -> list[dict]:
    """Parse the Recent Results section.

    Each result entry looks like:
        Task (6/8)
        08:41 PM . 40.1s
        2/8 (25%)

    Or variants. The key patterns:
    - Header: "Task (X/Y)" where X is the task-specific param, Y is total checks
    - Timing line: time and duration
    - Score line: "A/B (C%)" where A=checks_passed, B=total_checks, C=percentage
    """
    results = []

    # Find the "Recent Results" section
    recent_idx = text.find("Recent Results")
    if recent_idx == -1:
        # Try alternate names
        recent_idx = text.find("Recent Submissions")
    if recent_idx == -1:
        recent_idx = text.find("Submission History")
    if recent_idx == -1:
        # Fall back to scanning the whole text
        recent_idx = 0

    section_text = text[recent_idx:]

    # Strategy: find all score patterns "X/Y (Z%)" and work backwards to find task headers
    # This is more robust than trying to parse the exact layout
    score_pattern = re.compile(r"(\d+)/(\d+)\s*\((\d+(?:\.\d+)?)%\)")
    task_header_pattern = re.compile(r"Task\s*\((\d+)/(\d+)\)")
    time_pattern = re.compile(r"(\d{1,2}:\d{2}\s*(?:AM|PM))\s*[.·]\s*([\d.]+)s")

    # Find all score matches in the section
    score_matches = list(score_pattern.finditer(section_text))

    for score_match in score_matches:
        entry = {
            "checks_passed": int(score_match.group(1)),
            "total_checks": int(score_match.group(2)),
            "percentage": float(score_match.group(3)),
            "task_header": None,
            "time": None,
            "duration_s": None,
        }

        # Look backwards from this score match for the task header and timing
        preceding = section_text[max(0, score_match.start() - 200):score_match.start()]

        # Find the closest task header before this score
        task_matches = list(task_header_pattern.finditer(preceding))
        if task_matches:
            last_task = task_matches[-1]
            entry["task_header"] = f"Task ({last_task.group(1)}/{last_task.group(2)})"

        # Find timing info
        time_matches = list(time_pattern.finditer(preceding))
        if time_matches:
            last_time = time_matches[-1]
            entry["time"] = last_time.group(1).strip()
            try:
                entry["duration_s"] = float(last_time.group(2))
            except ValueError:
                pass

        results.append(entry)

    return results


def group_by_task_type(results: list[dict]) -> list[dict]:
    """Group results by total_checks to approximate unique task types.

    Since the page only shows "Task" (no specific names), we use total_checks
    as a proxy for task type identity.
    """
    groups = {}

    for r in results:
        tc = r["total_checks"]
        key = f"task_{tc}checks"

        if key not in groups:
            groups[key] = {
                "task_type": key,
                "total_checks": tc,
                "best_checks": 0,
                "best_percentage": 0.0,
                "attempts": 0,
                "all_scores": [],
            }

        groups[key]["attempts"] += 1
        groups[key]["all_scores"].append(r["checks_passed"])

        if r["checks_passed"] > groups[key]["best_checks"]:
            groups[key]["best_checks"] = r["checks_passed"]
            groups[key]["best_percentage"] = r["percentage"]

    # Convert to sorted list (best percentage descending)
    task_list = []
    for g in sorted(groups.values(), key=lambda x: x["best_percentage"], reverse=True):
        task_list.append({
            "task_type": g["task_type"],
            "best_checks": g["best_checks"],
            "total_checks": g["total_checks"],
            "best_percentage": g["best_percentage"],
            "attempts": g["attempts"],
        })

    return task_list


def scrape(headed: bool = False, debug: bool = False) -> dict:
    """Scrape the Tripletex submission page for per-task scores."""
    if not AUTH_STATE.exists():
        print(f"ERROR: Auth state not found at {AUTH_STATE}")
        print("Run the NLP auto-submitter with --login first to authenticate.")
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        context = browser.new_context(storage_state=str(AUTH_STATE))
        page = context.new_page()

        print(f"Loading {SUBMIT_URL}...")
        try:
            page.goto(SUBMIT_URL, wait_until="networkidle", timeout=30000)
        except PlaywrightTimeout:
            print("WARNING: Page load timed out at 30s, proceeding with partial content...")

        # Wait for content to render
        try:
            page.wait_for_selector("text=Total Score", timeout=10000)
        except PlaywrightTimeout:
            # Check if we got redirected to sign-in
            body_text = page.inner_text("body")
            if "Sign in" in body_text or "Missing token" in body_text:
                print("ERROR: Auth expired. Re-run with --login on the NLP auto-submitter to refresh cookies.")
                browser.close()
                sys.exit(1)
            print("WARNING: 'Total Score' not found on page. Attempting to parse anyway...")

        # Grab full page text
        body_text = page.inner_text("body")

        if debug:
            debug_path = REPO_ROOT / "shared" / "tools" / "nlp_page_dump.txt"
            debug_path.write_text(body_text)
            print(f"DEBUG: Page text saved to {debug_path}")
            print(f"DEBUG: Page text length: {len(body_text)} chars")
            print("DEBUG: First 2000 chars:")
            print(body_text[:2000])
            print("---")

        # Try scrolling to load more results if the page uses lazy loading
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1000)
            body_text_scrolled = page.inner_text("body")
            if len(body_text_scrolled) > len(body_text):
                body_text = body_text_scrolled
                print("  (scrolled to load more results)")
        except Exception:
            pass

        browser.close()

    # Parse
    stats = parse_summary_stats(body_text)
    results = parse_recent_results(body_text)
    tasks = group_by_task_type(results)

    return {
        "total_score": stats["total_score"],
        "tasks_solved": stats["tasks_solved"],
        "rank": stats["rank"],
        "rank_of": stats["rank_of"],
        "submissions_total": stats["submissions_total"],
        "daily_used": stats["daily_used"],
        "daily_limit": stats["daily_limit"],
        "tasks": tasks,
        "recent_results": results,
        "last_fetched": datetime.now(timezone.utc).isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(description="Scrape Tripletex per-task scores for dashboard")
    parser.add_argument("--headed", action="store_true", help="Show browser window for debugging")
    parser.add_argument("--debug", action="store_true", help="Dump raw page text for inspection")
    parser.add_argument("--output", help="Override output path")
    parser.add_argument("--stdout", action="store_true", help="Print JSON to stdout instead of saving")
    args = parser.parse_args()

    output_path = Path(args.output) if args.output else OUTPUT

    print("NLP Task Score Scraper")
    print(f"  Auth: {AUTH_STATE}")
    print(f"  Output: {output_path}")
    print()

    data = scrape(headed=args.headed, debug=args.debug)

    if args.stdout:
        print(json.dumps(data, indent=2))
        return

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    # Summary
    print(f"\nResults:")
    print(f"  Total Score: {data['total_score']}")
    print(f"  Tasks Solved: {data['tasks_solved']}")
    print(f"  Rank: #{data['rank']} of {data['rank_of']} teams")
    print(f"  Submissions: {data['submissions_total']} total")
    if data["daily_used"] is not None:
        print(f"  Daily: {data['daily_used']}/{data['daily_limit']} used")

    print(f"\n  Per-task breakdown ({len(data['tasks'])} unique task types from {len(data['recent_results'])} recent results):")
    for t in data["tasks"]:
        bar = "+" * t["best_checks"] + "-" * (t["total_checks"] - t["best_checks"])
        print(f"    {t['task_type']:>16s}  [{bar}] {t['best_checks']}/{t['total_checks']} ({t['best_percentage']}%) x{t['attempts']}")

    print(f"\n  Saved to {output_path}")


if __name__ == "__main__":
    main()
