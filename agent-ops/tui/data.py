"""Data fetching layer for the Competition TUI.

Reads JSON files, agent statuses, and intelligence messages.
All paths are relative to the repository root.
Caches large files and only reloads on mtime change.
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# Repository root (3 levels up from tui/)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DASHBOARD_DATA = REPO_ROOT / "agent-ops" / "dashboard" / "public" / "data"
SHARED_TOOLS = REPO_ROOT / "shared" / "tools"
INTELLIGENCE = REPO_ROOT / "intelligence"

# Competition deadline
DEADLINE = datetime(2026, 3, 22, 14, 0, 0, tzinfo=timezone.utc)  # 15:00 CET = 14:00 UTC
FEATURE_FREEZE = datetime(2026, 3, 22, 8, 0, 0, tzinfo=timezone.utc)  # 09:00 CET = 08:00 UTC
CUT_LOSS = datetime(2026, 3, 21, 11, 0, 0, tzinfo=timezone.utc)  # Saturday 12:00 CET


# --- File cache (mtime-based) ---
_cache: dict[str, tuple[float, object]] = {}


def _read_json_cached(path: Path) -> dict | list | None:
    """Read JSON with mtime-based caching. Avoids re-reading large files."""
    key = str(path)
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        _cache.pop(key, None)
        return None

    cached = _cache.get(key)
    if cached and cached[0] == mtime:
        return cached[1]

    try:
        data = json.loads(path.read_text())
        _cache[key] = (mtime, data)
        return data
    except (json.JSONDecodeError, OSError):
        return None


def _read_json(path: Path) -> dict | list | None:
    """Read a small JSON file (no cache)."""
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def time_remaining() -> dict:
    """Get time remaining to each deadline."""
    now = datetime.now(timezone.utc)
    freeze_delta = FEATURE_FREEZE - now
    end_delta = DEADLINE - now
    cutloss_delta = CUT_LOSS - now
    return {
        "freeze": max(0, int(freeze_delta.total_seconds())),
        "end": max(0, int(end_delta.total_seconds())),
        "cutloss": max(0, int(cutloss_delta.total_seconds())),
    }


def format_countdown(seconds: int) -> str:
    """Format seconds as Xh Ym."""
    if seconds <= 0:
        return "PASSED"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h}h {m:02d}m"


def load_leaderboard() -> list[dict]:
    """Load leaderboard data (cached). Returns latest snapshot's rows."""
    data = _read_json_cached(DASHBOARD_DATA / "leaderboard.json")
    if not data:
        return []
    if isinstance(data, list) and data:
        latest = data[-1] if isinstance(data[-1], dict) and "rows" in data[-1] else data[0]
        return latest.get("rows", [])
    if isinstance(data, dict):
        return data.get("rows", [])
    return []


def load_score_history() -> list[dict]:
    """Load our team's score over time from leaderboard snapshots.

    Returns list of {timestamp, total, tripletex, astar_island, norgesgruppen, rank}.
    """
    data = _read_json_cached(DASHBOARD_DATA / "leaderboard.json")
    if not isinstance(data, list):
        return []

    history = []
    for snap in data:
        if not isinstance(snap, dict) or "rows" not in snap:
            continue
        ts = snap.get("timestamp", "")
        rows = snap.get("rows", [])
        us = next((r for r in rows if "kreativ" in r.get("team", "").lower()), None)
        if us:
            history.append({
                "timestamp": ts,
                "total": float(us.get("total", 0) or 0),
                "tripletex": float(us.get("tripletex", 0) or 0),
                "astar_island": float(us.get("astar_island", 0) or 0),
                "norgesgruppen": float(us.get("norgesgruppen", 0) or 0),
                "rank": us.get("rank", "?"),
            })
    return history


def render_sparkline(values: list[float], width: int = 30) -> str:
    """Render a sparkline string from a list of values using unicode blocks."""
    if not values:
        return "[dim]no data[/]"
    blocks = " ▁▂▃▄▅▆▇█"
    mn, mx = min(values), max(values)
    rng = mx - mn if mx > mn else 1

    # Sample to fit width
    if len(values) > width:
        step = len(values) / width
        sampled = [values[int(i * step)] for i in range(width)]
    else:
        sampled = values

    chars = []
    for v in sampled:
        idx = int(((v - mn) / rng) * 8)
        idx = max(0, min(8, idx))
        chars.append(blocks[idx])

    return "".join(chars)


def find_our_team(leaderboard: list[dict]) -> dict | None:
    """Find Kreativ KI in leaderboard."""
    for row in leaderboard:
        if "kreativ" in row.get("team", "").lower():
            return row
    return None


