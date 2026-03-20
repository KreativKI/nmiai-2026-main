"""Tab 0: Dashboard - at-a-glance overview."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Static, Label
from textual.reactive import reactive

from data import (
    time_remaining, format_countdown, load_leaderboard, find_our_team,
    load_all_agent_statuses, load_nlp_submissions, load_cv_results,
)


class DeadlineCard(Static):
    """Countdown timers to key deadlines."""

    def compose(self) -> ComposeResult:
        yield Label("DEADLINE", classes="card-title")
        yield Static(id="deadline-content")

    def refresh_data(self) -> None:
        tr = time_remaining()
        content = self.query_one("#deadline-content", Static)
        content.update(
            f"FREEZE: {format_countdown(tr['freeze'])}\n"
            f"END:    {format_countdown(tr['end'])}\n"
            f"\n"
            f"[dim]Cut-loss: {format_countdown(tr['cutloss'])}[/]"
        )


class TrackCard(Static):
    """Status card for a single track."""

    def __init__(self, track: str, emoji: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.track = track
        self.emoji = emoji

    def compose(self) -> ComposeResult:
        yield Label(f"{self.emoji} {self.track.upper()}", classes="card-title")
        yield Static(id=f"track-{self.track}")

    def refresh_data(self) -> None:
        widget = self.query_one(f"#track-{self.track}", Static)
        statuses = load_all_agent_statuses()

        if self.track == "ml":
            s = statuses.get("agent-ml", {})
            score = s.get("best_submitted_score", 0)
            phase = s.get("phase", "unknown")
            widget.update(
                f"Score: {score or '--'}\n"
                f"Phase: {phase}\n"
                f"Rounds: {s.get('submissions_count', 0)}\n"
                f"Obs: 0/50"
            )
        elif self.track == "cv":
            s = statuses.get("agent-cv", {})
            results = load_cv_results()
            best = max((r.get("combined_score", 0) for r in results), default=0)
            subs = s.get("submissions_count", 0)
            widget.update(
                f"Best mAP: {best:.3f}\n"
                f"Subs: {subs}/10\n"
                f"Phase: {s.get('phase', 'unknown')}\n"
                f"Approach: {s.get('approach', '--')[:20]}"
            )
        elif self.track == "nlp":
            s = statuses.get("agent-nlp", {})
            lb = load_leaderboard()
            us = find_our_team(lb)
            nlp_subs = load_nlp_submissions()
            nlp_score = us.get("tripletex", 0) if us else 0
            rank = us.get("rank", "?") if us else "?"
            widget.update(
                f"Score: {nlp_score}  #{rank}\n"
                f"Subs: {len(nlp_subs)}/300\n"
                f"Phase: {s.get('phase', 'unknown')}\n"
                f"Endpoint: {s.get('endpoint', 'N/A')[:30]}"
            )


class MiniLeaderboard(Static):
    """Top 10 leaderboard summary."""

    def compose(self) -> ComposeResult:
        yield Label("LEADERBOARD", classes="card-title")
        yield Static(id="mini-lb")

    def refresh_data(self) -> None:
        lb = load_leaderboard()
        us = find_our_team(lb)
        widget = self.query_one("#mini-lb", Static)

        lines = []
        for row in lb[:10]:
            team = row.get("team", "?")[:18]
            total = row.get("total", 0)
            rank = row.get("rank", "?")
            marker = " [bold cyan]<[/]" if "kreativ" in team.lower() else ""
            lines.append(f" {rank:>3}. {team:<18} {total:>7.2f}{marker}")

        if us and isinstance(us.get("rank"), int) and us["rank"] > 10:
            lines.append(" ...")
            rank = us.get("rank", "?")
            team = us.get("team", "?")[:18]
            total = us.get("total", 0)
            lines.append(f" {rank:>3}. {team:<18} {total:>7.2f} [bold cyan]<[/]")

        widget.update("\n".join(lines) if lines else "[dim]No data[/]")


class DashboardView(Container):
    """Main dashboard tab."""

    def compose(self) -> ComposeResult:
        with Horizontal(classes="dashboard-top"):
            yield DeadlineCard(classes="card")
            yield TrackCard("ml", "Mountain", classes="card")
            yield TrackCard("cv", "Box", classes="card")
            yield TrackCard("nlp", "Note", classes="card")
        yield MiniLeaderboard(classes="card wide-card")

    def refresh_data(self) -> None:
        for card in self.query(DeadlineCard):
            card.refresh_data()
        for card in self.query(TrackCard):
            card.refresh_data()
        for card in self.query(MiniLeaderboard):
            card.refresh_data()
