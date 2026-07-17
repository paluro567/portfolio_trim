"""`mip portfolio` — ledger, imports, snapshots, and portfolio analytics."""

import json as json_lib
from pathlib import Path

import typer

from mip.cli._deps import open_session_factory
from mip.core.db import session_scope

app = typer.Typer(
    help="Portfolio ledger (append-only) and portfolio intelligence.", no_args_is_help=True
)


@app.command("create")
def create(
    name: str = typer.Argument(..., help="Portfolio name."),
    description: str = typer.Option(None, "--description"),
) -> None:
    """Create a portfolio (FIFO cost basis, USD)."""
    from mip.repositories.portfolio import PortfolioRepository

    factory = open_session_factory()
    with session_scope(factory) as session:
        portfolio = PortfolioRepository(session).create_portfolio(name, description=description)
        typer.echo(f"created portfolio {portfolio.name!r} (id={portfolio.id}, FIFO, USD)")


@app.command("list")
def list_portfolios() -> None:
    """List portfolios."""
    from mip.repositories.portfolio import PortfolioRepository

    factory = open_session_factory()
    with session_scope(factory) as session:
        portfolios = PortfolioRepository(session).list_portfolios()
        if not portfolios:
            typer.echo("no portfolios; create one with: mip portfolio create <NAME>")
            return
        for p in portfolios:
            typer.echo(f"{p.id:>3}  {p.name}  {p.cost_basis_method}  {p.base_currency}")


def _run_import(importer, file: Path, portfolio: str, dry_run: bool) -> None:
    from mip.portfolio.importers import ImportService

    factory = open_session_factory()
    with session_scope(factory) as session:
        report = ImportService(session).run(portfolio, importer, file, dry_run=dry_run)
    mode = "DRY RUN — nothing written" if report.dry_run else f"run {report.run_id}"
    typer.echo(
        f"{mode}: parsed {report.parsed}, duplicates skipped {report.duplicates}, "
        f"inserted {report.inserted}"
    )


