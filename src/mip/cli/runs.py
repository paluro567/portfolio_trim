"""`mip runs` — ingestion run audit trail."""

import typer

from mip.cli._deps import open_session_factory
from mip.core.db import session_scope

app = typer.Typer(help="Ingestion run history.", no_args_is_help=True)


@app.command("list")
def list_(limit: int = typer.Option(20, "--limit", "-n", help="Runs to show.")) -> None:
    """Show recent ingestion runs, newest first."""
    from mip.repositories.ingestion_runs import IngestionRunRepository

    factory = open_session_factory()
    with session_scope(factory) as session:
        runs = IngestionRunRepository(session).recent(limit)
        if not runs:
            typer.echo("No ingestion runs yet.")
            raise typer.Exit()

        typer.echo(
            f"{'ID':>5} {'TYPE':13} {'PROVIDER':9} {'STATUS':8} "
            f"{'STARTED (UTC)':20} {'INS':>6} {'UPD':>6} SCOPE"
        )
        for run in runs:
            started = run.started_at.strftime("%Y-%m-%d %H:%M:%S") if run.started_at else "-"
            scope = (run.scope or "")[:40]
            typer.echo(
                f"{run.id:5} {run.run_type.value:13} {run.provider:9} {run.status.value:8} "
                f"{started:20} {run.rows_inserted:6} {run.rows_updated:6} {scope}"
            )
