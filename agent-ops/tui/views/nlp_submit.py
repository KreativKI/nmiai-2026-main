"""Tab 5: NLP Submit - 30-task grid + submission results."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Container
from textual.widgets import Static, Label

from data import (
    load_nlp_task_log, load_nlp_submissions, load_leaderboard, find_our_team,
)


class NLPTaskGrid(Static):
    """30-task coverage display."""

    def compose(self) -> ComposeResult:
        yield Label("NLP TASK COVERAGE", classes="card-title")
        yield Static(id="nlp-grid")

    def refresh_data(self) -> None:
        widget = self.query_one("#nlp-grid", Static)
        lb = load_leaderboard()
        us = find_our_team(lb)

        nlp_score = us.get("tripletex", 0) if us else 0
        rank = us.get("rank", "?") if us else "?"
        nlp_subs_count = us.get("nlp_submissions", 0) if us else 0

        subs = load_nlp_submissions()

        # Count task types from submissions
        task_counts = {}
        for s in subs:
            tt = s.get("task_type")
            if tt:
                task_counts[tt] = task_counts.get(tt, 0) + 1

        lines = [
            f" Total: [bold]{nlp_score}[/]  |  Rank: [bold]#{rank}[/]  |  Submissions: {len(subs)}/300",
            "",
        ]

        # Show task type distribution
        if task_counts:
            lines.append(" Task types submitted:")
            for tt, count in sorted(task_counts.items(), key=lambda x: -x[1]):
                lines.append(f"   {tt}: {count} submissions")
        else:
            lines.append(" [dim]No task types recorded yet[/]")

        widget.update("\n".join(lines))


class NLPRecentResults(Static):
    """Recent NLP submission results."""

    def compose(self) -> ComposeResult:
        yield Label("RECENT RESULTS", classes="card-title")
        yield Static(id="nlp-results")

    def refresh_data(self) -> None:
        widget = self.query_one("#nlp-results", Static)
        log = load_nlp_task_log()
        if not log:
            widget.update("[dim]No results yet[/]")
            return

        lines = []
        for entry in log[-15:]:
            ts = entry.get("timestamp", "?")[:16]
            status = entry.get("status", "?")
            calls = entry.get("api_calls", 0)
            try:
                elapsed = float(entry.get("elapsed_s", 0))
            except (TypeError, ValueError):
                elapsed = 0.0
            summary = entry.get("summary", "")[:50].split("\t")[0]
            color = "green" if status == "completed" else "red"
            lines.append(f" [{color}]{status:<10}[/] {calls} calls  {elapsed:.1f}s  {summary}")

        widget.update("\n".join(lines))


class NLPSubmitView(Container):
    """NLP submission tab."""

    def compose(self) -> ComposeResult:
        with Horizontal(classes="nlp-layout"):
            yield NLPTaskGrid(classes="card main-panel")
            yield NLPRecentResults(classes="card side-panel")
        yield Static("[dim]0-9:tabs  r:refresh  q:quit[/]", classes="key-hints")

    def refresh_data(self) -> None:
        for w in self.query(NLPTaskGrid):
            w.refresh_data()
        for w in self.query(NLPRecentResults):
            w.refresh_data()
