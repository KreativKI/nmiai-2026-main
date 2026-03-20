"""Tab 1: Agents - real-time agent monitoring.

Shows what each agent is doing, WHY, and next step.
Reads from status.json + plan.md per agent.
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Static, Label

from data import load_agent_context, load_intelligence_messages


class AgentPanel(Static):
    """Status panel for a single agent with what/why/next."""

    AGENT_META = {
        "agent-cv": ("CV Agent", "Object Detection", "yellow"),
        "agent-ml": ("ML Agent", "Norse World Prediction", "cyan"),
        "agent-nlp": ("NLP Agent", "AI Accounting Bot", "green"),
        "agent-ops": ("Ops Agent", "Butler / Tools", "blue"),
    }

    def __init__(self, agent_id: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.agent_id = agent_id

    def compose(self) -> ComposeResult:
        label, task, color = self.AGENT_META.get(self.agent_id, (self.agent_id, "", "white"))
        yield Label(f"[{color}]{label}[/] [dim]{task}[/]", classes="card-title")
        yield Static(id=f"agent-panel-{self.agent_id}")

    def refresh_data(self) -> None:
        ctx = load_agent_context(self.agent_id)
        widget = self.query_one(f"#agent-panel-{self.agent_id}", Static)

        state = ctx["state"]
        state_color = {
            "active": "green", "idle": "yellow", "waiting": "blue",
        }.get(state, "red")

        conf = ctx["confidence"]
        conf_str = f"{int(conf * 100)}%" if conf else "--"

        lines = [
            f"  State: [{state_color}]{state.upper()}[/]   Confidence: {conf_str}",
            "",
        ]

        # WHAT is the agent doing
        lines.append(f"  [bold]Doing:[/]  {ctx['what']}")

        # WHY (from plan.md approach reasoning)
        if ctx["why"]:
            why_text = ctx["why"][:65]
            lines.append(f"  [bold]Why:[/]    {why_text}")

        # Approach
        if ctx["approach"] and ctx["approach"] != "--":
            lines.append(f"  [bold]How:[/]    {ctx['approach'][:50]}")

        # NEXT step
        if ctx["next_step"]:
            lines.append(f"  [bold]Next:[/]   {ctx['next_step'][:50]}")

        # Notes (from status.json)
        if ctx["notes"]:
            lines.append("")
            lines.append(f"  [dim]{ctx['notes'][:70]}[/]")

        # Endpoint for NLP
        if ctx["endpoint"]:
            lines.append(f"  Endpoint: [cyan]{ctx['endpoint'][:50]}[/]")

        # Timestamp
        if ctx["timestamp"]:
            ts = ctx["timestamp"][:16]
            lines.append(f"  [dim]Last update: {ts}[/]")

        widget.update("\n".join(lines))


class IntelligenceFeed(Static):
    """Recent intelligence messages across all agents."""

    def compose(self) -> ComposeResult:
        yield Label("INTELLIGENCE FEED [dim](messages between agents)[/]", classes="card-title")
        yield Static(id="intel-feed")

    def refresh_data(self) -> None:
        msgs = load_intelligence_messages()
        widget = self.query_one("#intel-feed", Static)
        msgs.sort(key=lambda m: m["modified"], reverse=True)

        lines = []
        for m in msgs[:12]:
            ts = m["modified"].strftime("%H:%M")
            target = m["target"].replace("for-", "")
            color = {
                "cv-agent": "yellow", "ml-agent": "cyan",
                "nlp-agent": "green", "ops-agent": "blue",
                "overseer": "magenta", "jc": "bold white",
            }.get(target, "dim")
            lines.append(f" {ts} [{color}]->{target}[/]: {m['filename']}")

        widget.update("\n".join(lines) if lines else "[dim]No messages[/]")


class AgentsView(Container):
    """Agent monitoring tab with 4 panels + intelligence feed."""

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
