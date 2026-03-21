#!/usr/bin/env python3
"""
Self-Improving Loop for Tripletex Bot.

Master script that orchestrates the efficiency improvement pipeline:
  Phase 1 - ANALYZE:   Run efficiency_analyzer, collect results
  Phase 2 - DIAGNOSE:  Parse Cloud Run logs to find specific inefficiencies
  Phase 3 - PRESCRIBE: Generate FIXES-QUEUE.md with ranked code changes
  Phase 4 - REPORT:    Write human-readable EFFICIENCY-REPORT.md

Uses Gemini (via Vertex AI) to analyze log patterns and suggest code fixes.

Usage:
    python3 agent-nlp/scripts/self_improve.py
    python3 agent-nlp/scripts/self_improve.py --hours 6
    python3 agent-nlp/scripts/self_improve.py --skip-gemini  # Skip AI analysis, just stats
"""

import argparse
import json
import os
import re
import subprocess
import sys
import textwrap
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
SOLUTIONS_DIR = SCRIPT_DIR.parent / "solutions"
BOT_FILE = SOLUTIONS_DIR / "tripletex_bot_v4.py"
FIXES_QUEUE = SOLUTIONS_DIR / "FIXES-QUEUE.md"
EFFICIENCY_REPORT = SOLUTIONS_DIR / "EFFICIENCY-REPORT.md"

# Optimal write budgets
OPTIMAL_WRITES = {
    "create_customer": 1,
    "create_employee": 1,
    "create_employee_with_employment": 3,
    "create_product": 1,
    "create_department": 1,
    "create_project": 2,
    "create_invoice": 1,
    "create_invoice_with_payment": 2,
    "create_project_invoice": 3,
    "register_payment": 1,
    "create_credit_note": 1,
    "create_travel_expense": 3,
    "delete_employee": 1,
    "delete_travel_expense": 1,
    "update_customer": 1,
    "update_employee": 1,
    "create_contact": 1,
    "enable_module": 1,
    "process_salary": 3,
    "register_supplier_invoice": 2,
    "create_dimension": 2,
    "create_supplier": 1,
}

# Known inefficiencies to check (from code analysis)
KNOWN_ISSUES = {
    "create_invoice": {
        "description": "PUT /ledger/account to set bankAccountNumber may be unnecessary if already set",
        "waste_writes": 1,
        "fix": "Check if account 1920 already has bankAccountNumber before PUT",
        "line_hint": "exec_create_invoice",
    },
    "create_project": {
        "description": "POST /employee for PM may fail (422 email conflict), then PUT to rename admin",
        "waste_writes": 2,
        "fix": "Check admin name first; if PM matches admin, skip employee creation entirely",
        "line_hint": "exec_create_project",
    },
    "process_salary": {
        "description": "PUT /employee to set dateOfBirth on EXISTING employees unconditionally",
        "waste_writes": 1,
        "fix": "GET employee first, check if dateOfBirth is already set before PUT",
        "line_hint": "exec_process_salary",
    },
    "create_travel_expense": {
        "description": "Always creates new employee even if one with same name exists",
        "waste_writes": 2,
        "fix": "GET /employee by name first; if exists, use existing ID",
        "line_hint": "exec_create_travel_expense",
    },
    "create_invoice_with_payment": {
        "description": "Inherits create_invoice waste (bank PUT) + GET paymentType",
        "waste_writes": 1,
        "fix": "Fix create_invoice bank PUT, paymentType GET is free",
        "line_hint": "exec_create_invoice_with_payment",
    },
    "create_project_invoice": {
        "description": "Inherits create_project PM creation issues + bank PUT",
        "waste_writes": 2,
        "fix": "Fix PM creation and bank account setup",
        "line_hint": "exec_create_project_invoice",
    },
}


def fetch_logs(hours: int = 12, limit: int = 3000) -> list[str]:
    """Fetch Cloud Run logs via gcloud logging read.

    Uses targeted filter for request-relevant lines only.
    """
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
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
            print(f"WARNING: gcloud error: {result.stderr[:300]}", file=sys.stderr)
            return []
        return [line for line in result.stdout.strip().split("\n") if line.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"WARNING: Could not fetch logs: {e}", file=sys.stderr)
        return []


