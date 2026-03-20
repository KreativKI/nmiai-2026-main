"""Tab 1: Agents - real-time agent monitoring."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Static, Label

from data import load_all_agent_statuses, load_intelligence_messages


class AgentPanel(Static):
    """Status panel for a single agent."""

    AGENT_LABELS = {
        "agent-cv": ("CV Agent", "Box"),
        "agent-ml": ("ML Agent", "Mountain"),
        "agent-nlp": ("NLP Agent", "Note"),
        "agent-ops": ("Ops Agent (Butler)", "Gear"),
    }

    def __init__(self, agent_id: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.agent_id = agent_id

    def compose(self) -> ComposeResult:
        label, _ = self.AGENT_LABELS.get(self.agent_id, (self.agent_id, ""))
        yield Label(label, classes="card-title")
        yield Static(id=f"agent-panel-{self.agent_id}")

    def refresh_data(self) -> None:
        statuses = load_all_agent_statuses()
        s = statuses.get(self.agent_id, {})
        widget = self.query_one(f"#agent-panel-{self.agent_id}", Static)

        state = s.get("state", "unknown")
        state_color = {"active": "green", "idle": "yellow", "waiting": "blue"}.get(state, "red")

        lines = [
            f"State: [{state_color}]{state.upper()}[/]",
            f"Phase: {s.get('phase', '--')}",
            f"Confidence: {int(s.get('confidence', 0) * 100)}%" if s.get('confidence') else "Confidence: --",
            "",
            f"Approach: {s.get('approach', '--')[:30]}",
        ]
        if s.get("notes"):
            lines.append(f"[dim]{s['notes'][:60]}[/]")
        if s.get("endpoint"):
            lines.append(f"Endpoint: [cyan]{s['endpoint'][:40]}[/]")

        widget.update("\n".join(lines))


class IntelligenceFeed(Static):
    """Recent intelligence messages."""

    def compose(self) -> ComposeResult:
        yield Label("INTELLIGENCE FEED", classes="card-title")
        yield Static(id="intel-feed")

    def refresh_data(self) -> None:
        msgs = load_intelligence_messages()
        widget = self.query_one("#intel-feed", Static)
        # Sort by modified time, newest first
        msgs.sort(key=lambda m: m["modified"], reverse=True)
        lines = []
        for m in msgs[:10]:
            ts = m["modified"].strftime("%H:%M")
            target = m["target"].replace("for-", "")
            lines.append(f" {ts} -> {target}: {m['filename']}")
        widget.update("\n".join(lines) if lines else "[dim]No messages[/]")


class AgentsView(Container):
    """Agent monitoring tab."""

    def compose(self) -> ComposeResult:
        with Horizontal(classes="agents-grid"):
            yield AgentPanel("agent-cv", classes="card")
            yield AgentPanel("agent-ml", classes="card")
        with Horizontal(classes="agents-grid"):
            yield AgentPanel("agent-nlp", classes="card")
            yield AgentPanel("agent-ops", classes="card")
        yield IntelligenceFeed(classes="card wide-card")

    def refresh_data(self) -> None:
        for panel in self.query(AgentPanel):
            panel.refresh_data()
        for feed in self.query(IntelligenceFeed):
            feed.refresh_data()
