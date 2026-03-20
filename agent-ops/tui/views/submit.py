"""Tab 6: Submit - cross-track submission control."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Container
from textual.widgets import Static, Label

from data import (
    load_nlp_submissions, load_cv_results, load_ml_results, load_agent_status,
)


class SubmitView(Container):
    """Cross-track submission control panel."""

    def compose(self) -> ComposeResult:
        with Horizontal(classes="submit-layout"):
            yield Static(id="submit-nlp", classes="card")
            yield Static(id="submit-cv", classes="card")
            yield Static(id="submit-ml", classes="card")

    def refresh_data(self) -> None:
        # NLP
        nlp_w = self.query_one("#submit-nlp", Static)
        nlp_subs = load_nlp_submissions()
        nlp_status = load_agent_status("agent-nlp")
        endpoint = nlp_status.get("endpoint", "N/A")
        nlp_w.update(
            "[bold]NLP Submissions[/]\n"
            f"Budget: {300 - len(nlp_subs)}/300 remaining\n"
            f"Endpoint: {'[green]HEALTHY[/]' if endpoint != 'N/A' else '[red]DOWN[/]'}\n\n"
            f"Last: {len(nlp_subs)} total submissions\n"
            f"Auto-submit: available (225 max/day)"
        )

        # CV
        cv_w = self.query_one("#submit-cv", Static)
        cv_results = load_cv_results()
        cv_status = load_agent_status("agent-cv")
        cv_subs = cv_status.get("submissions_count", 0)
        best_cv = max((r.get("combined_score", 0) for r in cv_results), default=0)
        cv_w.update(
            "[bold]CV Submissions[/]\n"
            f"Budget: {10 - cv_subs}/10 remaining\n"
            f"Best: {best_cv:.4f}\n\n"
            "Validate before upload:\n"
            " 1. validate_cv_zip.py\n"
            " 2. cv_profiler.py\n"
            " 3. cv_judge.py"
        )

        # ML
        ml_w = self.query_one("#submit-ml", Static)
        ml_results = load_ml_results()
        ml_status = load_agent_status("agent-ml")
        ml_w.update(
            "[bold]ML Submissions[/]\n"
            f"API: automatic (REST)\n"
            f"Phase: {ml_status.get('phase', '--')}\n\n"
            f"Results: {len(ml_results)} logged\n"
            f"State: {ml_status.get('state', '--')}"
        )
