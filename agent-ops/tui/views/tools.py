"""Tab 7: Tools - shared tool launcher."""

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Static, Label


TOOLS = [
    ("cv_judge.py", "Score CV submission (det + cls mAP)"),
    ("ml_judge.py", "Validate + score ML predictions"),
    ("cv_profiler.py", "Check if submission fits 300s timeout"),
    ("ab_compare.py", "Compare two prediction sets"),
    ("batch_eval.py", "Rank all CV submissions"),
    ("oracle_sim.py", "Theoretical ceiling per track"),
    ("fetch_leaderboard.py", "Fetch live leaderboard from API"),
    ("nlp_auto_submit.py", "NLP auto-submitter"),
    ("validate_cv_zip.py", "Validate CV ZIP structure"),
]


class ToolsView(Container):
    """Tool launcher tab."""

    def compose(self) -> ComposeResult:
        yield Label("SHARED TOOLS", classes="card-title")
        yield Static(id="tools-list")
        yield Label("OUTPUT", classes="card-title")
        yield Static(id="tools-output", classes="output-panel")

    def on_mount(self) -> None:
        self.refresh_data()

    def refresh_data(self) -> None:
        widget = self.query_one("#tools-list", Static)
        lines = []
        for i, (name, desc) in enumerate(TOOLS, 1):
            lines.append(f" [{i}] [bold]{name:<22}[/] {desc}")
        lines.append("")
        lines.append(" [dim]Tools are in shared/tools/. Run from terminal.[/]")
        widget.update("\n".join(lines))
