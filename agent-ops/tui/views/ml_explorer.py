"""Tab 3: ML Explorer - terrain grid with legend and round history.

Reference layout:
  Left: round history + experiment table
  Center: terrain grid (40x40, row/col numbers, colored symbols)
  Right: terrain legend + viewport stats + settlement counts
  Top: seed selector tabs
  Bottom: keyboard hints
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Static, Label

from data import load_viz_data, load_ml_results
from terrain import (
    render_terrain_grid_rich, render_terrain_legend,
    render_viewport_stats, render_settlement_stats, count_terrain,
)


class SeedSelector(Static):
    """Seed selector buttons matching reference style."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.active_seed = 0
        self.seed_count = 5

    def render_bar(self) -> str:
        parts = []
        for i in range(self.seed_count):
            if i == self.active_seed:
                parts.append(f"[bold white on #2a5080] Seed {i} [/]")
            else:
                parts.append(f"[dim] Seed {i} [/]")
        return " ".join(parts)

    def update_display(self, active: int, count: int) -> None:
        self.active_seed = active
        self.seed_count = count
        self.update(self.render_bar())


class RoundInfo(Static):
    """Round info header."""
    pass


class TerrainGridWidget(Static):
    """40x40 terrain grid with rich colored rendering."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.current_seed = 0
        self.current_round = None
        self._viz_cache = None

    def compose(self) -> ComposeResult:
        yield RoundInfo(id="round-info")
        yield SeedSelector(id="seed-selector")
        yield Static(id="seed-label")
        yield Static(id="terrain-display")
        yield Static(id="terrain-keys")

    def refresh_data(self) -> None:
        viz = load_viz_data()
        round_info = self.query_one("#round-info", RoundInfo)
        seed_sel = self.query_one("#seed-selector", SeedSelector)
        seed_label = self.query_one("#seed-label", Static)
        display = self.query_one("#terrain-display", Static)
        keys_hint = self.query_one("#terrain-keys", Static)

        if not viz:
            round_info.update("[bold]R[/] Astar Island Explorer")
            display.update("[dim]No terrain data loaded. Waiting for ML agent.[/]")
            return

        self._viz_cache = viz

        # Filter to valid round entries
        round_keys = sorted(
            k for k, v in viz.items()
            if isinstance(v, dict) and "seeds" in v
        )
        if self.current_round is None or self.current_round not in round_keys:
            self.current_round = round_keys[-1] if round_keys else None

        if not self.current_round:
            display.update("[dim]No rounds available[/]")
            return

        round_data = viz[self.current_round]
        seeds = round_data.get("seeds", [])
        rnum = round_data.get("round_number", "?")
        rid = self.current_round[:8] if len(self.current_round) > 8 else self.current_round

        if self.current_seed >= len(seeds):
            self.current_seed = 0

        # Round info header
        round_info.update(
            f"[bold]R[/] Astar Island Explorer\n"
            f"  Round [bold]#{rnum}[/] (active)  ID: {rid}"
        )

        # Seed selector
        seed_sel.update_display(self.current_seed, len(seeds))

        # Seed label
        seed_label.update(f"[bold]⌂[/] Seed {self.current_seed}")

        # Render the grid
        grid = seeds[self.current_seed].get("grid", [])
        rich_grid = render_terrain_grid_rich(grid)
        display.update(rich_grid)

        # Keyboard hints
        keys_hint.update(
            "[dim]1-5 seed  r refresh[/]"
        )

    def switch_seed(self, seed: int) -> None:
        if self._viz_cache:
            round_keys = sorted(
                k for k, v in self._viz_cache.items()
                if isinstance(v, dict) and "seeds" in v
            )
            if self.current_round in round_keys:
                rd = self._viz_cache[self.current_round]
                max_seeds = len(rd.get("seeds", []))
                if 0 <= seed < max_seeds:
                    self.current_seed = seed
                    self.refresh_data()


class TerrainSidebar(Static):
    """Right sidebar: legend + viewport stats + settlement info."""

    def compose(self) -> ComposeResult:
        yield Static(id="sidebar-legend")
        yield Static(id="sidebar-stats")
        yield Static(id="sidebar-settlements")

    def refresh_data(self, grid=None) -> None:
        legend_w = self.query_one("#sidebar-legend", Static)
        stats_w = self.query_one("#sidebar-stats", Static)
        settle_w = self.query_one("#sidebar-settlements", Static)

        legend_w.update(render_terrain_legend())

        if grid:
            stats_w.update(render_viewport_stats(grid))
            settle_w.update(render_settlement_stats(grid))
        else:
            stats_w.update("[dim]No grid data[/]")
            settle_w.update("")


class RoundHistory(Static):
    """Left panel: round history and ML results."""

    def compose(self) -> ComposeResult:
        yield Label("R Round History", classes="card-title")
        yield Static(id="round-history")
        yield Label("", classes="card-title")
        yield Label("R Available Rounds", classes="card-title")
        yield Static(id="round-list")

    def refresh_data(self) -> None:
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
    """ML Explorer: 3-column layout matching reference screenshot."""

    def compose(self) -> ComposeResult:
        with Horizontal(classes="ml-layout"):
            yield RoundHistory(classes="card ml-left-panel")
            yield TerrainGridWidget(classes="card ml-center-panel")
            yield TerrainSidebar(classes="card ml-right-panel")
        yield Static("[dim]1-5:seed  r:refresh  0:dashboard  q:quit[/]", classes="key-hints")

    def refresh_data(self) -> None:
        # Refresh grid
        for w in self.query(TerrainGridWidget):
            w.refresh_data()

            # Pass grid data to sidebar
            if w._viz_cache and w.current_round:
                rd = w._viz_cache.get(w.current_round, {})
                seeds = rd.get("seeds", [])
                if w.current_seed < len(seeds):
                    grid = seeds[w.current_seed].get("grid", [])
                    for sb in self.query(TerrainSidebar):
                        sb.refresh_data(grid)

        for w in self.query(RoundHistory):
            w.refresh_data()
