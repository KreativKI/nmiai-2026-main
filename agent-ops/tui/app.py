"""NM i AI 2026 Competition Command Center TUI.

Launch: python -m agent-ops.tui.app (from repo root)
    or: cd agent-ops/tui && source .venv/bin/activate && python app.py
"""

from textual.app import App, ComposeResult
from textual.widgets import TabbedContent, TabPane, Static, Footer
from textual.timer import Timer
from textual import work

from views.dashboard import DashboardView
from views.agents import AgentsView
from views.leaderboard import LeaderboardView
from views.ml_explorer import MLExplorerView
from views.cv_status import CVStatusView
from views.nlp_submit import NLPSubmitView
from views.submit import SubmitView
from views.tools import ToolsView
from views.logs import LogsView
from views.settings import SettingsView
from data import time_remaining, format_countdown, load_leaderboard, find_our_team


class CompetitionTUI(App):
    """NM i AI 2026 Mission Control."""

    TITLE = "NM i AI 2026 Command Center"
    CSS_PATH = "style.tcss"

    BINDINGS = [
        ("0", "switch_tab('tab-dashboard')", "Dashboard"),
        ("1", "switch_tab('tab-agents')", "Agents"),
        ("2", "switch_tab('tab-leaderboard')", "Leaderboard"),
        ("3", "switch_tab('tab-ml')", "ML"),
        ("4", "switch_tab('tab-cv')", "CV"),
        ("5", "switch_tab('tab-nlp')", "NLP"),
        ("6", "switch_tab('tab-submit')", "Submit"),
        ("7", "switch_tab('tab-tools')", "Tools"),
        ("8", "switch_tab('tab-logs')", "Logs"),
        ("9", "switch_tab('tab-settings')", "Settings"),
        ("r", "refresh_all", "Refresh"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("NM i AI 2026 | Kreativ KI", id="app-header")
        with TabbedContent(id="tabs"):
            with TabPane("0:Dashboard", id="tab-dashboard"):
                yield DashboardView()
            with TabPane("1:Agents", id="tab-agents"):
                yield AgentsView()
            with TabPane("2:Leaderboard", id="tab-leaderboard"):
                yield LeaderboardView()
            with TabPane("3:ML", id="tab-ml"):
                yield MLExplorerView()
            with TabPane("4:CV", id="tab-cv"):
                yield CVStatusView()
            with TabPane("5:NLP", id="tab-nlp"):
                yield NLPSubmitView()
            with TabPane("6:Submit", id="tab-submit"):
                yield SubmitView()
            with TabPane("7:Tools", id="tab-tools"):
                yield ToolsView()
            with TabPane("8:Logs", id="tab-logs"):
                yield LogsView()
            with TabPane("9:Settings", id="tab-settings"):
                yield SettingsView()
        yield Static(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_all()
        # Auto-refresh every 30 seconds
        self.set_interval(30, self.refresh_all)
        # Status bar updates every 5 seconds
        self.set_interval(5, self.update_status_bar)

    def action_switch_tab(self, tab_id: str) -> None:
        tabs = self.query_one("#tabs", TabbedContent)
        tabs.active = tab_id

    def refresh_all(self) -> None:
        """Refresh all views."""
        for view_cls in (DashboardView, AgentsView, LeaderboardView, MLExplorerView,
                         CVStatusView, NLPSubmitView, SubmitView, ToolsView, LogsView,
                         SettingsView):
            for view in self.query(view_cls):
                try:
                    view.refresh_data()
                except Exception:
                    pass
        self.update_status_bar()

    def action_refresh_all(self) -> None:
        self.refresh_all()
        self.notify("Data refreshed")

    def update_status_bar(self) -> None:
        try:
            bar = self.query_one("#status-bar", Static)
            tr = time_remaining()
            lb = load_leaderboard()
            us = find_our_team(lb)
            rank = us.get("rank", "?") if us else "?"
            score = float(us.get("total", 0) or 0) if us else 0.0
            nlp_score = float(us.get("tripletex", 0) or 0) if us else 0.0
            bar.update(
                f" Rank #{rank} | Score {score:.1f} | NLP {nlp_score:.1f} | "
                f"FREEZE {format_countdown(tr['freeze'])} | END {format_countdown(tr['end'])} | "
                f"[r]efresh [q]uit"
            )
        except Exception:
            pass


if __name__ == "__main__":
    app = CompetitionTUI()
    app.run()
