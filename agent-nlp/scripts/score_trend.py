#!/usr/bin/env python3
"""Score trend analysis: groups submissions by batch, shows improvement over time."""
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

LOG_FILE = Path(__file__).parent.parent.parent / "shared/tools/nlp_submission_log.json"
BATCH_WINDOW_MINUTES = 30

def load_log():
    if LOG_FILE.exists():
        return json.loads(LOG_FILE.read_text())
    return []

def main():
    log = load_log()
    scored = [e for e in log if e.get("score") is not None]
    if not scored:
        print("No scored submissions found.")
        return

    # Group by batch (30-min windows)
    batches = defaultdict(list)
    for e in scored:
        ts = e.get("timestamp", "")
        try:
            dt = datetime.fromisoformat(ts)
            batch_key = dt.strftime("%Y-%m-%d %H:") + ("00" if dt.minute < 30 else "30")
            batches[batch_key].append(e)
        except (ValueError, TypeError):
            pass

    # Print trend
    prev_avg = None
    print(f"{'Batch':<20s} {'Runs':>5s} {'Avg':>6s} {'Min':>6s} {'Max':>6s} {'0%':>4s} {'100%':>5s} {'Trend':>8s}")
    print("-" * 70)

    for batch_key in sorted(batches):
        entries = batches[batch_key]
        scores = [e["score"] for e in entries]
        avg = sum(scores) / len(scores)
        zeros = sum(1 for s in scores if s == 0.0)
        perfects = sum(1 for s in scores if s == 1.0)
        trend = ""
        if prev_avg is not None:
            delta = avg - prev_avg
            if delta > 0.02:
                trend = f"+{delta:.0%}"
            elif delta < -0.02:
                trend = f"{delta:.0%}"
            else:
                trend = "="
        prev_avg = avg

        print(f"{batch_key:<20s} {len(scores):>5d} {avg:>6.1%} {min(scores):>6.1%} {max(scores):>6.1%} {zeros:>4d} {perfects:>5d} {trend:>8s}")

    # Overall stats
    all_scores = [e["score"] for e in scored]
    print("-" * 70)
    print(f"{'TOTAL':<20s} {len(all_scores):>5d} {sum(all_scores)/len(all_scores):>6.1%} {min(all_scores):>6.1%} {max(all_scores):>6.1%}")

    # Check count distribution
    print(f"\nScore distribution by check count:")
    by_checks = defaultdict(list)
    for e in scored:
        by_checks[e.get("total_checks", "?")].append(e["score"])
    for tc in sorted(by_checks):
        scores = by_checks[tc]
        avg = sum(scores) / len(scores)
        zeros = sum(1 for s in scores if s == 0.0)
        print(f"  {tc:>3} checks: {len(scores):>4d} runs  avg={avg:.1%}  zeros={zeros}")

if __name__ == "__main__":
    main()
