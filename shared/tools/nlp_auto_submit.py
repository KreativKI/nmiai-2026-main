#!/usr/bin/env python3
"""
NM i AI 2026 — NLP Auto-Submitter (shared/tools/nlp_auto_submit.py)

Automates Tripletex submissions via Playwright. Fills endpoint URL,
clicks Submit, waits for result, logs score, repeats.

JC-approved. Auto-submits 75% of daily budget (225 of 300), then stops.

Usage:
    # First time: interactive login (opens browser for Google OAuth)
    python3 shared/tools/nlp_auto_submit.py --login

    # Interactive mode (default): asks before each submission
    python3 shared/tools/nlp_auto_submit.py

    # Full auto mode (no confirmation, caps at 135)
    python3 shared/tools/nlp_auto_submit.py --auto

    # Debug mode (visible browser)
    python3 shared/tools/nlp_auto_submit.py --max 3 --headed

Dependencies: playwright (pip install playwright && playwright install chromium)
"""

import argparse
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("ERROR: playwright required. Install: pip install playwright && playwright install chromium")
    raise SystemExit(1)

# Competition limits (increased 2026-03-20: 10/type, 300/day)
DAILY_BUDGET = 300
AUTO_LIMIT = 225    # 75% of 300
PER_TASK_LIMIT = 10 # 10 per task type per day (verified team)
DEFAULT_DELAY = 5

# URLs
SUBMIT_URL = "https://app.ainm.no/submit/tripletex"
SIGNIN_URL = "https://app.ainm.no/signin"
DEFAULT_ENDPOINT = "https://tripletex-agent-795548831221.europe-west4.run.app/solve"

# Auth state (shared with login.py)
AUTH_DIR = Path("/Volumes/devdrive/github_dev/NM_I_AI_dash/.auth")
AUTH_STATE = AUTH_DIR / "state.json"

# Output
LOG_FILE = "shared/tools/nlp_submission_log.json"


def find_repo_root() -> Path:
    cwd = Path.cwd()
    for p in [cwd] + list(cwd.parents):
        if (p / "CLAUDE.md").exists() or (p / "shared").exists():
            return p
    return cwd


def do_interactive_login(playwright) -> bool:
    """Open a visible browser for manual Google login. Saves cookies."""
    print("Opening browser for Google login...")
    print("  Sign in with your Google account. Browser closes automatically after login.\n")

    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto(SIGNIN_URL, wait_until="networkidle")

    # Wait for user to complete login (up to 5 minutes)
    for i in range(150):
        time.sleep(2)
        if i % 15 == 0:
            print(f"  Waiting... ({i*2}s) URL: {page.url[:80]}")

        cookies = context.cookies()
        access_token = next(
            (c["value"] for c in cookies
             if c["name"] == "access_token" and "ainm.no" in c.get("domain", "")),
            None
        )

        if access_token:
            print(f"  Login successful! (access_token: {len(access_token)} chars)")
            AUTH_DIR.mkdir(exist_ok=True)
            context.storage_state(path=str(AUTH_STATE))
            print(f"  Session saved to {AUTH_STATE}")
            browser.close()
            return True

        # Navigate to app to trigger cookie exchange after OAuth redirect
        if "ainm.no" in page.url and "/signin" not in page.url and i > 5 and i % 10 == 0:
            page.goto(SUBMIT_URL, wait_until="networkidle", timeout=10000)

    print("  Login timed out (5 minutes).")
    browser.close()
    return False


def is_authenticated(page) -> bool:
    """Check if the current page shows an authenticated state."""
    page.goto(SUBMIT_URL, wait_until="networkidle", timeout=20000)
    text = page.inner_text("body")
    # Authenticated page shows submission stats, not "Sign in" or "Missing token"
    if "Missing token" in text or "Sign in" in text.split("Dashboard")[0] if "Dashboard" in text else "Sign in" in text:
        return False
    # Check for submission form elements that only appear when logged in
    # "Total Score" with a number (not "—") indicates logged in
    if "Submissions" in text and "Submit" in text:
        return True
    return False


