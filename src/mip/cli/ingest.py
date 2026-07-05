"""`mip ingest` — data ingestion commands."""

import typer

from mip.cli._deps import open_session_factory
from mip.core.config import get_settings
from mip.core.db import session_scope

app = typer.Typer(help="Data ingestion.", no_args_is_help=True)


@app.command("prices")
def prices(
    symbols: str = typer.Option(
        None, "--symbols", "-s", help="Comma-separated symbols (default: whole universe)."
    ),
    all_instruments: bool = typer.Option(False, "--all", help="Ingest the whole universe."),
    full_refresh: bool = typer.Option(
        False, "--full-refresh", help="Re-fetch full history from MIP_HISTORY_START_DATE."
    ),
) -> None:
    """Incrementally ingest daily prices (idempotent; safe to re-run)."""
    from mip.ingestion.archive import RawDataArchive
    from mip.ingestion.price_service import PriceIngestionService
    from mip.providers.yfinance.prices import YFinancePriceProvider

    if symbols and all_instruments:
        typer.echo("Use either --symbols or --all, not both.", err=True)
        raise typer.Exit(2)
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()] if symbols else None

    settings = get_settings()
    factory = open_session_factory()
    with session_scope(factory) as session:
        service = PriceIngestionService(
            session=session,
            provider=YFinancePriceProvider(),
            archive=RawDataArchive(settings.rawdata_root),
            settings=settings,
        )
        run, outcomes = service.ingest(symbol_list, full_refresh=full_refresh)

        typer.echo(f"{'SYMBOL':8} {'STATUS':7} {'INS':>5} {'UPD':>5} {'QUAR':>4} {'WARN':>4} ERROR")
        for o in outcomes:
            typer.echo(
                f"{o.symbol:8} {o.status:7} {o.inserted:5} {o.updated:5} "
                f"{o.quarantined:4} {o.warnings:4} {o.error or ''}"
            )
        typer.echo(
            f"\nrun {run.id}: {run.status.value} — "
            f"{run.rows_inserted} inserted, {run.rows_updated} updated"
        )
        failed_run = run.status.value == "failed"
    if failed_run:
        raise typer.Exit(1)


@app.command("macro")
def macro(
    series: str = typer.Option(
        None, "--series", help="Comma-separated FRED codes (must be in fred_series.yaml)."
    ),
    all_series: bool = typer.Option(False, "--all", help="Ingest every catalog series."),
    catalog_file: str = typer.Option("fred_series.yaml", "--catalog", help="Series catalog path."),
) -> None:
    """Incrementally ingest FRED macro series (idempotent; safe to re-run)."""
    from pathlib import Path

    from mip.ingestion.archive import RawDataArchive
    from mip.ingestion.fred_service import MacroIngestionService
    from mip.providers.fred.macro import FredMacroProvider
    from mip.reference.macro_catalog import parse_macro_catalog

    if series and all_series:
        typer.echo("Use either --series or --all, not both.", err=True)
        raise typer.Exit(2)
    codes = [c.strip().upper() for c in series.split(",") if c.strip()] if series else None

    settings = get_settings()
    catalog = parse_macro_catalog(Path(catalog_file))
    factory = open_session_factory()
    with session_scope(factory) as session:
        service = MacroIngestionService(
            session=session,
            provider=FredMacroProvider(settings.fred_api_key),
            archive=RawDataArchive(settings.rawdata_root),
            settings=settings,
            catalog=catalog,
        )
        run, outcomes = service.ingest(codes)

        typer.echo(
            f"{'SERIES':10} {'STATUS':7} {'INS':>5} {'UPD':>5} {'QUAR':>4} {'WARN':>4} ERROR"
        )
        for o in outcomes:
            typer.echo(
                f"{o.code:10} {o.status:7} {o.inserted:5} {o.updated:5} "
                f"{o.quarantined:4} {o.warnings:4} {o.error or ''}"
            )
        typer.echo(
            f"\nrun {run.id}: {run.status.value} — "
            f"{run.rows_inserted} inserted, {run.rows_updated} updated"
        )
        failed_run = run.status.value == "failed"
    if failed_run:
        raise typer.Exit(1)


def _run_symbol_ingestion(service_factory, symbols: str | None, all_flag: bool) -> None:
    """Shared driver for fundamentals/earnings symbol-scoped ingestion."""
    if symbols and all_flag:
        typer.echo("Use either --symbols or --all, not both.", err=True)
        raise typer.Exit(2)
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()] if symbols else None

    factory = open_session_factory()
    with session_scope(factory) as session:
        run, outcomes = service_factory(session).ingest(symbol_list)

        typer.echo(f"{'SYMBOL':8} {'STATUS':7} {'INS':>5} {'UPD':>5} {'QUAR':>4} {'WARN':>4} ERROR")
        for o in outcomes:
            typer.echo(
                f"{o.key:8} {o.status:7} {o.inserted:5} {o.updated:5} "
                f"{o.quarantined:4} {o.warnings:4} {o.error or ''}"
            )
        typer.echo(
            f"\nrun {run.id}: {run.status.value} — "
            f"{run.rows_inserted} inserted, {run.rows_updated} updated"
        )
        failed_run = run.status.value == "failed"
    if failed_run:
        raise typer.Exit(1)


@app.command("fundamentals")
def fundamentals(
    symbols: str = typer.Option(None, "--symbols", "-s", help="Comma-separated symbols."),
    all_instruments: bool = typer.Option(False, "--all", help="All active stocks."),
) -> None:
    """Snapshot company fundamentals (one dated row per instrument per day)."""
    from mip.ingestion.archive import RawDataArchive
    from mip.ingestion.fundamental_service import FundamentalIngestionService
    from mip.providers.yfinance.fundamentals import YFinanceFundamentalsProvider

    settings = get_settings()

    def build(session):
        return FundamentalIngestionService(
            session=session,
            provider=YFinanceFundamentalsProvider(),
            archive=RawDataArchive(settings.rawdata_root),
            settings=settings,
        )

    _run_symbol_ingestion(build, symbols, all_instruments)


@app.command("earnings")
def earnings(
    symbols: str = typer.Option(None, "--symbols", "-s", help="Comma-separated symbols."),
    all_instruments: bool = typer.Option(False, "--all", help="All active stocks."),
) -> None:
    """Observe earnings dates (append-only; shifted dates become new rows)."""
    from mip.ingestion.archive import RawDataArchive
    from mip.ingestion.earnings_service import EarningsIngestionService
    from mip.providers.yfinance.earnings import YFinanceEarningsProvider

    settings = get_settings()

    def build(session):
        return EarningsIngestionService(
            session=session,
            provider=YFinanceEarningsProvider(),
            archive=RawDataArchive(settings.rawdata_root),
            settings=settings,
        )

    _run_symbol_ingestion(build, symbols, all_instruments)
