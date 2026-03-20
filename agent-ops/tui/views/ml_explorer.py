"""Tab 3: ML Explorer - terrain grid + round history."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Container
from textual.widgets import Static, Label, DataTable

from data import load_viz_data, load_ml_results
from terrain import render_terrain_grid, count_terrain, render_legend


class TerrainGridWidget(Static):
    """40x40 terrain grid display."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.current_seed = 0
        self.grid_data = None

    def compose(self) -> ComposeResult:
        yield Label("TERRAIN GRID", classes="card-title")
        yield Static(id="terrain-display")
        yield Static(id="terrain-stats")

    def refresh_data(self) -> None:
        viz = load_viz_data()
        display = self.query_one("#terrain-display", Static)
        stats = self.query_one("#terrain-stats", Static)

        if not viz:
            display.update("[dim]No terrain data loaded[/]")
            stats.update("")
            return

        # Find first available round
        round_key = next(iter(viz), None)
        if not round_key:
            display.update("[dim]No rounds in data[/]")
            return

        round_data = viz[round_key]
        seeds = round_data.get("seeds", [])
        if self.current_seed >= len(seeds):
            display.update(f"[dim]Seed {self.current_seed} not available[/]")
            return

        grid = seeds[self.current_seed].get("grid", [])
        self.grid_data = grid
        display.update(render_terrain_grid(grid))

        counts = count_terrain(grid)
        count_str = "  ".join(f"{k}:{v}" for k, v in sorted(counts.items()))
        stats.update(
            f"Seed: {self.current_seed}  |  [1-5] Switch seed\n"
            f"{count_str}"
        )


class RoundHistory(Static):
    """ML round history and results."""

    def compose(self) -> ComposeResult:
        yield Label("ROUND HISTORY", classes="card-title")
        yield Static(id="round-history")

    def refresh_data(self) -> None:
        results = load_ml_results()
        widget = self.query_one("#round-history", Static)
        if not results:
            widget.update("[dim]No ML results yet[/]")
            return
        lines = []
        for r in results[-10:]:
            score = r.get("score")
            verdict = r.get("verdict", "?")
            score_str = f"{score:.1f}" if score is not None else "--"
            color = {"SUBMIT": "green", "SKIP": "red", "VALID": "yellow"}.get(verdict, "white")
            lines.append(f" [{color}]{verdict:<8}[/] Score: {score_str}")
        widget.update("\n".join(lines))


class MLExplorerView(Container):
    """ML Explorer tab with terrain grid and round history."""

    def compose(self) -> ComposeResult:
        with Horizontal(classes="ml-layout"):
            yield RoundHistory(classes="card side-panel")
            yield TerrainGridWidget(classes="card main-panel")

    def refresh_data(self) -> None:
        for w in self.query(TerrainGridWidget):
            w.refresh_data()
        for w in self.query(RoundHistory):
            w.refresh_data()