def submit_once(page, endpoint: str, attempt: int) -> dict:
    """Perform one submission cycle."""
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "attempt": attempt,
        "endpoint": endpoint,
        "success": False,
        "task_type": None,
        "score": None,
        "checks_passed": None,
        "total_checks": None,
        "error": None,
    }

    try:
        # Navigate to submission page
        page.goto(SUBMIT_URL, wait_until="networkidle", timeout=20000)

        # Check for auth issues
        page_text = page.inner_text("body")
        if "Missing token" in page_text:
            result["error"] = "Not authenticated (Missing token). Run with --login"
            return result

        # Find and fill endpoint URL input (type=url based on page inspection)
        endpoint_input = page.locator("input[type='url']")
        if endpoint_input.count() == 0:
            endpoint_input = page.locator("input[placeholder*='solve' i], input[placeholder*='endpoint' i], input[placeholder*='https' i]")
        if endpoint_input.count() == 0:
            result["error"] = "Could not find endpoint URL input"
            return result

        endpoint_input.first.fill("")
        endpoint_input.first.fill(endpoint)
        time.sleep(0.5)

        # Capture page text BEFORE clicking submit (to diff later)
        pre_submit_text = page.inner_text("body")

        # Find and click Submit button
        submit_btn = page.locator("button:has-text('Submit')")
        if submit_btn.count() == 0:
            result["error"] = "Could not find Submit button"
            return result

        submit_btn.first.click()

        # Wait for the page to change (new content after submission)
        # The platform sends a task to our endpoint, waits for response, scores it
        # This can take 30-120 seconds depending on task complexity
        print("waiting...", end=" ", flush=True)

        # Wait for actual result (not just loading state)
        # Page shows "Evaluating..." then "Scoring..." then the real result "X/Y (Z%)"
        # The page always shows exactly ~20 results, so count-based detection fails.
        # Instead: detect change by comparing the FIRST result (newest = top of list).
        max_wait = 180
        start = time.time()
        post_submit_text = pre_submit_text
        pre_first = re.findall(r"\d+/\d+\s*\(\d+%\)", pre_submit_text)
        pre_first_val = pre_first[0] if pre_first else None
        pre_first_time = re.findall(r"\d{2}:\d{2}\s*[AP]M\s*·\s*[\d.]+s", pre_submit_text)
        pre_first_time_val = pre_first_time[0] if pre_first_time else None

        while time.time() - start < max_wait:
            time.sleep(5)
            try:
                post_submit_text = page.inner_text("body")
            except Exception:
                continue

            # Still loading? Keep waiting.
            if "Evaluating" in post_submit_text or "Scoring" in post_submit_text:
                continue

            # Check if the first (newest) result changed
            post_first = re.findall(r"\d+/\d+\s*\(\d+%\)", post_submit_text)
            post_first_time = re.findall(r"\d{2}:\d{2}\s*[AP]M\s*·\s*[\d.]+s", post_submit_text)
            if post_first and post_first_time:
                # New result if the timestamp at the top changed
                if post_first_time[0] != pre_first_time_val:
                    break
                # Or if score changed at the same position
                if post_first[0] != pre_first_val:
                    break

        elapsed = int(time.time() - start)
        print(f"({elapsed}s)", end=" ", flush=True)

        # Parse result: page always shows ~20 results (fixed list, not growing).
        # New result appears at TOP (index 0). Compare first result pre vs post.

        post_results = re.findall(r"(\d+)/(\d+)\s*\((\d+)%\)", post_submit_text)
        pre_results_flat = re.findall(r"\d+/\d+\s*\(\d+%\)", pre_submit_text)
        post_results_flat = re.findall(r"\d+/\d+\s*\(\d+%\)", post_submit_text)

        # Detect new result: first entry in post differs from first entry in pre
        has_new = (post_results_flat and pre_results_flat
                   and post_results_flat[0] != pre_results_flat[0])
        # Also check timestamp change (handles same score, different task)
        if not has_new:
            pre_times = re.findall(r"\d{2}:\d{2}\s*[AP]M\s*·\s*[\d.]+s", pre_submit_text)
            post_times = re.findall(r"\d{2}:\d{2}\s*[AP]M\s*·\s*[\d.]+s", post_submit_text)
            has_new = (post_times and pre_times and post_times[0] != pre_times[0])

        if has_new and post_results:
            latest = post_results[0]  # First = newest (top of list)
            result["checks_passed"] = int(latest[0])
            result["total_checks"] = int(latest[1])
            result["percentage"] = int(latest[2])
            result["score"] = result["checks_passed"] / result["total_checks"] if result["total_checks"] > 0 else 0

        # Parse daily usage from full page text
        daily_match = re.search(r"(\d+)\s*/\s*(\d+)\s*daily\s*submissions", post_submit_text)
        if daily_match:
            result["daily_used"] = int(daily_match.group(1))
            result["daily_limit"] = int(daily_match.group(2))

        # Parse task name: first "Task (X/Y)" entry is the newest
        task_entries = re.findall(r"^(.+?)\s*\(\d+/\d+\)\s*$", post_submit_text, re.MULTILINE)
        pre_task_entries = re.findall(r"^(.+?)\s*\(\d+/\d+\)\s*$", pre_submit_text, re.MULTILINE)
        if task_entries and pre_task_entries:
            # First entry is newest; check if it changed
            first_task = task_entries[0].strip()
            if first_task and len(first_task) > 2:
                result["task_type"] = first_task

        # Store new lines for debugging when no result parsed
        pre_lines = set(pre_submit_text.splitlines())
        new_lines = [l.strip() for l in post_submit_text.splitlines()
                     if l.strip() not in pre_lines and l.strip()]
        if result["score"] is None and result["task_type"] is None:
            result["raw_result"] = "\n".join(new_lines)[:800]

        # Success if we parsed a score or task name
        if result["score"] is not None or result["task_type"] is not None:
            result["success"] = True
        elif post_submit_text != pre_submit_text:
            result["success"] = False
            result["error"] = "Page changed but could not parse result (check raw_result)"
        elif elapsed >= max_wait:
            result["error"] = f"Timeout waiting for result ({max_wait}s)"

    except PlaywrightTimeout as e:
        result["error"] = f"Page timeout: {e}"
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"

    return result


