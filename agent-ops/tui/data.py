"""Data fetching layer for the Competition TUI.

Reads JSON files, agent statuses, and intelligence messages.
All paths are relative to the repository root.
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


def _read_json(path: Path) -> dict | list | None:
    """Read a JSON file, return None on error."""
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
    """Load leaderboard data."""
    data = _read_json(DASHBOARD_DATA / "leaderboard.json")
    if not data:
        return []
    # Can be a list of snapshots; use the latest
    if isinstance(data, list) and data:
        latest = data[-1] if isinstance(data[-1], dict) and "rows" in data[-1] else data[0]
        return latest.get("rows", [])
    if isinstance(data, dict):
        return data.get("rows", [])
    return []


def find_our_team(leaderboard: list[dict]) -> dict | None:
    """Find Kreativ KI in leaderboard."""
    for row in leaderboard:
        if "kreativ" in row.get("team", "").lower():
            return row
    return None


def load_agent_status(agent: str) -> dict:
    """Load an agent's status.json."""
    path = REPO_ROOT / agent / "status.json"
    data = _read_json(path)
    return data if isinstance(data, dict) else {}


def load_all_agent_statuses() -> dict[str, dict]:
    """Load all 4 agent statuses."""
    agents = ["agent-cv", "agent-ml", "agent-nlp", "agent-ops"]
    return {a: load_agent_status(a) for a in agents}


def load_viz_data() -> dict | None:
    """Load ML terrain visualization data."""
    return _read_json(DASHBOARD_DATA / "viz_data.json")


def load_cv_results() -> list[dict]:
    """Load CV judge results."""
    data = _read_json(SHARED_TOOLS / "cv_results.json")
    return data if isinstance(data, list) else []


def load_ml_results() -> list[dict]:
    """Load ML judge results."""
    data = _read_json(SHARED_TOOLS / "ml_results.json")
    return data if isinstance(data, list) else []


def load_nlp_submissions() -> list[dict]:
    """Load NLP submission log."""
    data = _read_json(SHARED_TOOLS / "nlp_submission_log.json")
    return data if isinstance(data, list) else []


def load_nlp_task_log() -> list[dict]:
    """Load NLP task execution log from dashboard."""
    data = _read_json(DASHBOARD_DATA / "nlp_task_log.json")
    return data if isinstance(data, list) else []


def load_cv_training_log() -> list[dict]:
    """Load CV training log."""
    data = _read_json(DASHBOARD_DATA / "cv_training_log.json")
    return data if isinstance(data, list) else []


def load_intelligence_messages() -> list[dict]:
    """Scan intelligence folders for messages."""
    messages = []
    if not INTELLIGENCE.exists():
        return messages
    for folder in sorted(INTELLIGENCE.iterdir()):
        if not folder.is_dir():
            continue
        target = folder.name  # e.g. "for-cv-agent"
        for f in sorted(folder.glob("*.md")):
            messages.append({
                "target": target,
                "filename": f.name,
                "modified": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc),
            })
    return messages
