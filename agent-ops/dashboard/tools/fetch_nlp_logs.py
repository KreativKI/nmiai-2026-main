#!/usr/bin/env python3
"""
Fetch Tripletex bot task logs from Cloud Run and save as dashboard JSON.
Run manually: python3 tools/fetch_nlp_logs.py
Output: public/data/nlp_task_log.json
"""

import json
import subprocess
import re
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
OUTPUT = WORKSPACE / "public" / "data" / "nlp_task_log.json"
PROJECT = "ai-nm26osl-1779"
SERVICE = "tripletex-agent"


def fetch_logs():
    """Pull Cloud Run logs via gcloud."""
    cmd = [
        "gcloud", "logging", "read",
        f'resource.type="cloud_run_revision" AND resource.labels.service_name="{SERVICE}" '
        f'AND (textPayload:"Agent result:" OR textPayload:"Agent completed:" OR textPayload:"Received /solve")',
        f"--project={PROJECT}",
        "--limit=200",
        "--format=value(textPayload,timestamp)",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print(f"gcloud error: {result.stderr}")
        return []
    return result.stdout.strip().split("\n")


def parse_logs(lines):
    """Parse Cloud Run log lines into structured task records."""
    tasks = []
    # Group lines by timestamp proximity (within 1s = same request)
    current = {}

    for line in lines:
        if not line.strip():
            continue

        # Parse "Agent result: status=completed, api_calls=2, errors_4xx=0, elapsed=6.3s"
        result_match = re.search(
            r"Agent result: status=(\w+), api_calls=(\d+), errors_4xx=(\d+), elapsed=([\d.]+)s",
            line,
        )
        if result_match:
            current["status"] = result_match.group(1)
            current["api_calls"] = int(result_match.group(2))
            current["errors_4xx"] = int(result_match.group(3))
            current["elapsed_s"] = float(result_match.group(4))

        # Parse "Agent completed: Le client Lumière SARL a été créé avec succès."
        completed_match = re.search(r"Agent completed: (.+)", line)
        if completed_match:
            current["summary"] = completed_match.group(1)

        # Parse "Received /solve" with task info
        solve_match = re.search(r"Received /solve.*prompt=(\d+)", line)
        if solve_match:
            current["prompt_length"] = int(solve_match.group(1))

        # Extract timestamp
        ts_match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
        if ts_match:
            current["timestamp"] = ts_match.group(1)

        # If we have a complete result, save it
        if "status" in current and "timestamp" in current:
            tasks.append(dict(current))
            current = {}

    return tasks


def main():
    print("Fetching Cloud Run logs...")
    lines = fetch_logs()
    print(f"Got {len(lines)} log lines")

    tasks = parse_logs(lines)
    print(f"Parsed {len(tasks)} task executions")

    # Load existing
    existing = []
    if OUTPUT.exists():
        try:
            existing = json.loads(OUTPUT.read_text())
        except (json.JSONDecodeError, ValueError):
            existing = []

    # Merge: deduplicate by timestamp
    seen_ts = {t.get("timestamp") for t in existing}
    for task in tasks:
        if task.get("timestamp") not in seen_ts:
            existing.append(task)

    # Sort by timestamp
    existing.sort(key=lambda t: t.get("timestamp", ""))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
    print(f"Saved {len(existing)} total tasks to {OUTPUT}")

    # Summary
    completed = sum(1 for t in existing if t.get("status") == "completed")
    total_calls = sum(t.get("api_calls", 0) for t in existing)
    total_errors = sum(t.get("errors_4xx", 0) for t in existing)
    print(f"\nSummary: {completed}/{len(existing)} completed, {total_calls} API calls, {total_errors} errors")


if __name__ == "__main__":
    main()
