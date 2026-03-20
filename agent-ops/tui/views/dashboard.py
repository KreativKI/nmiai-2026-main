"""Tab 0: Dashboard - at-a-glance overview with track cards and mini leaderboard."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Static, Label

from data import (
    time_remaining, format_countdown, load_leaderboard, find_our_team,
    load_all_agent_statuses, load_nlp_submissions, load_cv_results,
    load_agent_context, load_score_history, render_sparkline,
)


class DeadlineCard(Static):
    """Countdown timers to key deadlines."""

    def compose(self) -> ComposeResult:
        yield Label("[bold]DEADLINES[/]", classes="card-title")
        yield Static(id="deadline-content")

    def refresh_data(self) -> None:
        tr = time_remaining()
        content = self.query_one("#deadline-content", Static)
        freeze = tr["freeze"]
        end = tr["end"]

        # Color based on urgency
        freeze_color = "red" if freeze < 3600 else "yellow" if freeze < 7200 else "green"
        end_color = "red" if end < 7200 else "yellow" if end < 14400 else "green"

        content.update(
            f"  FREEZE: [{freeze_color}]{format_countdown(freeze)}[/]\n"
            f"  END:    [{end_color}]{format_countdown(end)}[/]\n"
            f"  CUT-LOSS: {format_countdown(tr['cutloss'])}\n"
            f"\n"
            f"  [dim]Freeze = no new features\n"
            f"  End = competition closes[/]"
        )


class TrackCard(Static):
    """Status card for a single track with score + agent state."""

    TRACK_META = {
        "ml": ("ML - Astar Island", "agent-ml", "cyan"),
        "cv": ("CV - NorgesGruppen", "agent-cv", "yellow"),
        "nlp": ("NLP - Tripletex", "agent-nlp", "green"),
    }

    def __init__(self, track: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.track = track

    def compose(self) -> ComposeResult:
        label, _, color = self.TRACK_META.get(self.track, (self.track, "", "white"))
        yield Label(f"[{color}]{label}[/]", classes="card-title")
        yield Static(id=f"track-{self.track}")

    def refresh_data(self) -> None:
        widget = self.query_one(f"#track-{self.track}", Static)
        _, agent_id, _ = self.TRACK_META.get(self.track, ("", "", ""))
        lb = load_leaderboard()
        us = find_our_team(lb)
        ctx = load_agent_context(agent_id) if agent_id else {}

        # Find best team score in this track for comparison
        track_key = {"ml": "astar_island", "cv": "norgesgruppen", "nlp": "tripletex"}.get(self.track, "")
        our_score = float(us.get(track_key, 0) or 0) if us else 0.0
        best_score = max((float(r.get(track_key, 0) or 0) for r in lb), default=0)

        state = ctx.get("state", "?")
        state_color = {"active": "green", "idle": "yellow", "waiting": "blue"}.get(state, "red")

        lines = [
            f"  Score: [bold]{our_score:.1f}[/]  [dim](#1: {best_score:.1f})[/]",
            f"  Agent: [{state_color}]{state.upper()}[/]",
        ]

        if self.track == "ml":
            lines.append(f"  Doing: {ctx.get('what', '--')[:35]}")
        elif self.track == "cv":
            results = load_cv_results()
            best_map = max((r.get("combined_score", 0) for r in results), default=0)
            cv_status = load_all_agent_statuses().get("agent-cv", {})
            subs = cv_status.get("submissions_count", 0)
            lines.append(f"  Local mAP: {best_map:.3f}")
            lines.append(f"  Subs: {subs}/10")
        elif self.track == "nlp":
            subs = load_nlp_submissions()
            lines.append(f"  Subs: {len(subs)}/300")
            if ctx.get("endpoint"):
                lines.append(f"  Bot: [green]DEPLOYED[/]")

        # What's happening now
        lines.append(f"  [dim]{ctx.get('notes', '')[:45]}[/]")

        widget.update("\n".join(lines))


class MiniLeaderboard(Static):
    """Top 10 leaderboard with our position highlighted."""

    def compose(self) -> ComposeResult:
        yield Label("[bold]LEADERBOARD[/]", classes="card-title")
        yield Static(id="mini-lb")

    def refresh_data(self) -> None:
        lb = load_leaderboard()
        us = find_our_team(lb)
        widget = self.query_one("#mini-lb", Static)

        lines = [" [dim] #  Team                 Tripletex  Astar  NorgesGr  Total[/]"]
        for row in lb[:10]:
            team = row.get("team", "?")[:18]
            total = float(row.get("total", 0) or 0)
            nlp = float(row.get("tripletex", 0) or 0)
            ml = float(row.get("astar_island", 0) or 0)
            cv = float(row.get("norgesgruppen", 0) or 0)
            rank = row.get("rank", "?")
            is_us = "kreativ" in team.lower()
            row_text = f" {rank:>3}. {team:<18} {nlp:>8.1f} {ml:>7.1f} {cv:>8.1f} {total:>7.1f}"
            if is_us:
                lines.append(f" [bold cyan]{row_text}[/] [bold cyan]<[/]")
            else:
                lines.append(row_text
            )

        if us and isinstance(us.get("rank"), int) and us["rank"] > 10:
            lines.append(" [dim]...[/]")
            rank = us["rank"]
            team = us.get("team", "?")[:18]
            total = float(us.get("total", 0) or 0)
            nlp = float(us.get("tripletex", 0) or 0)
            ml = float(us.get("astar_island", 0) or 0)
            cv = float(us.get("norgesgruppen", 0) or 0)
            lines.append(
                f" [bold cyan]{rank:>3}. {team:<18} {nlp:>8.1f} {ml:>7.1f} {cv:>8.1f} {total:>7.1f}[/] [bold cyan]<[/]"
            )

        widget.update("\n".join(lines) if lines else "[dim]No data[/]")


class ScoreProgression(Static):
    """Score over time sparklines."""

    def compose(self) -> ComposeResult:
        yield Label("[bold]SCORE PROGRESSION[/]", classes="card-title")
        yield Static(id="score-progression")

    def refresh_data(self) -> None:
        widget = self.query_one("#score-progression", Static)
        history = load_score_history()
        if len(history) < 2:
            widget.update("[dim]Not enough data points yet[/]")
            return

        totals = [h["total"] for h in history]
        nlp_scores = [h["tripletex"] for h in history]
        ml_scores = [h["astar_island"] for h in history]
        ranks = [h["rank"] for h in history if isinstance(h["rank"], int)]

        lines = [
            f"  Total:    [bold]{totals[-1]:.1f}[/]  {render_sparkline(totals, 40)}",
            f"  ML:       [cyan]{ml_scores[-1]:.1f}[/]  {render_sparkline(ml_scores, 40)}",
            f"  NLP:      [green]{nlp_scores[-1]:.1f}[/]  {render_sparkline(nlp_scores, 40)}",
        ]
        if ranks:
            # Invert ranks for sparkline (lower=better, so show improvement as going up)
            max_rank = max(ranks) if ranks else 1
            inv_ranks = [max_rank - r for r in ranks]
            lines.append(
                f"  Rank:     [bold]#{ranks[-1]}[/]  {render_sparkline(inv_ranks, 40)}  [dim](lower=better)[/]"
            )

        ts_first = history[0].get("timestamp", "")[:16]
        ts_last = history[-1].get("timestamp", "")[:16]
        lines.append(f"  [dim]{ts_first} -> {ts_last} ({len(history)} snapshots)[/]")

        widget.update("\n".join(lines))


class DashboardView(Container):
    """Main dashboard tab."""

    def compose(self) -> ComposeResult:
        with Horizontal(classes="dashboard-top"):
            yield DeadlineCard(classes="card")
            yield TrackCard("ml", classes="card")
            yield TrackCard("cv", classes="card")
            yield TrackCard("nlp", classes="card")
        with Horizontal(classes="dashboard-bottom"):
            yield MiniLeaderboard(classes="card")
            yield ScoreProgression(classes="card")

    def refresh_data(self) -> None:
        for card in self.query(DeadlineCard):
            card.refresh_data()
        for card in self.query(TrackCard):
            card.refresh_data()
        for card in self.query(MiniLeaderboard):
            card.refresh_data()
        for card in self.query(ScoreProgression):
            card.refresh_data()
