"""Tab 4: CV Status - submissions, profiler, training progress."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Container
from textual.widgets import Static, Label, DataTable

from data import load_cv_results, load_cv_training_log, load_agent_status


class CVSubmissions(Static):
    """CV submission results table."""

    def compose(self) -> ComposeResult:
        yield Label("CV SUBMISSIONS", classes="card-title")
        yield Static(id="cv-subs")

    def refresh_data(self) -> None:
        results = load_cv_results()
        widget = self.query_one("#cv-subs", Static)
        if not results:
            widget.update("[dim]No CV results yet[/]")
            return

        lines = [" #  Detection  Classif.  Combined  Verdict"]
        lines.append(" " + "-" * 48)
        for i, r in enumerate(results, 1):
            det = r.get("detection_mAP", 0)
            cls = r.get("classification_mAP", 0)
            combined = r.get("combined_score", 0)
            verdict = r.get("verdict", "?")
            color = {"SUBMIT": "green", "SKIP": "red", "RISKY": "yellow"}.get(verdict, "white")
            lines.append(
                f" {i:>2}  {det:>8.4f}  {cls:>8.4f}  {combined:>8.4f}  [{color}]{verdict}[/]"
            )

        status = load_agent_status("agent-cv")
        subs = status.get("submissions_count", 0)
        lines.append(f"\n Remaining today: {10 - subs}/10")
        widget.update("\n".join(lines))


class CVTraining(Static):
    """CV training progress from GCP."""

    def compose(self) -> ComposeResult:
        yield Label("TRAINING", classes="card-title")
        yield Static(id="cv-training")

    def refresh_data(self) -> None:
        log = load_cv_training_log()
        widget = self.query_one("#cv-training", Static)
        if not log:
            widget.update("[dim]No training data[/]")
            return

        # Show latest entries
        lines = []
        for entry in log[-8:]:
            if isinstance(entry, dict):
                epoch = entry.get("epoch", "?")
                map50 = entry.get("mAP50", entry.get("map50", "?"))
                lines.append(f" Epoch {epoch}: mAP50={map50}")
            else:
                lines.append(f" {str(entry)[:60]}")
        widget.update("\n".join(lines) if lines else "[dim]No entries[/]")


class CVStatusView(Container):
    """CV status tab."""

    def compose(self) -> ComposeResult:
        with Horizontal(classes="cv-layout"):
            yield CVSubmissions(classes="card main-panel")
            yield CVTraining(classes="card side-panel")
        yield Static("[dim]0-9:tabs  r:refresh  q:quit[/]", classes="key-hints")

    def refresh_data(self) -> None:
        for w in self.query(CVSubmissions):
            w.refresh_data()
        for w in self.query(CVTraining):
            w.refresh_data()
