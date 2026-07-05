"""`mip earnings` — current earnings calendar (from v_earnings_current)."""

import typer

from mip.cli._deps import open_session_factory
from mip.core.db import session_scope

app = typer.Typer(help="Earnings calendar inspection.", no_args_is_help=True)


@app.command("calendar")
def calendar(
    symbol: str = typer.Option(None, "--symbol", "-s", help="Filter to one symbol."),
) -> None:
    """Show the current earnings calendar (latest observation per event)."""
    from mip.repositories.earnings import EarningsRepository
    from mip.repositories.instruments import InstrumentRepository

    factory = open_session_factory()
    with session_scope(factory) as session:
        instrument_id = None
        if symbol:
            instrument = InstrumentRepository(session).get_by_symbol(symbol.upper())
            if instrument is None:
                typer.echo(f"Unknown symbol {symbol!r}.", err=True)
                raise typer.Exit(1)
            instrument_id = instrument.id

        rows = EarningsRepository(session).current_calendar(instrument_id)
        if not rows:
            typer.echo("No earnings observations. Run: mip ingest earnings --all")
            raise typer.Exit()

        symbols_by_id = {i.id: i.symbol for i in InstrumentRepository(session).list_instruments()}
        typer.echo(f"{'SYMBOL':8} {'DATE':12} {'TOD':7} {'EST':>9} {'ACTUAL':>9} CONFIRMED")
        for row in rows:
            typer.echo(
                f"{symbols_by_id.get(row['instrument_id'], '?'):8} "
                f"{row['earnings_date']!s:12} {row['time_of_day'] or '-':7} "
                f"{str(row['eps_estimate'] or '-'):>9} "
                f"{str(row['eps_actual'] or '-'):>9} "
                f"{'yes' if row['is_confirmed'] else 'no'}"
            )