def parse_request_groups(raw_lines: list[str]) -> list[dict]:
    """Group log lines into per-request records."""
    requests = []
    current = None

    for line in reversed(raw_lines):
        if "=== SOLVE v4:" in line:
            if current:
                requests.append(current)
            ts_match = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
            current = {
                "timestamp": ts_match.group(1) if ts_match else "",
                "task_type": None,
                "api_calls": [],
                "write_sequence": [],
                "errors": [],
                "success": None,
                "elapsed": None,
                "raw_lines": [line],
            }
            continue

        if not current:
            continue

        current["raw_lines"].append(line)

        if "Task type:" in line:
            tt_match = re.search(r"Task type: (\S+)", line)
            if tt_match:
                current["task_type"] = tt_match.group(1)

        api_match = re.search(r"API (\w+) (\S+) -> (\d+)", line)
        if api_match:
            method, path, status = api_match.group(1), api_match.group(2), int(api_match.group(3))
            call = {"method": method, "path": path, "status": status}
            current["api_calls"].append(call)
            if method in ("POST", "PUT", "DELETE", "PATCH"):
                current["write_sequence"].append(f"{method} {path} -> {status}")
            if 400 <= status < 500:
                # Extract error message if present
                err_msg_match = re.search(r"-> \d+: (.+)", line)
                err_msg = err_msg_match.group(1)[:200] if err_msg_match else ""
                current["errors"].append({
                    "call": f"{method} {path}",
                    "status": status,
                    "message": err_msg,
                })

        exec_match = re.search(r"Executor (\S+): success=(\S+), elapsed=(\d+\.\d+)s", line)
        if exec_match:
            current["task_type"] = current.get("task_type") or exec_match.group(1)
            current["success"] = exec_match.group(2) == "True"
            current["elapsed"] = float(exec_match.group(3))

    if current:
        requests.append(current)

    return requests


def diagnose_per_executor(requests: list[dict]) -> dict:
    """For each task type, identify specific inefficiencies."""
    diagnostics = defaultdict(lambda: {
        "runs": 0,
        "successful_runs": 0,
        "write_sequences": [],
        "error_patterns": defaultdict(int),
        "avg_writes": 0,
        "known_issue": None,
        "specific_waste": [],
    })

    for req in requests:
        tt = req.get("task_type")
        if not tt:
            continue

        diag = diagnostics[tt]
        diag["runs"] += 1
        writes = len([c for c in req["api_calls"] if c["method"] in ("POST", "PUT", "DELETE", "PATCH")])
        if req.get("success"):
            diag["successful_runs"] += 1

        if req["write_sequence"]:
            diag["write_sequences"].append(req["write_sequence"])

        for err in req["errors"]:
            pattern = f"{err['call']} -> {err['status']}"
            diag["error_patterns"][pattern] += 1

    # Compute averages and identify waste
    for tt, diag in diagnostics.items():
        if diag["runs"] > 0:
            total_writes = sum(len(seq) for seq in diag["write_sequences"])
            diag["avg_writes"] = total_writes / diag["runs"]
            optimal = OPTIMAL_WRITES.get(tt, 1)
            waste = diag["avg_writes"] - optimal

            if tt in KNOWN_ISSUES:
                diag["known_issue"] = KNOWN_ISSUES[tt]

            # Identify specific wasteful patterns
            if waste > 0.3:
                # Find the most common extra writes
                write_counts = defaultdict(int)
                for seq in diag["write_sequences"]:
                    for w in seq:
                        write_counts[w] += 1

                for call, count in sorted(write_counts.items(), key=lambda x: -x[1]):
                    freq = count / diag["runs"]
                    if freq > 0.3:
                        # Check if this is a "wasted" write (fails often)
                        fail_key = None
                        for err_pattern, err_count in diag["error_patterns"].items():
                            if call.split(" -> ")[0] in err_pattern:
                                fail_key = err_pattern
                                break
                        diag["specific_waste"].append({
                            "call": call,
                            "frequency": round(freq, 2),
                            "fails_as": fail_key,
                        })

    return dict(diagnostics)


