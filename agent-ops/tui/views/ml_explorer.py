"""Tab 3: ML Explorer - terrain grid + round history."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Static, Label
from textual import on
from textual.message import Message

from data import load_viz_data, load_ml_results
from terrain import render_terrain_rich, render_terrain_compact, count_terrain, render_legend


class TerrainGridWidget(Static):
    """40x40 terrain grid with colored rendering, seed selector, legend."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.current_seed = 0
        self.current_round = None
        self._viz_cache = None

    def compose(self) -> ComposeResult:
        yield Static(id="terrain-header")
        yield Static(id="terrain-display")
        yield Static(id="terrain-legend")
        yield Static(id="terrain-stats")

    def refresh_data(self) -> None:
        viz = load_viz_data()
        header = self.query_one("#terrain-header", Static)
        display = self.query_one("#terrain-display", Static)
        legend = self.query_one("#terrain-legend", Static)
        stats = self.query_one("#terrain-stats", Static)

        if not viz:
            header.update("[bold]TERRAIN GRID[/]  [dim]No data[/]")
            display.update("[dim]No terrain data loaded. Waiting for ML agent.[/]")
            legend.update("")
            stats.update("")
            return

        self._viz_cache = viz

        # List available rounds (filter to dicts with "seeds" key)
        round_keys = sorted(
            k for k, v in viz.items()
            if isinstance(v, dict) and "seeds" in v
        )
        if self.current_round is None or self.current_round not in round_keys:
            self.current_round = round_keys[-1] if round_keys else None

        if not self.current_round or self.current_round not in viz:
            header.update("[bold]TERRAIN GRID[/]  [dim]Invalid round[/]")
            display.update("[dim]Round not found[/]")
            return

        round_data = viz[self.current_round]
        seeds = round_data.get("seeds", [])

        if self.current_seed >= len(seeds):
            header.update(f"[bold]TERRAIN GRID[/]  Round: {self.current_round}  Seed {self.current_seed} unavailable")
            display.update(f"[dim]Only {len(seeds)} seeds available[/]")
            return

        grid = seeds[self.current_seed].get("grid", [])

        # Header with round + seed info
        seed_bar = ""
        for i in range(len(seeds)):
            if i == self.current_seed:
                seed_bar += f"[bold cyan][{i}][/] "
            else:
                seed_bar += f"[dim]{i}[/] "

        round_label = self.current_round.replace("round", "R")
        header.update(
            f"[bold]TERRAIN GRID[/]  {round_label}  |  Seeds: {seed_bar} |  "
            f"[dim]Keys: 1-5=seed  <>=round[/]"
        )

        # Render the grid with full color
        rich_grid = render_terrain_rich(grid, use_bg=True)
        display.update(rich_grid)

        # Legend
        legend.update(render_legend())

        # Stats
        counts = count_terrain(grid)
        dynamic = counts.get("Settlement", 0) + counts.get("Port", 0) + counts.get("Ruin", 0)
        static = counts.get("Mountain", 0) + counts.get("Ocean", 0)
        total = sum(counts.values())
        stats.update(
            f"Cells: {total}  |  "
            f"[yellow]Settlement:{counts.get('Settlement', 0)}[/]  "
            f"[cyan]Port:{counts.get('Port', 0)}[/]  "
            f"[red]Ruin:{counts.get('Ruin', 0)}[/]  "
            f"[green]Forest:{counts.get('Forest', 0)}[/]  "
            f"[bright_white]Mountain:{counts.get('Mountain', 0)}[/]  "
            f"[blue]Ocean:{counts.get('Ocean', 0)}[/]  "
            f"[dim]Empty/Plains:{counts.get('Empty', 0) + counts.get('Plains', 0)}[/]  |  "
            f"Dynamic: {dynamic}  Static: {static}"
        )

    def switch_seed(self, seed: int) -> None:
        if self._viz_cache:
            round_data = self._viz_cache.get(self.current_round, {})
            max_seeds = len(round_data.get("seeds", []))
            if 0 <= seed < max_seeds:
                self.current_seed = seed
                self.refresh_data()

    def switch_round(self, direction: int) -> None:
        if not self._viz_cache:
            return
        keys = sorted(
            k for k, v in self._viz_cache.items()
            if isinstance(v, dict) and "seeds" in v
        )
        if not keys or self.current_round not in keys:
            return
        idx = keys.index(self.current_round)
        new_idx = max(0, min(len(keys) - 1, idx + direction))
        self.current_round = keys[new_idx]
        self.refresh_data()


class RoundHistory(Static):
    """ML round history and results."""

    def compose(self) -> ComposeResult:
        yield Label("ROUND HISTORY", classes="card-title")
        yield Static(id="round-history")
        yield Label("", classes="card-title")
        yield Label("AVAILABLE ROUNDS", classes="card-title")
        yield Static(id="round-list")

    def refresh_data(self) -> None:
        # ML judge results
        results = load_ml_results()
        widget = self.query_one("#round-history", Static)
        if not results:
            widget.update("[dim]No ML results yet[/]")
        else:
            lines = []
            for r in results[-10:]:
                score = r.get("score")
                verdict = r.get("verdict", "?")
                score_str = f"{score:.1f}" if score is not None else "--"
                color = {"SUBMIT": "green", "SKIP": "red", "VALID": "yellow"}.get(verdict, "white")
                lines.append(f" [{color}]{verdict:<8}[/] Score: {score_str}")
            widget.update("\n".join(lines))

        # Available rounds in viz data
        viz = load_viz_data()
        rlist = self.query_one("#round-list", Static)
        if not viz:
            rlist.update("[dim]No viz data[/]")
        else:
            lines = []
            for key in sorted(viz.keys()):
                rd = viz[key]
                if not isinstance(rd, dict) or "seeds" not in rd:
                    continue
                seeds = len(rd.get("seeds", []))
                rnum = rd.get("round_number", "?")
                lines.append(f" Round {rnum}: {seeds} seeds")
            rlist.update("\n".join(lines) if lines else "[dim]None[/]")


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

