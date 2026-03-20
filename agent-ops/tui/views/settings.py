"""Tab 9: Settings - configuration display."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Container
from textual.widgets import Static, Label

from data import REPO_ROOT


class SettingsView(Container):
    """Configuration panel."""

    def compose(self) -> ComposeResult:
        with Horizontal(classes="settings-layout"):
            yield Static(id="settings-intervals", classes="card")
            yield Static(id="settings-api", classes="card")
            yield Static(id="settings-paths", classes="card")

    def on_mount(self) -> None:
        self.refresh_data()

    def refresh_data(self) -> None:
        intervals = self.query_one("#settings-intervals", Static)
        intervals.update(
            "[bold]Refresh Intervals[/]\n\n"
            "Leaderboard: 60s\n"
            "Agent status: 30s\n"
            "File watch: 5s\n\n"
            "Auto-submit: NLP only\n"
            "Max subs/day: 225 (NLP)"
        )

        api = self.query_one("#settings-api", Static)
        api.update(
            "[bold]API Status[/]\n\n"
            "ML API:  [dim]check manually[/]\n"
            "NLP Bot: [dim]check manually[/]\n"
            "GCP:     AUTHENTICATED\n\n"
            "MCP Docs: available\n"
            "Leaderboard: polling"
        )

        paths = self.query_one("#settings-paths", Static)
        paths.update(
            "[bold]Paths[/]\n\n"
            f"Repo: {REPO_ROOT.name}\n"
            "Branch: agent-ops\n"
            "Worktree: yes\n\n"
            "Tools: shared/tools/\n"
            "Data: agent-ops/dashboard/public/data/"
        )