def generate_fixes_queue(diagnostics: dict) -> str:
    """Generate FIXES-QUEUE.md content ranked by impact."""
    fixes = []

    for tt, diag in diagnostics.items():
        if diag["runs"] == 0:
            continue

        optimal = OPTIMAL_WRITES.get(tt, 1)
        waste = diag["avg_writes"] - optimal
        impact = waste * diag["runs"]  # Total excess writes

        if waste <= 0.1 and not diag["error_patterns"]:
            continue  # Already efficient

        fix_entry = {
            "task_type": tt,
            "impact_score": round(impact + len(diag["error_patterns"]) * 5, 1),
            "avg_writes": round(diag["avg_writes"], 1),
            "optimal": optimal,
            "waste_per_run": round(waste, 1),
            "runs_observed": diag["runs"],
            "success_rate": round(diag["successful_runs"] / diag["runs"] * 100, 0) if diag["runs"] > 0 else 0,
            "errors": dict(diag["error_patterns"]),
            "known_fix": diag.get("known_issue"),
            "waste_details": diag["specific_waste"],
        }
        fixes.append(fix_entry)

    fixes.sort(key=lambda x: x["impact_score"], reverse=True)

    # Generate markdown
    lines = [
        "# FIXES QUEUE -- Ranked Efficiency Improvements",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "Priority: Fix errors first (each 4xx hurts efficiency), then reduce writes.",
        "",
    ]

    for i, fix in enumerate(fixes, 1):
        lines.append(f"## {i}. {fix['task_type']} (impact: {fix['impact_score']})")
        lines.append(f"- Runs observed: {fix['runs_observed']}")
        lines.append(f"- Avg writes: {fix['avg_writes']} (optimal: {fix['optimal']}, waste: {fix['waste_per_run']:+.1f})")
        lines.append(f"- Success rate: {fix['success_rate']:.0f}%")

        if fix["errors"]:
            lines.append("- **4xx errors:**")
            for err, count in sorted(fix["errors"].items(), key=lambda x: -x[1]):
                lines.append(f"  - `{err}`: {count}x")

        if fix["waste_details"]:
            lines.append("- **Wasteful calls:**")
            for w in fix["waste_details"]:
                fails = f" (often fails as: {w['fails_as']})" if w["fails_as"] else ""
                lines.append(f"  - `{w['call']}` ({w['frequency']*100:.0f}% of runs){fails}")

        if fix["known_fix"]:
            kf = fix["known_fix"]
            lines.append(f"- **Known fix:** {kf['description']}")
            lines.append(f"  - How: {kf['fix']}")
            lines.append(f"  - Saves: ~{kf['waste_writes']} write(s)/run")
            lines.append(f"  - Look at: `{kf['line_hint']}`")

        lines.append("")

    return "\n".join(lines)


def read_bot_code() -> str:
    """Read the current bot source for AI analysis."""
    if BOT_FILE.exists():
        return BOT_FILE.read_text()
    return ""


