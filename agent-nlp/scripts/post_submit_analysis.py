#!/usr/bin/env python3
"""
Post-Submission Analysis: closes the autonomous improvement loop.

Runs AFTER a submission batch. Fetches Cloud Run logs, correlates with
submission scores, identifies what to fix next.

Usage:
    python3 agent-nlp/scripts/post_submit_analysis.py
    python3 agent-nlp/scripts/post_submit_analysis.py --hours 2
    python3 agent-nlp/scripts/post_submit_analysis.py --limit 50
"""
import argparse
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

LOG_FILE = Path(__file__).parent.parent.parent / "shared/tools/nlp_submission_log.json"
BEST_SCORES_FILE = Path(__file__).parent.parent / "solutions/best_scores.json"


def fetch_logs(limit: int = 200) -> list[str]:
    """Fetch Cloud Run logs using the simple logs reader."""
    cmd = [
        "gcloud", "run", "services", "logs", "read", "tripletex-agent",
        "--region", "europe-west4",
        "--project", "ai-nm26osl-1779",
        "--limit", str(limit),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return r.stdout.strip().split("\n") if r.returncode == 0 else []
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def parse_executor_stats(lines: list[str]) -> dict:
    """Parse executor results from log lines."""
    stats = defaultdict(lambda: {
        "runs": 0, "success": 0, "total_calls": 0,
        "total_errors": 0, "details": []
    })
    for line in lines:
        m = re.search(
            r"Executor (\w+): success=(\w+), elapsed=([\d.]+)s, "
            r"total_calls=(\d+), writes=(\d+), errors_4xx=(\d+)", line
        )
        if m:
            name = m.group(1)
            s = stats[name]
            s["runs"] += 1
            if m.group(2) == "True":
                s["success"] += 1
            s["total_calls"] += int(m.group(4))
            s["total_errors"] += int(m.group(6))

        # Capture efficiency details
        d = re.search(r"Efficiency detail \[(\w+)\]: (.+)", line)
        if d:
            stats[d.group(1)]["details"].append(d.group(2))

    return dict(stats)


def parse_4xx_breakdown(lines: list[str]) -> list[dict]:
    """Find specific 4xx errors with endpoint and error message."""
    errors = []
    for line in lines:
        m = re.search(r"API (\w+) (.+?) -> (\d+): (.+)", line)
        if m and int(m.group(3)) >= 400:
            errors.append({
                "method": m.group(1),
                "path": m.group(2),
                "status": int(m.group(3)),
                "message": m.group(4)[:200],
            })
    return errors


def load_submission_scores(hours: int = 4) -> list[dict]:
    """Load recent scored submissions."""
    if not LOG_FILE.exists():
        return []
    data = json.loads(LOG_FILE.read_text())
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    return [e for e in data if e.get("timestamp", "") >= cutoff and e.get("score") is not None]


def load_best_scores() -> dict:
    """Load historical best scores per check count."""
    if BEST_SCORES_FILE.exists():
        return json.loads(BEST_SCORES_FILE.read_text())
    return {}


def save_best_scores(bests: dict):
    """Save updated best scores."""
    BEST_SCORES_FILE.parent.mkdir(parents=True, exist_ok=True)
    BEST_SCORES_FILE.write_text(json.dumps(bests, indent=2))


def check_regressions(recent: list[dict], bests: dict) -> list[str]:
    """Compare recent scores against historical bests. Return alerts."""
    alerts = []
    by_checks = defaultdict(list)
    for e in recent:
        tc = e.get("total_checks")
        if tc:
            by_checks[tc].append(e["score"])

    for tc, scores in by_checks.items():
        key = str(tc)
        best_now = max(scores)
        avg_now = sum(scores) / len(scores)
        prev_best = bests.get(key, {}).get("best", 0)

        # Update best if improved
        if best_now > prev_best:
            bests[key] = {"best": best_now, "updated": datetime.now(timezone.utc).isoformat()}

        # Alert if average dropped significantly from best
        if prev_best >= 0.8 and avg_now < prev_best * 0.5:
            alerts.append(
                f"REGRESSION: {tc}-check tasks avg {avg_now:.0%} "
                f"(was {prev_best:.0%} best). Check for broken executor."
            )
    return alerts


def main():
    parser = argparse.ArgumentParser(description="Post-submission analysis")
    parser.add_argument("--hours", type=int, default=4, help="Hours of submission history")
    parser.add_argument("--limit", type=int, default=200, help="Cloud Run log lines to fetch")
    args = parser.parse_args()

    print("=" * 60)
    print("  POST-SUBMISSION ANALYSIS")
    print("=" * 60)

    # 1. Fetch and parse Cloud Run logs
    print("\n[1] Fetching Cloud Run logs...")
    lines = fetch_logs(args.limit)
    if not lines:
        print("  ERROR: Could not fetch logs")
        return 1

    executor_stats = parse_executor_stats(lines)
    errors_4xx = parse_4xx_breakdown(lines)

    # 2. Executor performance
    print(f"\n[2] Executor Performance ({sum(s['runs'] for s in executor_stats.values())} runs)")
    print(f"{'Executor':<40s} {'Runs':>5s} {'OK%':>5s} {'Avg':>5s} {'Err':>4s}")
    print("-" * 62)
    for name in sorted(executor_stats, key=lambda x: -executor_stats[x]["total_errors"]):
        s = executor_stats[name]
        ok = s["success"] / s["runs"] * 100 if s["runs"] else 0
        avg_calls = s["total_calls"] / s["runs"] if s["runs"] else 0
        print(f"  {name:<38s} {s['runs']:>5d} {ok:>4.0f}% {avg_calls:>5.1f} {s['total_errors']:>4d}")

    # 3. 4xx error breakdown
    if errors_4xx:
        print(f"\n[3] 4xx Errors ({len(errors_4xx)} total)")
        error_counts = Counter(f"{e['method']} {e['path']} -> {e['status']}" for e in errors_4xx)
        for pattern, count in error_counts.most_common(10):
            print(f"  {count:>3d}x  {pattern}")
            # Show first error message for this pattern
            for e in errors_4xx:
                if f"{e['method']} {e['path']} -> {e['status']}" == pattern:
                    msg = e["message"][:120]
                    print(f"        {msg}")
                    break
    else:
        print("\n[3] 4xx Errors: NONE (clean run)")

    # 4. Submission scores
    recent = load_submission_scores(args.hours)
    if recent:
        print(f"\n[4] Submission Scores (last {args.hours}h, {len(recent)} scored)")
        by_checks = defaultdict(list)
        for e in recent:
            tc = e.get("total_checks")
            if tc:
                by_checks[tc].append(e["score"])

        print(f"  {'Checks':>7s} {'Runs':>5s} {'Avg':>6s} {'Best':>6s} {'Zeros':>6s}")
        print("  " + "-" * 38)
        for tc in sorted(by_checks):
            scores = by_checks[tc]
            avg = sum(scores) / len(scores)
            best = max(scores)
            zeros = sum(1 for s in scores if s == 0.0)
            print(f"  {tc:>7d} {len(scores):>5d} {avg:>6.1%} {best:>6.1%} {zeros:>6d}")
    else:
        print(f"\n[4] No scored submissions in last {args.hours}h")

    # 5. Regression check
    bests = load_best_scores()
    if recent:
        alerts = check_regressions(recent, bests)
        save_best_scores(bests)
        if alerts:
            print(f"\n[5] REGRESSION ALERTS")
            for a in alerts:
                print(f"  *** {a}")
        else:
            print(f"\n[5] Regression check: PASS (no drops detected)")

    # 6. Recommendations
    print(f"\n[6] Recommendations")
    # Find worst executors
    worst = [(name, s) for name, s in executor_stats.items() if s["total_errors"] > 0]
    worst.sort(key=lambda x: -x[1]["total_errors"])
    if worst:
        print(f"  Fix 4xx errors (most impactful):")
        for name, s in worst[:3]:
            avg_err = s["total_errors"] / s["runs"]
            print(f"    {name}: {s['total_errors']} errors in {s['runs']} runs ({avg_err:.1f}/run)")
            # Show the API calls that errored
            for detail in s["details"][:1]:
                errored = [p for p in detail.split(" | ") if "4" in p.split("->")[-1] if "->" in p]
                if errored:
                    print(f"      Failing calls: {', '.join(errored)}")
    else:
        print(f"  All executors clean (0 errors). Focus on field correctness.")

    # Find lowest scoring check counts
    if recent:
        low_scores = [(tc, scores) for tc, scores in by_checks.items()
                      if sum(scores) / len(scores) < 0.5]
        low_scores.sort(key=lambda x: sum(x[1]) / len(x[1]))
        if low_scores:
            print(f"\n  Improve correctness (lowest scoring):")
            for tc, scores in low_scores[:3]:
                avg = sum(scores) / len(scores)
                print(f"    {tc}-check tasks: {avg:.0%} avg ({len(scores)} runs)")

    print(f"\n{'=' * 60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