def load_log(log_path: Path) -> list:
    if log_path.exists():
        try:
            return json.loads(log_path.read_text())
        except (json.JSONDecodeError, ValueError):
            return []
    return []


def save_log(log_path: Path, log: list):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False))


def count_today_submissions(log: list) -> Counter:
    """Count submissions per task type since last midnight UTC."""
    now = datetime.now(timezone.utc)
    reset_today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    counts = Counter()
    for entry in log:
        ts = entry.get("timestamp", "")
        try:
            entry_time = datetime.fromisoformat(ts)
            if entry_time >= reset_today and entry.get("success"):
                task_type = entry.get("task_type", "unknown")
                counts[task_type] += 1
        except (ValueError, TypeError):
            pass
    return counts


def print_summary(log: list, today_counts: Counter, total_attempted: int):
    successes = [e for e in log if e.get("success")]
    failures = [e for e in log if not e.get("success")]

    print(f"\n{'='*55}")
    print(f"  NLP Auto-Submit Summary")
    print(f"{'='*55}")
    print(f"  Attempted:    {total_attempted}")
    print(f"  Successful:   {len(successes)}")
    print(f"  Failed:       {len(failures)}")

    if successes:
        scores = [e["score"] for e in successes if e.get("score") is not None]
        if scores:
            print(f"  Avg score:    {sum(scores)/len(scores):.2f}")
            print(f"  Best score:   {max(scores):.2f}")

    if today_counts:
        print(f"\n  Per task type today:")
        for task_type, count in sorted(today_counts.items()):
            at_limit = " (LIMIT)" if count >= PER_TASK_LIMIT else ""
            print(f"    {task_type:<30s} {count}/{PER_TASK_LIMIT}{at_limit}")

    remaining = DAILY_BUDGET - sum(today_counts.values())
    print(f"\n  Budget remaining: {remaining}/{DAILY_BUDGET}")
    print(f"{'='*55}\n")


