"""`mip quality` — data-quality issue review workflow (D15)."""

import typer

from mip.cli._deps import open_session_factory
from mip.core.db import session_scope
from mip.domain.enums import IssueStatus

app = typer.Typer(help="Data quality issues (quarantine ledger).", no_args_is_help=True)


@app.command("list")
def list_(
    status: str = typer.Option("open", "--status", help="open | accepted | resolved | all"),
    limit: int = typer.Option(50, "--limit", "-n"),
) -> None:
    """List data-quality issues (default: open)."""
    from mip.repositories.quality import QualityRepository

    status_filter = None if status == "all" else IssueStatus(status)
    factory = open_session_factory()
    with session_scope(factory) as session:
        issues = QualityRepository(session).list_issues(status_filter, limit)
        if not issues:
            typer.echo(f"No {status} data-quality issues.")
            raise typer.Exit()

        typer.echo(f"{'ID':>5} {'SEV':7} {'STATUS':8} {'ENTITY':22} {'RULE':28} OBSERVED")
        for issue in issues:
            typer.echo(
                f"{issue.id:5} {issue.severity.value:7} {issue.status.value:8} "
                f"{issue.entity_key:22} {issue.rule:28} {issue.observed_value or ''}"
            )


@app.command("accept")
def accept(issue_id: int = typer.Argument(..., help="Issue id from `mip quality list`.")) -> None:
    """Mark an issue ACCEPTED: the flagged value is real (e.g. a genuine
    40%+ move). Acceptance suppresses re-flagging and lets the row load on
    the next ingestion of that symbol."""
    from mip.repositories.quality import QualityRepository

    factory = open_session_factory()
    with session_scope(factory) as session:
        issue = QualityRepository(session).set_status(issue_id, IssueStatus.ACCEPTED)
        if issue is None:
            typer.echo(f"No issue with id {issue_id}.", err=True)
            raise typer.Exit(1)
        typer.echo(
            f"Issue {issue.id} accepted ({issue.rule} on {issue.entity_key}). "
            "Re-run ingestion to load the suppressed row."
        )
