#!/usr/bin/env python3
"""
Persistent Unbiased Auditor for Astar Island ML Pipeline.

Spawns a code-architect agent with a consistent, unbiased system prompt.
Maintains audit history in data/audit_history.json.

Usage:
  # From another script or agent:
  from audit import run_audit
  result = run_audit("Review overnight_v5.py changes", files=["overnight_v5.py"])

  # Standalone:
  python audit.py "Review the current plan for final hours"
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
HISTORY_FILE = DATA_DIR / "audit_history.json"

AUDITOR_SYSTEM_PROMPT = """You are an independent ML competition consultant hired to audit a team's work.

Your evaluation criteria:
- Mathematical correctness: do the numbers add up?
- ML soundness: will the proposed changes actually improve predictions?
- Risk assessment: what could go wrong and is the fallback adequate?
- Priority: is the team working on the highest-impact items first?
- Completeness: is anything missing that would be obvious to a top competitor?

You have no stake in the outcome. No loyalty to the team. Your reputation
depends on giving honest, unbiased advice that maximizes their competition score.

Challenge every assumption. If something "sounds good" but lacks evidence, say so.
If a simpler approach would achieve the same result, recommend it.
If the team is over-engineering, call it out.

Always read the actual code and data, never trust summaries.

Output format:
- APPROVED: ready to proceed (with any minor notes)
- BLOCKED: specific issues that must be fixed first
- Each finding: severity (CRITICAL/IMPORTANT/MINOR), confidence %, concrete fix
"""

BASE_FILES = [
    "/Volumes/devdrive/github_dev/nmiai-worktree-ml/agent-ml/plan.md",
    "/Volumes/devdrive/github_dev/nmiai-worktree-ml/agent-ml/CLAUDE.md",
]


def load_history():
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text())
    return {"audits": []}


def save_history(history):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(history, indent=2))


def build_prompt(task_description, extra_files=None):
    """Build the full audit prompt with context files."""
    files_to_read = list(BASE_FILES)
    if extra_files:
        for f in extra_files:
            if not f.startswith("/"):
                f = f"/Volumes/devdrive/github_dev/nmiai-worktree-ml/agent-ml/solutions/{f}"
            files_to_read.append(f)

    file_instructions = "\n".join(f"- `{f}`" for f in files_to_read)

    return f"""{AUDITOR_SYSTEM_PROMPT}

**Read these files for context:**
{file_instructions}

**Audit task:**
{task_description}

**Previous audit count:** {len(load_history()['audits'])} audits completed this competition.
"""


def record_audit(task, result_summary, verdict):
    """Record an audit in the persistent history."""
    history = load_history()
    history["audits"].append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task": task,
        "verdict": verdict,
        "summary": result_summary[:500],
        "audit_number": len(history["audits"]) + 1,
    })
    save_history(history)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python audit.py 'description of what to audit'")
        print("This prints the prompt to pass to the auditor agent.")
        sys.exit(1)

    task = sys.argv[1]
    extra = sys.argv[2:] if len(sys.argv) > 2 else None
    prompt = build_prompt(task, extra)
    print(prompt)
