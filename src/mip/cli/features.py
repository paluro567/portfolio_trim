"""`mip features` — build and inspect the feature store."""

import typer

from mip.cli._deps import open_session_factory
from mip.core.config import get_settings
from mip.core.db import session_scope

app = typer.Typer(help="Feature store (build, list, describe).", no_args_is_help=True)


@app.command("build")
def build(
    symbols: str = typer.Option(None, "--symbols", "-s", help="Comma-separated symbols."),
    all_instruments: bool = typer.Option(False, "--all", help="Whole universe."),
    rebuild_from: str = typer.Option(
        None, "--from", help="Full rebuild from date (YYYY-MM-DD); default: incremental."
    ),
) -> None:
    """Compute all registered features into the feature stores (idempotent)."""
    from datetime import date as date_type

    from mip.features.pipeline import FeaturePipeline

    if symbols and all_instruments:
        typer.echo("Use either --symbols or --all, not both.", err=True)
        raise typer.Exit(2)
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()] if symbols else None
    from_date = date_type.fromisoformat(rebuild_from) if rebuild_from else None

    settings = get_settings()
    factory = open_session_factory()
    with session_scope(factory) as session:
        pipeline = FeaturePipeline(session=session, settings=settings)
        run, stats = pipeline.build(symbol_list, rebuild_from=from_date)

        typer.echo(
            f"run {run.id}: {run.status.value} — {stats.features} features, "
            f"{stats.instruments} instruments, "
            f"{stats.market_rows} market rows, {stats.instrument_rows} instrument rows written"
        )
        for symbol, error in stats.errors.items():
            typer.echo(f"  FAILED {symbol}: {error}", err=True)
        failed = run.status.value == "failed"
    if failed:
        raise typer.Exit(1)


@app.command("list")
def list_() -> None:
    """List registered feature definitions with store coverage."""
    from sqlalchemy import func, select

    from mip.domain.models import FeatureStoreDaily, FeatureStoreMarketDaily
    from mip.repositories.features import FeatureRepository

    factory = open_session_factory()
    with session_scope(factory) as session:
        definitions = FeatureRepository(session).list_definitions()
        if not definitions:
            typer.echo("No feature definitions. Run: mip features build --all")
            raise typer.Exit()

        counts_instrument = dict(
            session.execute(
                select(FeatureStoreDaily.feature_id, func.count()).group_by(
                    FeatureStoreDaily.feature_id
                )
            ).all()
        )
        counts_market = dict(
            session.execute(
                select(FeatureStoreMarketDaily.feature_id, func.count()).group_by(
                    FeatureStoreMarketDaily.feature_id
                )
            ).all()
        )
        typer.echo(f"{'NAME':24} {'V':>2} {'SCOPE':10} {'ROWS':>9} DESCRIPTION")
        for d in definitions:
            rows = counts_instrument.get(d.id, 0) + counts_market.get(d.id, 0)
            typer.echo(
                f"{d.name:24} {d.version:2} {d.scope.value:10} {rows:9} {d.description[:60]}"
            )


@app.command("describe")
def describe(name: str = typer.Argument(..., help="Feature name.")) -> None:
    """Show a feature's definition, params, and store coverage."""
    from sqlalchemy import func, select

    from mip.domain.enums import FeatureScope
    from mip.domain.models import FeatureStoreDaily, FeatureStoreMarketDaily
    from mip.repositories.features import FeatureRepository

    factory = open_session_factory()
    with session_scope(factory) as session:
        definition = FeatureRepository(session).get_definition(name)
        if definition is None:
            typer.echo(f"Unknown feature {name!r}. See: mip features list", err=True)
            raise typer.Exit(1)

        typer.echo(f"{definition.name} (v{definition.version}, {definition.scope.value})")
        typer.echo(f"  {definition.description}")
        typer.echo(f"  params: {definition.params}")
        typer.echo(f"  uses_adjusted_prices: {definition.uses_adjusted_prices}")

        model = (
            FeatureStoreMarketDaily
            if definition.scope is FeatureScope.MARKET
            else FeatureStoreDaily
        )
        count, first, last = session.execute(
            select(func.count(), func.min(model.feature_date), func.max(model.feature_date)).where(
                model.feature_id == definition.id
            )
        ).one()
        typer.echo(f"  coverage: {count} rows" + (f", {first} .. {last}" if count else ""))
