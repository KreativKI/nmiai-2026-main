#!/usr/bin/env python3
"""
Efficiency Analyzer for Tripletex Bot.

Reads Cloud Run logs and the submission log to produce a per-task-type
efficiency report. Identifies unnecessary writes, 4xx errors, and
optimization targets ranked by impact.

Usage:
    python3 agent-nlp/scripts/efficiency_analyzer.py
    python3 agent-nlp/scripts/efficiency_analyzer.py --hours 6
    python3 agent-nlp/scripts/efficiency_analyzer.py --json

Requires: gcloud CLI authenticated with ADC.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
SUBMISSION_LOG = REPO_ROOT / "shared" / "tools" / "nlp_submission_log.json"
REPORT_OUTPUT = SCRIPT_DIR.parent / "solutions" / "EFFICIENCY-REPORT.md"

# Optimal write budgets per executor (from code analysis)
OPTIMAL_WRITES = {
    "create_customer": 1,
    "create_employee": 1,
    "create_employee_with_employment": 3,
    "create_product": 1,
    "create_department": 1,  # per department
    "create_project": 2,  # POST employee + POST project (if PM != admin, else 1)
    "create_invoice": 1,  # just POST /invoice (if bank already set up)
    "create_invoice_with_payment": 2,  # POST invoice + PUT payment
    "create_project_invoice": 3,  # POST employee + POST project + POST invoice
    "register_payment": 1,  # PUT payment
    "create_credit_note": 1,  # PUT credit note
    "create_travel_expense": 3,  # POST employee + POST travelExpense + POST cost(s)
    "delete_employee": 1,  # DELETE employee
    "delete_travel_expense": 1,  # DELETE travelExpense
    "update_customer": 1,  # PUT customer
    "update_employee": 1,  # PUT employee
    "create_contact": 1,  # POST contact (if customer exists, else 2)
    "enable_module": 1,  # POST department
    "process_salary": 3,  # POST employee + POST employment + POST details (min)
    "register_supplier_invoice": 2,  # POST supplier + POST voucher
    "create_dimension": 2,  # POST dimName + POST dimValue (min)
    "create_supplier": 1,  # POST supplier
}


def fetch_cloud_run_logs(hours: int = 12, limit: int = 2000) -> list[str]:
    """Fetch Cloud Run logs via gcloud CLI.

    Uses a targeted filter to only get request-relevant lines
    (SOLVE, Task type, Executor, API warnings) and skip noise.
    """
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    # Filter for lines that contain meaningful request data
    log_filter = (
        f'resource.type="cloud_run_revision" AND '
        f'resource.labels.service_name="tripletex-agent" AND '
        f'timestamp>="{since}" AND '
        f'textPayload=~"(SOLVE v4|Task type:|Executor |API |Efficiency detail)"'
    )
    cmd = [
        "gcloud", "logging", "read",
        log_filter,
        "--project", "ai-nm26osl-1779",
        "--limit", str(limit),
        "--format", "value(textPayload)",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if result.returncode != 0:
            print(f"WARNING: gcloud returned {result.returncode}: {result.stderr[:300]}", file=sys.stderr)
            return []
        return [line for line in result.stdout.strip().split("\n") if line.strip()]
    except subprocess.TimeoutExpired:
        print("WARNING: gcloud command timed out after 90s", file=sys.stderr)
        return []
    except FileNotFoundError:
        print("WARNING: gcloud CLI not found", file=sys.stderr)
        return []


def parse_logs(raw_lines: list[str]) -> list[dict]:
    """Parse Cloud Run log lines into structured request records.

    Groups log lines into per-request records by correlating
    SOLVE v4 -> Task type -> API calls -> Executor result.
    """
    requests = []
    current = None

    # Process in reverse (oldest first, since gcloud returns newest first)
    for line in reversed(raw_lines):
        # Start of a new request
        if "=== SOLVE v4:" in line:
            if current:
                requests.append(current)
            ts_match = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
            prompt_len = re.search(r"prompt_len=(\d+)", line)
            files_count = re.search(r"files=(\d+)", line)
            current = {
                "timestamp": ts_match.group(1) if ts_match else "",
                "prompt_len": int(prompt_len.group(1)) if prompt_len else 0,
                "files": int(files_count.group(1)) if files_count else 0,
                "task_type": None,
                "api_calls": [],
                "write_calls": [],
                "errors_4xx": [],
                "success": None,
                "elapsed": None,
            }
            continue

        if not current:
            continue

        # Task type extraction
        if "Task type:" in line:
            tt_match = re.search(r"Task type: (\S+)", line)
            if tt_match:
                current["task_type"] = tt_match.group(1)

        # API calls (both successful and failed)
        api_match = re.search(r"API (\w+) (\S+) -> (\d+)", line)
        if api_match:
            method = api_match.group(1)
            path = api_match.group(2)
            status = int(api_match.group(3))
            call = {"method": method, "path": path, "status": status}
            current["api_calls"].append(call)
            if method in ("POST", "PUT", "DELETE", "PATCH"):
                current["write_calls"].append(call)
            if 400 <= status < 500:
                current["errors_4xx"].append(call)

        # Executor result
        exec_match = re.search(r"Executor (\S+): success=(\S+), elapsed=(\d+\.\d+)s", line)
        if exec_match:
            current["task_type"] = current.get("task_type") or exec_match.group(1)
            current["success"] = exec_match.group(2) == "True"
            current["elapsed"] = float(exec_match.group(3))

    # Don't forget the last request
    if current:
        requests.append(current)

    return requests


def analyze_by_task_type(requests: list[dict]) -> dict:
    """Aggregate request data by task type."""
    by_type = defaultdict(lambda: {
        "count": 0,
        "success_count": 0,
        "fail_count": 0,
        "total_writes": 0,
        "total_errors": 0,
        "total_gets": 0,
        "write_details": defaultdict(int),  # "POST /path" -> count
        "error_details": defaultdict(int),  # "POST /path -> 422" -> count
        "elapsed_list": [],
        "max_writes": 0,
        "min_writes": float("inf"),
    })

    for req in requests:
        tt = req.get("task_type")
        if not tt:
            continue

        entry = by_type[tt]
        entry["count"] += 1
        writes = len(req["write_calls"])
        errors = len(req["errors_4xx"])
        gets = len(req["api_calls"]) - writes

        entry["total_writes"] += writes
        entry["total_errors"] += errors
        entry["total_gets"] += gets
        entry["max_writes"] = max(entry["max_writes"], writes)
        entry["min_writes"] = min(entry["min_writes"], writes) if writes > 0 else entry["min_writes"]

        if req.get("success"):
            entry["success_count"] += 1
        else:
            entry["fail_count"] += 1

        if req.get("elapsed"):
            entry["elapsed_list"].append(req["elapsed"])

        for wc in req["write_calls"]:
            key = f"{wc['method']} {wc['path']}"
            entry["write_details"][key] += 1

        for ec in req["errors_4xx"]:
            key = f"{ec['method']} {ec['path']} -> {ec['status']}"
            entry["error_details"][key] += 1

    return dict(by_type)


def load_submission_log() -> dict:
    """Load submission log and compute per-task stats."""
    if not SUBMISSION_LOG.exists():
        return {}
    try:
        data = json.loads(SUBMISSION_LOG.read_text())
    except (json.JSONDecodeError, OSError):
        return {}

    stats = {
        "total_submissions": len(data),
        "scored_submissions": len([d for d in data if d.get("score") is not None]),
        "perfect_runs": len([d for d in data if d.get("score") == 1.0]),
        "avg_score": 0,
    }
    scored = [d["score"] for d in data if d.get("score") is not None and d["score"] > 0]
    if scored:
        stats["avg_score"] = sum(scored) / len(scored)
    return stats


def rank_optimization_targets(by_type: dict) -> list[dict]:
    """Rank task types by optimization potential (biggest write savings first)."""
    targets = []
    for tt, data in by_type.items():
        if data["count"] == 0:
            continue
        avg_writes = data["total_writes"] / data["count"]
        optimal = OPTIMAL_WRITES.get(tt, 1)
        waste = avg_writes - optimal
        error_rate = data["total_errors"] / data["count"] if data["count"] > 0 else 0

        targets.append({
            "task_type": tt,
            "count": data["count"],
            "avg_writes": round(avg_writes, 1),
            "optimal_writes": optimal,
            "waste_per_run": round(waste, 1),
            "total_waste": round(waste * data["count"], 0),
            "error_rate": round(error_rate, 2),
            "success_rate": round(data["success_count"] / data["count"] * 100, 0) if data["count"] > 0 else 0,
            "avg_elapsed": round(sum(data["elapsed_list"]) / len(data["elapsed_list"]), 1) if data["elapsed_list"] else 0,
            "write_details": dict(data["write_details"]),
            "error_details": dict(data["error_details"]),
        })

    # Sort by waste_per_run descending, then by count descending
    targets.sort(key=lambda x: (x["waste_per_run"], x["count"]), reverse=True)
    return targets


def print_report(targets: list[dict], sub_stats: dict, output_json: bool = False) -> None:
    """Print efficiency report to stdout."""
    if output_json:
        print(json.dumps({"submission_stats": sub_stats, "targets": targets}, indent=2))
        return

    print("=" * 70)
    print("EFFICIENCY ANALYZER REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    if sub_stats:
        print(f"\nSubmission Log: {sub_stats['total_submissions']} total, "
              f"{sub_stats['scored_submissions']} scored, "
              f"{sub_stats['perfect_runs']} perfect (1.0)")
        print(f"Average score (>0): {sub_stats['avg_score']:.3f}")

    print("\n--- PER-TASK EFFICIENCY ---\n")
    print(f"{'Task Type':<35} {'Runs':>5} {'Avg W':>6} {'Opt':>4} {'Waste':>6} {'Err%':>6} {'OK%':>5} {'Avg s':>6}")
    print("-" * 75)

    for t in targets:
        print(f"{t['task_type']:<35} {t['count']:>5} {t['avg_writes']:>6.1f} "
              f"{t['optimal_writes']:>4} {t['waste_per_run']:>+6.1f} "
              f"{t['error_rate']:>6.2f} {t['success_rate']:>4.0f}% {t['avg_elapsed']:>6.1f}")

    # Highlight worst offenders
    wasteful = [t for t in targets if t["waste_per_run"] > 0.5]
    if wasteful:
        print("\n--- TOP OPTIMIZATION TARGETS ---\n")
        for t in wasteful[:10]:
            print(f"  {t['task_type']}:")
            print(f"    Waste: {t['waste_per_run']:+.1f} writes/run ({t['total_waste']:.0f} total excess)")
            if t["write_details"]:
                print(f"    Write calls:")
                for call, count in sorted(t["write_details"].items(), key=lambda x: -x[1]):
                    print(f"      {call}: {count}x")
            if t["error_details"]:
                print(f"    4xx errors:")
                for err, count in sorted(t["error_details"].items(), key=lambda x: -x[1]):
                    print(f"      {err}: {count}x")
            print()

    # Summary
    total_waste = sum(t["total_waste"] for t in targets)
    total_errors = sum(t["error_rate"] * t["count"] for t in targets)
    print(f"\nTOTAL: {total_waste:.0f} excess write calls, {total_errors:.0f} total 4xx errors")
    print(f"Focus: Eliminate errors first (each one hurts efficiency), then reduce writes.")


def save_report_md(targets: list[dict], sub_stats: dict) -> None:
    """Save a Markdown report to EFFICIENCY-REPORT.md."""
    lines = [
        "# Efficiency Report",
        f"",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]

    if sub_stats:
        lines.extend([
            "## Submission Stats",
            f"- Total submissions: {sub_stats['total_submissions']}",
            f"- Scored: {sub_stats['scored_submissions']}",
            f"- Perfect (1.0): {sub_stats['perfect_runs']}",
            f"- Average score (>0): {sub_stats['avg_score']:.3f}",
            "",
        ])

    lines.extend([
        "## Per-Task Efficiency",
        "",
        "| Task Type | Runs | Avg Writes | Optimal | Waste | Err% | OK% |",
        "|-----------|------|-----------|---------|-------|------|-----|",
    ])

    for t in targets:
        lines.append(
            f"| {t['task_type']} | {t['count']} | {t['avg_writes']:.1f} | "
            f"{t['optimal_writes']} | {t['waste_per_run']:+.1f} | "
            f"{t['error_rate']:.2f} | {t['success_rate']:.0f}% |"
        )

    wasteful = [t for t in targets if t["waste_per_run"] > 0.5]
    if wasteful:
        lines.extend(["", "## Optimization Targets (ranked by waste)", ""])
        for i, t in enumerate(wasteful[:10], 1):
            lines.append(f"### {i}. {t['task_type']} (waste: {t['waste_per_run']:+.1f}/run)")
            if t["write_details"]:
                lines.append("Write calls:")
                for call, count in sorted(t["write_details"].items(), key=lambda x: -x[1]):
                    lines.append(f"  - `{call}`: {count}x")
            if t["error_details"]:
                lines.append("4xx errors:")
                for err, count in sorted(t["error_details"].items(), key=lambda x: -x[1]):
                    lines.append(f"  - `{err}`: {count}x")
            lines.append("")

    REPORT_OUTPUT.write_text("\n".join(lines))
    print(f"\nReport saved to: {REPORT_OUTPUT}")


def main():
    parser = argparse.ArgumentParser(description="Analyze Tripletex bot API efficiency")
    parser.add_argument("--hours", type=int, default=12, help="Hours of logs to analyze (default: 12)")
    parser.add_argument("--limit", type=int, default=2000, help="Max log lines to fetch (default: 2000)")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text")
    parser.add_argument("--save", action="store_true", help="Save Markdown report to EFFICIENCY-REPORT.md")
    args = parser.parse_args()

    print(f"Fetching Cloud Run logs (last {args.hours}h, limit {args.limit})...", file=sys.stderr)
    raw_lines = fetch_cloud_run_logs(hours=args.hours, limit=args.limit)
    print(f"Got {len(raw_lines)} log lines", file=sys.stderr)

    requests = parse_logs(raw_lines)
    print(f"Parsed {len(requests)} request records", file=sys.stderr)

    by_type = analyze_by_task_type(requests)
    sub_stats = load_submission_log()
    targets = rank_optimization_targets(by_type)

    print_report(targets, sub_stats, output_json=args.json)

    if args.save:
        save_report_md(targets, sub_stats)


if __name__ == "__main__":
    main()
