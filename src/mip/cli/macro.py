"""`mip macro` — inspect macro series and observations."""

import typer

from mip.cli._deps import open_session_factory
from mip.core.db import session_scope

app = typer.Typer(help="Macro series inspection.", no_args_is_help=True)


@app.command("list")
def list_() -> None:
    """List catalog-synced series with coverage and publication lag."""
    from mip.repositories.macro import MacroRepository

    factory = open_session_factory()
    with session_scope(factory) as session:
        repo = MacroRepository(session)
        series = repo.list_series()
        if not series:
            typer.echo("No macro series. Run: mip ingest macro --all")
            raise typer.Exit()

        typer.echo(f"{'CODE':10} {'FREQ':4} {'LAG(d)':>6} {'LATEST OBS':12} NAME")
        for s in series:
            latest = repo.latest_obs_date(s.id)
            typer.echo(
                f"{s.provider_code:10} {s.frequency:4} {s.publication_lag_days:6} "
                f"{str(latest or '-'):12} {s.name}"
            )


@app.command("show")
def show(
    code: str = typer.Argument(..., help="FRED series code, e.g. DGS10."),
    limit: int = typer.Option(12, "--limit", "-n", help="Observations to show."),
) -> None:
    """Show a series' metadata and its most recent observations."""
    from datetime import date, timedelta

    from mip.repositories.macro import MacroRepository

    factory = open_session_factory()
    with session_scope(factory) as session:
        repo = MacroRepository(session)
        series = repo.get_series("FRED", code.upper())
        if series is None:
            typer.echo(f"Series {code!r} not found. Run: mip ingest macro --all", err=True)
            raise typer.Exit(1)

        typer.echo(f"{series.provider_code} — {series.name}")
        typer.echo(
            f"frequency={series.frequency}  units={series.units or '-'}  "
            f"seasonally_adjusted={series.seasonally_adjusted}  "
            f"publication_lag_days={series.publication_lag_days}"
        )
        typer.echo(f"{'OBS DATE':12} {'VALUE':>14}  KNOWABLE FROM")
        for obs in repo.recent_observations(series.id, limit):
            knowable = obs.obs_date + timedelta(days=series.publication_lag_days)
            marker = "" if knowable <= date.today() else "  (not yet public)"
            value = f"{obs.value}" if obs.value is not None else "NULL"
            typer.echo(f"{obs.obs_date!s:12} {value:>14}  {knowable}{marker}")