@app.command("import")
def import_transactions(
    file: Path = typer.Argument(..., exists=True, readable=True),
    portfolio: str = typer.Option(..., "--portfolio"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate without writing."),
) -> None:
    """Import canonical transaction CSV
    (type,date,symbol,quantity,price,fees,amount[,external_id,note])."""
    from mip.portfolio.importers import GenericCsvImporter

    _run_import(GenericCsvImporter(), file, portfolio, dry_run)


@app.command("opening-balances")
def opening_balances(
    file: Path = typer.Argument(..., exists=True, readable=True),
    portfolio: str = typer.Option(..., "--portfolio"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate without writing."),
) -> None:
    """Initialize positions from current holdings (synthetic opening
    balances; CSV: symbol,as_of_date,quantity,total_cost_basis|average_cost
    [,source,notes])."""
    from mip.portfolio.importers import OpeningBalanceCsvImporter

    _run_import(OpeningBalanceCsvImporter(), file, portfolio, dry_run)


@app.command("transactions")
def transactions(portfolio: str = typer.Option(..., "--portfolio")) -> None:
    """The append-only ledger in replay order."""
    from mip.repositories.portfolio import PortfolioRepository

    factory = open_session_factory()
    with session_scope(factory) as session:
        repo = PortfolioRepository(session)
        p = repo.require_portfolio(portfolio)
        rows = repo.transactions(p.id)
        typer.echo(f"{'ID':>5} {'DATE':>10} {'TYPE':>15} {'SYMBOL':>7} {'QTY':>12} {'AMOUNT':>14}")
        for t in rows:
            symbol = t.instrument.symbol if t.instrument else "—"
            quantity = f"{t.quantity:.4f}" if t.quantity is not None else "—"
            typer.echo(
                f"{t.id:>5} {t.trade_date} {t.txn_type:>15} {symbol:>7} "
                f"{quantity:>12} {t.total_amount:>14.2f}"
            )
        typer.echo(f"{len(rows)} transactions")


@app.command("rebuild")
def rebuild(portfolio: str = typer.Option(..., "--portfolio")) -> None:
    """Rebuild lots, closures, and daily snapshots from the ledger."""
    from mip.portfolio.lots import rebuild_lots
    from mip.portfolio.snapshots import SnapshotBuilder

    factory = open_session_factory()
    with session_scope(factory) as session:
        lots, closures = rebuild_lots(session, portfolio)
        changed = SnapshotBuilder(session).build(portfolio)
        typer.echo(f"rebuilt {lots} lots, {closures} closures; {changed} snapshot rows changed")


@app.command("positions")
def positions(portfolio: str = typer.Option(..., "--portfolio")) -> None:
    """Current positions (latest snapshot)."""
    from mip.repositories.portfolio import PortfolioRepository

    factory = open_session_factory()
    with session_scope(factory) as session:
        repo = PortfolioRepository(session)
        p = repo.require_portfolio(portfolio)
        latest = repo.latest_snapshot_date(p.id)
        if latest is None:
            typer.echo("no snapshots; run: mip portfolio rebuild --portfolio " + portfolio)
            raise typer.Exit(1)
        rows = repo.snapshots_on(p.id, latest)
        typer.echo(f"positions as of {latest}")
        typer.echo(f"{'SYMBOL':>7} {'QTY':>12} {'COST':>14} {'VALUE':>14} {'UNRLZD':>12} {'WT':>7}")
        from mip.domain.models import Instrument

        for s in rows:
            symbol = session.get(Instrument, s.instrument_id).symbol
            weight = f"{float(s.weight) * 100:.1f}%" if s.weight is not None else "—"
            value = f"{s.market_value:.2f}" if s.market_value is not None else "—"
            gain = f"{s.unrealized_gain:+.2f}" if s.unrealized_gain is not None else "—"
            typer.echo(
                f"{symbol:>7} {s.quantity:>12.4f} {s.cost_basis:>14.2f} "
                f"{value:>14} {gain:>12} {weight:>7}"
            )


@app.command("analyze")
def analyze(
    portfolio: str = typer.Option(..., "--portfolio"),
    symbol: list[str] = typer.Option(None, "--symbol", help="Limit to symbols."),
    as_json: bool = typer.Option(False, "--json"),
    no_evidence: bool = typer.Option(
        False, "--no-evidence", help="Skip intelligence-model evidence (faster)."
    ),
) -> None:
    """Portfolio intelligence: concentration, correlation, risk
    contribution, drawdowns, and normalized model evidence per position.
    Descriptive only — no Hold/Trim/Sell labels."""
    from mip.portfolio.analytics import PortfolioAnalyzer

    factory = open_session_factory()
    with session_scope(factory) as session:
        assessments = PortfolioAnalyzer(session).analyze(
            portfolio, symbols=symbol or None, with_evidence=not no_evidence
        )
        if as_json:
            typer.echo(json_lib.dumps([a.to_dict() for a in assessments], indent=2))
            return
        first = assessments[0]
        typer.echo(f"{first.portfolio_name} — {len(assessments)} positions as of {first.as_of}")
        typer.echo(
            f"{'SYMBOL':>7} {'WT':>6} {'RANK':>4} {'VOL':>6} {'RISK%':>6} "
            f"{'DIV':>7} {'DD':>6} {'FLAGS':>5}"
        )
        for a in assessments:
            vol = f"{a.annualized_volatility * 100:.0f}%" if a.annualized_volatility else "—"
            risk = f"{a.risk_contribution * 100:.0f}%" if a.risk_contribution is not None else "—"
            div = (
                f"{a.diversification_contribution * 100:+.2f}"
                if a.diversification_contribution is not None
                else "—"
            )
            dd = f"{a.current_drawdown * 100:.0f}%" if a.current_drawdown is not None else "—"
            flags = len(a.concentration_flags) + len(a.correlation_flags)
            typer.echo(
                f"{a.symbol:>7} {a.portfolio_weight * 100:>5.1f}% {a.weight_rank:>4} "
                f"{vol:>6} {risk:>6} {div:>7} {dd:>6} {flags:>5}"
            )
        for a in assessments:
            if a.strengths or a.risks:
                typer.echo(f"\n{a.symbol}:")
                for s in a.strengths:
                    typer.echo(f"  + {s}")
                for r in a.risks:
                    typer.echo(f"  - {r}")