def main():
    parser = argparse.ArgumentParser(description="NLP Auto-Submitter (Playwright)")
    parser.add_argument("--max", type=int, default=AUTO_LIMIT,
                        help=f"Max submissions (default: {AUTO_LIMIT})")
    parser.add_argument("--delay", type=int, default=DEFAULT_DELAY,
                        help=f"Seconds between submissions (default: {DEFAULT_DELAY})")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT,
                        help="NLP endpoint URL")
    parser.add_argument("--auto", action="store_true",
                        help="Full auto mode (no confirmation between submissions)")
    parser.add_argument("--headed", action="store_true",
                        help="Run browser in headed mode (visible)")
    parser.add_argument("--login", action="store_true",
                        help="Interactive login (opens browser for Google OAuth)")
    args = parser.parse_args()

    # Handle --login mode
    if args.login:
        with sync_playwright() as p:
            success = do_interactive_login(p)
            raise SystemExit(0 if success else 1)

    repo_root = find_repo_root()
    log_path = repo_root / LOG_FILE

    if not AUTH_STATE.exists():
        print(f"ERROR: No auth session found at {AUTH_STATE}")
        print(f"  Run: python3 shared/tools/nlp_auto_submit.py --login")
        raise SystemExit(1)

    # Always load existing log to enforce per-task and daily limits
    log = load_log(log_path)
    today_counts = count_today_submissions(log)

    mode = "AUTO" if args.auto else "INTERACTIVE (y/n/q before each)"
    print(f"NLP Submitter [{mode}]")
    print(f"  Endpoint: {args.endpoint}")
    print(f"  Max: {args.max}, Delay: {args.delay}s")
    if sum(today_counts.values()) > 0:
        print(f"  Already logged today: {sum(today_counts.values())}")
    print()

    if args.max > AUTO_LIMIT:
        print(f"WARNING: Capping --max to {AUTO_LIMIT}")
        args.max = AUTO_LIMIT

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        context = browser.new_context(storage_state=str(AUTH_STATE))
        page = context.new_page()

        # Verify auth with robust check
        print("Checking auth...")
        if not is_authenticated(page):
            print("ERROR: Not authenticated. Session may have expired.")
            print(f"  Run: python3 shared/tools/nlp_auto_submit.py --login")
            browser.close()
            raise SystemExit(1)
        print("  Auth OK\n")

        submitted = 0
        for i in range(args.max):
            total_today = sum(today_counts.values()) + submitted
            if total_today >= DAILY_BUDGET:
                print(f"\nDaily budget reached ({DAILY_BUDGET}). Stopping.")
                break

            # Interactive mode: ask before each submission (unless --auto)
            if not args.auto:
                remaining = DAILY_BUDGET - total_today
                try:
                    answer = input(f"[Ready] Submit #{submitted + 1}? ({remaining} remaining) (y/n/q): ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    print("\nStopped.")
                    break
                if answer == "q":
                    print("Stopped by user.")
                    break
                if answer != "y":
                    print("Skipped.")
                    continue

            print(f"[{submitted + 1}/{args.max}] ", end="", flush=True)

            result = submit_once(page, args.endpoint, submitted + 1)
            log.append(result)
            save_log(log_path, log)

            if result["success"]:
                checks = f"{result['checks_passed']}/{result['total_checks']}" if result.get("total_checks") else "?"
                pct = f"{result['percentage']}%" if result.get("percentage") is not None else ""
                task_str = result.get("task_type", "?")
                daily = f"[{result['daily_used']}/{result['daily_limit']}]" if result.get("daily_used") else ""
                print(f"OK  {checks} ({pct}) task={task_str} {daily}")
                if result.get("task_type"):
                    today_counts[result["task_type"]] += 1
            else:
                error = result.get("error", "unknown")
                print(f"FAILED: {error}")
                if "Not authenticated" in str(error):
                    print("Auth lost mid-run. Stopping.")
                    break
                if "timeout" in str(error).lower():
                    print("  Pausing 30s...")
                    time.sleep(30)

            submitted += 1

            if args.auto and i < args.max - 1:
                time.sleep(args.delay)

        browser.close()

    print_summary(log, today_counts, submitted)


if __name__ == "__main__":
    main()
