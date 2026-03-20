"""Tab 2: Leaderboard - full competition leaderboard."""

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import DataTable, Label
from rich.text import Text

from data import load_leaderboard


class LeaderboardView(Container):
    """Full leaderboard table."""

    def compose(self) -> ComposeResult:
        yield Label("COMPETITION LEADERBOARD", classes="card-title")
        table = DataTable(id="lb-table")
        table.cursor_type = "row"
        yield table

    def on_mount(self) -> None:
        table = self.query_one("#lb-table", DataTable)
        table.add_columns("#", "Team", "Tripletex", "Astar Island", "NorgesGruppen", "Total")
        self.refresh_data()

    def refresh_data(self) -> None:
        table = self.query_one("#lb-table", DataTable)
        table.clear()
        lb = load_leaderboard()
        for row in lb:
            rank = row.get("rank", "?")
            team = row.get("team", "?")
            is_us = "kreativ" in team.lower()
            style = "bold cyan" if is_us else ""
            marker = " <" if is_us else ""
            cells = [
                str(rank),
                f"{team}{marker}",
                f"{row.get('tripletex', 0):.2f}",
                f"{row.get('astar_island', 0):.2f}",
                f"{row.get('norgesgruppen', 0):.2f}",
                f"{row.get('total', 0):.2f}",
            ]
            if is_us:
                cells = [Text(c, style=style) for c in cells]
            table.add_row(*cells)