def call_gemini_analysis(diagnostics: dict, bot_excerpt: str) -> str | None:
    """Use Gemini to generate intelligent fix recommendations."""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("WARNING: google-genai not installed, skipping AI analysis", file=sys.stderr)
        return None

    # Build analysis prompt
    diag_summary = json.dumps(
        {tt: {
            "avg_writes": d["avg_writes"],
            "optimal": OPTIMAL_WRITES.get(tt, 1),
            "errors": dict(d["error_patterns"]),
            "runs": d["runs"],
            "success_rate": round(d["successful_runs"] / d["runs"] * 100) if d["runs"] > 0 else 0,
            "waste_details": d["specific_waste"][:5],
        } for tt, d in diagnostics.items() if d["runs"] > 0},
        indent=2
    )

    # Extract relevant executor functions (not the whole file)
    executor_code = ""
    if bot_excerpt:
        # Find all executor function definitions
        pattern = re.compile(r"(async def exec_\w+\(.*?\n(?:(?!async def ).)*)", re.DOTALL)
        matches = pattern.findall(bot_excerpt)
        for match in matches:
            # Truncate each executor to first 40 lines
            func_lines = match.split("\n")[:40]
            executor_code += "\n".join(func_lines) + "\n...\n\n"

    prompt = f"""You are analyzing a Tripletex API bot for efficiency. The bot makes API calls
and each WRITE call (POST/PUT/DELETE/PATCH) counts against an efficiency score.
GET calls are FREE. Each 4xx error also hurts efficiency.

Here is the diagnostic data from recent Cloud Run logs:

{diag_summary}

Here are the executor functions from the bot code:

{executor_code[:8000]}

For each task type with waste > 0 or errors, provide a SPECIFIC code change:
1. Which function to modify
2. What line(s) to change
3. The exact logic change (not full code, just the key change)
4. Expected write savings

Focus on the HIGHEST IMPACT changes first.
Return as a numbered list. Be concise and specific.
"""

    try:
        client = genai.Client(
            vertexai=True,
            project=os.getenv("GCP_PROJECT", "ai-nm26osl-1779"),
            location=os.getenv("GCP_LOCATION", "us-central1"),
        )
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)])],
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=4096,
            ),
        )
        return response.text
    except Exception as e:
        print(f"WARNING: Gemini analysis failed: {e}", file=sys.stderr)
        return None


