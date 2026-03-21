"""
Write Call Tracker for Tripletex Bot Efficiency Monitoring.

Provides request-scoped tracking of API write calls (POST/PUT/DELETE/PATCH)
and 4xx errors. Uses contextvars for async-safe per-request isolation.

Usage in tripletex_bot_v4.py:
    from scripts.write_call_tracker import tracker, get_efficiency_stats

    # At start of each /solve request:
    tracker.reset()

    # In tx() function, after each API call:
    tracker.record_call(method, path, status_code)

    # At end of request:
    stats = get_efficiency_stats()
    log.info("Efficiency: %s", stats)
"""

import contextvars
import time
from dataclasses import dataclass, field


@dataclass
class RequestTracker:
    """Tracks API calls for a single request."""
    write_count: int = 0
    error_4xx_count: int = 0
    get_count: int = 0
    calls: list = field(default_factory=list)
    start_time: float = field(default_factory=time.time)

    def record_call(self, method: str, path: str, status_code: int) -> None:
        """Record an API call. Classifies as write or read, tracks errors."""
        is_write = method.upper() in ("POST", "PUT", "DELETE", "PATCH")
        is_error = 400 <= status_code < 500

        if is_write:
            self.write_count += 1
        else:
            self.get_count += 1

        if is_error:
            self.error_4xx_count += 1

        self.calls.append({
            "method": method.upper(),
            "path": path,
            "status": status_code,
            "is_write": is_write,
            "is_error": is_error,
        })

    def get_stats(self) -> dict:
        """Return efficiency statistics for the current request."""
        elapsed = time.time() - self.start_time
        write_calls = [c for c in self.calls if c["is_write"]]
        error_calls = [c for c in self.calls if c["is_error"]]

        return {
            "write_count": self.write_count,
            "get_count": self.get_count,
            "total_calls": len(self.calls),
            "error_4xx_count": self.error_4xx_count,
            "elapsed_seconds": round(elapsed, 2),
            "write_calls": [
                f"{c['method']} {c['path']} -> {c['status']}" for c in write_calls
            ],
            "error_calls": [
                f"{c['method']} {c['path']} -> {c['status']}" for c in error_calls
            ],
        }

    def reset(self) -> None:
        """Reset tracker for a new request."""
        self.write_count = 0
        self.error_4xx_count = 0
        self.get_count = 0
        self.calls = []
        self.start_time = time.time()


# Context variable for async-safe per-request tracking
_request_tracker: contextvars.ContextVar[RequestTracker] = contextvars.ContextVar(
    "request_tracker", default=RequestTracker()
)


class TrackerProxy:
    """Proxy that delegates to the context-local RequestTracker.

    This allows importing a single 'tracker' object that is safe to use
    across concurrent async requests.
    """

    def reset(self) -> None:
        """Reset (or create) the tracker for the current request context."""
        new_tracker = RequestTracker()
        _request_tracker.set(new_tracker)

    def record_call(self, method: str, path: str, status_code: int) -> None:
        """Record an API call in the current request context."""
        _request_tracker.get().record_call(method, path, status_code)

    def get_stats(self) -> dict:
        """Get efficiency stats for the current request context."""
        return _request_tracker.get().get_stats()

    @property
    def write_count(self) -> int:
        return _request_tracker.get().write_count

    @property
    def error_4xx_count(self) -> int:
        return _request_tracker.get().error_4xx_count

    @property
    def get_count(self) -> int:
        return _request_tracker.get().get_count

    @property
    def calls(self) -> list:
        return _request_tracker.get().calls


# Module-level singleton proxy -- import and use this
tracker = TrackerProxy()


def get_efficiency_stats() -> dict:
    """Convenience function: get efficiency stats for the current request."""
    return tracker.get_stats()
