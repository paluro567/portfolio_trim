"""`mip calendar` — build the trading calendar."""

from datetime import date, timedelta

import typer

from mip.cli._deps import open_session_factory
from mip.core.db import session_scope

app = typer.Typer(help="Trading calendar management.", no_args_is_help=True)


@app.command("build")
def build(
    from_year: int = typer.Option(2010, "--from", help="First calendar year to include."),
    to: str = typer.Option(
        None, "--to", help="Last date (YYYY-MM-DD). Default: one year from today."
    ),
    exchange: str = typer.Option("NYSE", "--exchange", help="Exchange code."),
) -> None:
    """Idempotently build trading_calendar from exchange session rules."""
    from mip.reference.calendar import build_trading_calendar

    start = date(from_year, 1, 1)
    end = date.fromisoformat(to) if to else date.today() + timedelta(days=365)

    factory = open_session_factory()
    with session_scope(factory) as session:
        count = build_trading_calendar(session, start=start, end=end, exchange=exchange)

    typer.echo(f"{exchange}: {count} trading sessions upserted for {start} .. {end}.")
