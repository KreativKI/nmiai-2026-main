"""Tab 8: Logs - combined filterable log viewer."""

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Static, Label

from data import load_nlp_task_log, load_nlp_submissions, load_intelligence_messages


class LogsView(Container):
    """Combined log viewer."""

    def compose(self) -> ComposeResult:
        yield Label("LOGS  [dim][A]ll [M]L [C]V [N]LP [O]ps[/]", classes="card-title")
        yield Static(id="logs-content")

    def refresh_data(self) -> None:
        widget = self.query_one("#logs-content", Static)
        entries = []

        # NLP task log
        for entry in load_nlp_task_log():
            ts = entry.get("timestamp", "")[:16]
            summary = entry.get("summary", "")[:70].split("\t")[0]
            entries.append((ts, "NLP", summary))

        # NLP submissions
        for entry in load_nlp_submissions():
            ts = entry.get("timestamp", "")[:16]
            task = entry.get("task_type", "?")
            score = entry.get("score")
            score_str = f"score={score}" if score else "no score"
            entries.append((ts, "NLP", f"Submit: {task} ({score_str})"))

        # Intelligence messages
        for msg in load_intelligence_messages():
            ts = msg["modified"].strftime("%Y-%m-%d %H:%M")
            entries.append((ts, "OVR", f"{msg['target']}: {msg['filename']}"))

        # Sort by timestamp, newest first
        entries.sort(key=lambda x: x[0], reverse=True)

        lines = []
        for ts, track, text in entries[:40]:
            color = {"ML": "cyan", "CV": "green", "NLP": "yellow", "OPS": "blue", "OVR": "magenta"}.get(track, "white")
            lines.append(f" {ts} [{color}][{track}][/] {text}")

        widget.update("\n".join(lines) if lines else "[dim]No log entries[/]")
