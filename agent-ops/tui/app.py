"""NM i AI 2026 Competition Command Center TUI.

Launch: cd agent-ops/tui && source .venv/bin/activate && python app.py
"""

from textual.app import App, ComposeResult
from textual.widgets import TabbedContent, TabPane, Static, Footer
from textual.events import Key

from views.dashboard import DashboardView
from views.agents import AgentsView
from views.leaderboard import LeaderboardView
from views.ml_explorer import MLExplorerView, TerrainGridWidget
from views.cv_status import CVStatusView
from views.nlp_submit import NLPSubmitView
from views.submit import SubmitView
from views.tools import ToolsView
from views.logs import LogsView
from views.settings import SettingsView
from data import time_remaining, format_countdown, load_leaderboard, find_our_team


TAB_IDS = [
    "tab-dashboard", "tab-agents", "tab-leaderboard", "tab-ml", "tab-cv",
    "tab-nlp", "tab-submit", "tab-tools", "tab-logs", "tab-settings",
]


class CompetitionTUI(App):
    """NM i AI 2026 Mission Control."""

    TITLE = "NM i AI 2026 Command Center"
    CSS_PATH = "style.tcss"

    BINDINGS = [
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
        # Initial load: refresh ALL tabs once so they have data
        self.action_refresh_all()
        # Periodic: only refresh active tab (lighter on system)
        self.set_interval(30, self.refresh_all)
        self.set_interval(5, self.update_status_bar)

    def on_key(self, event: Key) -> None:
        """Route number keys: on ML tab 1-5 switch seeds, otherwise switch tabs."""
        if event.key in "0123456789":
            num = int(event.key)
            tabs = self.query_one("#tabs", TabbedContent)

            # On ML tab, 1-5 switch seeds instead of tabs
            if tabs.active == "tab-ml" and 1 <= num <= 5:
                for w in self.query(TerrainGridWidget):
                    w.switch_seed(num - 1)
                event.prevent_default()
                return

            # Otherwise switch tabs
            if 0 <= num <= 9:
                tabs.active = TAB_IDS[num]
                event.prevent_default()

    def refresh_all(self) -> None:
        """Refresh only the active tab (lighter on system resources)."""
        tabs = self.query_one("#tabs", TabbedContent)
        active = tabs.active

        # Always refresh dashboard (it's the overview)
        for view in self.query(DashboardView):
            try:
                view.refresh_data()
            except Exception:
                pass

        # Refresh the currently visible tab
        tab_to_view = {
            "tab-agents": AgentsView,
            "tab-leaderboard": LeaderboardView,
            "tab-ml": MLExplorerView,
            "tab-cv": CVStatusView,
            "tab-nlp": NLPSubmitView,
            "tab-submit": SubmitView,
            "tab-tools": ToolsView,
            "tab-logs": LogsView,
            "tab-settings": SettingsView,
        }
        view_cls = tab_to_view.get(active)
        if view_cls:
            for view in self.query(view_cls):
                try:
                    view.refresh_data()
                except Exception:
                    pass

        self.update_status_bar()

    def action_refresh_all(self) -> None:
        """Manual refresh: refresh ALL tabs."""
        for view_cls in (DashboardView, AgentsView, LeaderboardView, MLExplorerView,
                         CVStatusView, NLPSubmitView, SubmitView, ToolsView, LogsView,
                         SettingsView):
            for view in self.query(view_cls):
                try:
                    view.refresh_data()
                except Exception:
                    pass
        self.update_status_bar()
        self.notify("All data refreshed")

    def update_status_bar(self) -> None:
        try:
            bar = self.query_one("#status-bar", Static)
            tr = time_remaining()
            lb = load_leaderboard()
            us = find_our_team(lb)
            rank = us.get("rank", "?") if us else "?"
            score = float(us.get("total", 0) or 0) if us else 0.0
            nlp_score = float(us.get("tripletex", 0) or 0) if us else 0.0
            ml_score = float(us.get("astar_island", 0) or 0) if us else 0.0
            bar.update(
                f" #{rank} | Total {score:.1f} | ML {ml_score:.1f} | NLP {nlp_score:.1f} | "
                f"FREEZE {format_countdown(tr['freeze'])} | END {format_countdown(tr['end'])} | "
                f"[r]efresh [0-9]tabs [q]uit"
            )
        except Exception:
            pass


if __name__ == "__main__":
    app = CompetitionTUI()
    app.run()
