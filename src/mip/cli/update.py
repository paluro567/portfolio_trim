"""`mip update` — the complete daily platform workflow, orchestrated."""

import json as json_lib
from datetime import date as date_type

import typer

from mip.cli._deps import open_session_factory
from mip.core.config import get_settings


def update(
    portfolio: str = typer.Option(None, "--portfolio", help="Portfolio (default from settings)."),
    as_of: str = typer.Option(None, "--as-of", help="Explicit market date (YYYY-MM-DD)."),
    force: bool = typer.Option(False, "--force", help="Rerun even if this date already updated."),
    resume: int = typer.Option(None, "--resume", help="Resume a failed/partial run by RUN_ID."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the plan; write nothing."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable run summary."),
    skip_macro: bool = typer.Option(False, "--skip-macro"),
    skip_fundamentals: bool = typer.Option(False, "--skip-fundamentals"),
    skip_earnings: bool = typer.Option(False, "--skip-earnings"),
    skip_reports: bool = typer.Option(False, "--skip-reports"),
    from_stage: str = typer.Option(None, "--from-stage", help="First stage to run."),
    to_stage: str = typer.Option(None, "--to-stage", help="Last stage to run."),
    only: str = typer.Option(None, "--only", help="Run exactly one stage."),
) -> None:
    """Refresh data, rebuild features and the portfolio, generate and
    archive predictions, evaluate matured outcomes, and write the daily
    reports — idempotently, for the latest completed trading session."""
    from mip.core.exceptions import ConfigurationError
    from mip.update.orchestrator import UpdateOrchestrator

    if only is not None:
        if from_stage or to_stage:
            typer.echo("--only cannot be combined with --from-stage/--to-stage", err=True)
            raise typer.Exit(2)
        from_stage = to_stage = only
    skip = set()
    if skip_macro:
        skip.add("macro")
    if skip_fundamentals:
        skip.add("fundamentals")
    if skip_earnings:
        skip.add("earnings")
    if skip_reports:
        skip.add("reports")

    settings = get_settings()
    orchestrator = UpdateOrchestrator(open_session_factory(), settings)
    try:
        result = orchestrator.run(
            portfolio=portfolio,
            as_of=date_type.fromisoformat(as_of) if as_of else None,
            force=force,
            resume_run_id=resume,
            dry_run=dry_run,
            skip=skip,
            from_stage=from_stage,
            to_stage=to_stage,
        )
    except ConfigurationError as exc:
        typer.echo(f"update failed: {exc}", err=True)
        raise typer.Exit(1) from None

    if as_json:
        typer.echo(json_lib.dumps(result.manifest(), indent=2))
    else:
        header = f"mip update — run {result.run_id or '—'}  [{result.status}]"
        typer.echo(header)
        typer.echo(
            f"portfolio: {result.portfolio}   market date: " f"{result.resolved_market_date or '—'}"
        )
        typer.echo(f"\n{'STAGE':<14} {'STATUS':<9} {'SECS':>7}  DETAIL")
        for name, record in result.stages.items():
            detail = record.get("detail", {})
            note = record.get("error") or ", ".join(
                f"{k}={v}" for k, v in detail.items() if not isinstance(v, (dict, list))
            )
            seconds = record.get("seconds")
            typer.echo(
                f"{name:<14} {record.get('status', '?'):<9} "
                f"{seconds if seconds is not None else '':>7}  {note[:90]}"
            )
        if result.warnings:
            typer.echo("\nwarnings:")
            for warning in result.warnings:
                typer.echo(f"  - {warning}")
        typer.echo(
            f"\npredictions archived: {result.predictions_archived}; "
            f"outcomes evaluated: {result.outcomes_evaluated}"
            + (f"; reports: {result.report_directory}" if result.report_directory else "")
        )
    if result.status == "failed":
        raise typer.Exit(1)