def generate_report(diagnostics: dict, fixes_md: str, gemini_analysis: str | None) -> str:
    """Generate final EFFICIENCY-REPORT.md."""
    lines = [
        "# Efficiency Report -- Self-Improving Loop",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Summary",
        "",
    ]

    total_runs = sum(d["runs"] for d in diagnostics.values())
    total_waste = sum(
        (d["avg_writes"] - OPTIMAL_WRITES.get(tt, 1)) * d["runs"]
        for tt, d in diagnostics.items()
        if d["runs"] > 0
    )
    total_errors = sum(
        sum(d["error_patterns"].values())
        for d in diagnostics.values()
    )

    lines.extend([
        f"- Total request runs analyzed: {total_runs}",
        f"- Total excess writes: {total_waste:.0f}",
        f"- Total 4xx errors: {total_errors}",
        f"- Task types observed: {len([d for d in diagnostics.values() if d['runs'] > 0])}",
        "",
        "## Per-Task Breakdown",
        "",
        "| Task Type | Runs | Avg W | Opt | Waste | Errors | OK% |",
        "|-----------|------|-------|-----|-------|--------|-----|",
    ])

    for tt, d in sorted(diagnostics.items(), key=lambda x: x[1]["avg_writes"] - OPTIMAL_WRITES.get(x[0], 1), reverse=True):
        if d["runs"] == 0:
            continue
        optimal = OPTIMAL_WRITES.get(tt, 1)
        waste = d["avg_writes"] - optimal
        err_count = sum(d["error_patterns"].values())
        ok_rate = round(d["successful_runs"] / d["runs"] * 100) if d["runs"] > 0 else 0
        lines.append(
            f"| {tt} | {d['runs']} | {d['avg_writes']:.1f} | {optimal} | "
            f"{waste:+.1f} | {err_count} | {ok_rate}% |"
        )

    if gemini_analysis:
        lines.extend([
            "",
            "## AI-Generated Fix Recommendations",
            "",
            gemini_analysis,
        ])

    lines.extend([
        "",
        "## Next Steps",
        "",
        "1. Fix 4xx errors first (each error reduces efficiency bonus)",
        "2. Eliminate unnecessary writes in highest-waste executors",
        "3. Re-run this script after changes to verify improvement",
        "4. Deploy and submit to measure real efficiency delta",
    ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Self-improving efficiency loop for Tripletex bot")
    parser.add_argument("--hours", type=int, default=12, help="Hours of logs to analyze")
    parser.add_argument("--limit", type=int, default=3000, help="Max log lines")
    parser.add_argument("--skip-gemini", action="store_true", help="Skip Gemini AI analysis")
    args = parser.parse_args()

    # Phase 1: ANALYZE
    print("=" * 60, file=sys.stderr)
    print("Phase 1: ANALYZE -- Fetching and parsing logs", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    raw_lines = fetch_logs(hours=args.hours, limit=args.limit)
    print(f"  Fetched {len(raw_lines)} log lines", file=sys.stderr)

    requests = parse_request_groups(raw_lines)
    print(f"  Parsed {len(requests)} request records", file=sys.stderr)

    # Phase 2: DIAGNOSE
    print("\n" + "=" * 60, file=sys.stderr)
    print("Phase 2: DIAGNOSE -- Identifying inefficiencies", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    diagnostics = diagnose_per_executor(requests)
    for tt, diag in sorted(diagnostics.items()):
        if diag["runs"] > 0:
            optimal = OPTIMAL_WRITES.get(tt, 1)
            waste = diag["avg_writes"] - optimal
            err_count = sum(diag["error_patterns"].values())
            status = "OK" if waste <= 0.1 and err_count == 0 else "NEEDS FIX"
            print(f"  {tt}: {diag['avg_writes']:.1f} writes (opt {optimal}) "
                  f"| {err_count} errors | {status}", file=sys.stderr)

    # Phase 3: PRESCRIBE
    print("\n" + "=" * 60, file=sys.stderr)
    print("Phase 3: PRESCRIBE -- Generating fix queue", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    fixes_md = generate_fixes_queue(diagnostics)
    FIXES_QUEUE.write_text(fixes_md)
    print(f"  Saved: {FIXES_QUEUE}", file=sys.stderr)

    gemini_analysis = None
    if not args.skip_gemini:
        print("  Running Gemini analysis...", file=sys.stderr)
        bot_code = read_bot_code()
        gemini_analysis = call_gemini_analysis(diagnostics, bot_code)
        if gemini_analysis:
            print("  Gemini analysis complete", file=sys.stderr)
        else:
            print("  Gemini analysis skipped/failed", file=sys.stderr)

    # Phase 4: REPORT
    print("\n" + "=" * 60, file=sys.stderr)
    print("Phase 4: REPORT -- Writing efficiency report", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    report = generate_report(diagnostics, fixes_md, gemini_analysis)
    EFFICIENCY_REPORT.write_text(report)
    print(f"  Saved: {EFFICIENCY_REPORT}", file=sys.stderr)

    # Print summary to stdout
    print("\n--- SELF-IMPROVE SUMMARY ---")
    total_runs = sum(d["runs"] for d in diagnostics.values())
    wasteful = {tt: d for tt, d in diagnostics.items()
                if d["runs"] > 0 and d["avg_writes"] - OPTIMAL_WRITES.get(tt, 1) > 0.3}
    erroring = {tt: d for tt, d in diagnostics.items()
                if d["runs"] > 0 and sum(d["error_patterns"].values()) > 0}

    print(f"Analyzed: {total_runs} requests, {len(diagnostics)} task types")
    print(f"Wasteful executors: {len(wasteful)}")
    print(f"Erroring executors: {len(erroring)}")
    print(f"\nFixes queue: {FIXES_QUEUE}")
    print(f"Full report: {EFFICIENCY_REPORT}")

    if wasteful or erroring:
        print("\nTop priorities:")
        combined = set(list(wasteful.keys()) + list(erroring.keys()))
        for i, tt in enumerate(sorted(combined), 1):
            d = diagnostics[tt]
            optimal = OPTIMAL_WRITES.get(tt, 1)
            waste = d["avg_writes"] - optimal
            errs = sum(d["error_patterns"].values())
            print(f"  {i}. {tt}: waste={waste:+.1f}, errors={errs}")
            if i >= 5:
                break


if __name__ == "__main__":
    main()