def load_agent_status(agent: str) -> dict:
    """Load an agent's status.json (small, no cache needed)."""
    path = REPO_ROOT / agent / "status.json"
    data = _read_json(path)
    return data if isinstance(data, dict) else {}


def load_all_agent_statuses() -> dict[str, dict]:
    """Load all 4 agent statuses."""
    agents = ["agent-cv", "agent-ml", "agent-nlp", "agent-ops"]
    return {a: load_agent_status(a) for a in agents}


def load_viz_data() -> dict | None:
    """Load ML terrain visualization data (LARGE file, always cached)."""
    return _read_json_cached(DASHBOARD_DATA / "viz_data.json")


def load_cv_results() -> list[dict]:
    """Load CV judge results."""
    data = _read_json_cached(SHARED_TOOLS / "cv_results.json")
    return data if isinstance(data, list) else []


def load_ml_results() -> list[dict]:
    """Load ML judge results."""
    data = _read_json_cached(SHARED_TOOLS / "ml_results.json")
    return data if isinstance(data, list) else []


def load_nlp_submissions() -> list[dict]:
    """Load NLP submission log."""
    data = _read_json_cached(SHARED_TOOLS / "nlp_submission_log.json")
    return data if isinstance(data, list) else []


def load_nlp_task_log() -> list[dict]:
    """Load NLP task execution log from dashboard."""
    data = _read_json_cached(DASHBOARD_DATA / "nlp_task_log.json")
    return data if isinstance(data, list) else []


def load_cv_training_log() -> list[dict]:
    """Load CV training log."""
    data = _read_json_cached(DASHBOARD_DATA / "cv_training_log.json")
    return data if isinstance(data, list) else []


def _strip_md(text: str) -> str:
    """Strip markdown formatting that breaks Rich markup."""
    return text.replace("**", "").replace("*", "").replace("`", "").replace("[", "(").replace("]", ")").replace("→", "->")


def load_agent_context(agent: str) -> dict:
    """Parse agent's plan.md + status.json into what/why/next summary.

    Returns dict with keys: what, why, next_step, approach, score, phase.
    """
    status = load_agent_status(agent)
    plan_path = REPO_ROOT / agent / "plan.md"

    result = {
        "what": status.get("phase", "--"),
        "why": "",
        "next_step": "",
        "approach": status.get("approach", "--"),
        "score": status.get("best_submitted_score", 0),
        "phase": status.get("phase", "--"),
        "state": status.get("state", "unknown"),
        "confidence": status.get("confidence", 0),
        "notes": _strip_md(status.get("notes", "")),
        "endpoint": status.get("endpoint", ""),
        "timestamp": status.get("timestamp", ""),
    }

    # Parse plan.md for current approach description
    try:
        plan_text = plan_path.read_text()
        lines = plan_text.split("\n")

        # Find "## Approach A (Primary)" section for the WHY
        for i, line in enumerate(lines):
            if "Primary" in line and "Approach" in line:
                # Next line with "**Why" has the reasoning
                for j in range(i + 1, min(i + 5, len(lines))):
                    if "Why" in lines[j]:
                        result["why"] = _strip_md(lines[j]).strip(": ")
                        break
                    elif lines[j].strip() and not lines[j].startswith("#"):
                        if not result["why"]:
                            result["why"] = _strip_md(lines[j]).strip()
                break

        # Find current phase status for next_step
        for i, line in enumerate(lines):
            if "Status:" in line and "current" in line.lower():
                result["next_step"] = line.split("Status:")[-1].strip()
                break

    except (FileNotFoundError, OSError):
        pass

    # Enrich "what" based on agent type
    if agent == "agent-cv":
        result["what"] = f"{status.get('phase', 'unknown')}: {status.get('approach', '')[:30]}"
    elif agent == "agent-nlp":
        ep = status.get("endpoint", "")
        if ep:
            result["what"] = f"Bot deployed at Cloud Run"
        else:
            result["what"] = status.get("phase", "unknown")
    elif agent == "agent-ml":
        result["what"] = status.get("phase", "waiting for round")

    return result


def load_intelligence_messages() -> list[dict]:
    """Scan intelligence folders for messages."""
    messages = []
    if not INTELLIGENCE.exists():
        return messages
    for folder in sorted(INTELLIGENCE.iterdir()):
        if not folder.is_dir():
            continue
        target = folder.name
        for f in sorted(folder.glob("*.md")):
            messages.append({
                "target": target,
                "filename": f.name,
                "modified": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc),
            })
    return messages
