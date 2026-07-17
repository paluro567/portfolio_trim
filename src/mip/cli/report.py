"""`mip report` — human-readable decision reports (text, JSON, Markdown)."""

import json as json_lib

import typer

from mip.cli._deps import open_session_factory
from mip.core.db import session_scope

app = typer.Typer(
    help="Decision reports built from trim assessments and their exact "
    "attribution — no new analysis, three output formats.",
    no_args_is_help=True,
)


def _pick_format(as_json: bool, markdown: bool) -> str:
    if as_json and markdown:
        typer.echo("choose one of --json or --markdown", err=True)
        raise typer.Exit(2)
    return "json" if as_json else "markdown" if markdown else "text"


def _options(horizon: str, top: int, min_confidence: float):
    from mip.engine.report import ReportOptions

    return ReportOptions(focus_horizon=horizon, top=top, min_confidence=min_confidence)


def _archive(session, assessments, no_archive: bool) -> None:
    """Reports publish predictions; publishing archives them (immutably)."""
    if no_archive:
        return
    from mip.evaluation.archive import PredictionArchiver

    result = PredictionArchiver(session).archive(assessments)
    typer.echo(
        f"(archived {result.inserted} new prediction(s); {result.skipped} already recorded)",
        err=True,
    )


@app.command("symbol")
def symbol_report(
    symbol: str = typer.Argument(..., help="Symbol to report on."),
    portfolio: str = typer.Option(None, "--portfolio", help="Include portfolio overlay."),
    horizon: str = typer.Option("1m", "--horizon", help="Deep-dive horizon."),
    top: int = typer.Option(10, "--top", help="Rows per ranked section."),
    min_confidence: float = typer.Option(0.40, "--min-confidence", help="Maintain-section gate."),
    as_json: bool = typer.Option(False, "--json", help="JSON output."),
    markdown: bool = typer.Option(False, "--markdown", help="Markdown output."),
    no_archive: bool = typer.Option(
        False, "--no-archive", help="Skip archiving these predictions."
    ),
) -> None:
    """Single-symbol decision report: all horizons, cross-horizon
    interpretation, strengths, risks, uncertainty, and exact attribution.
    The underlying assessments are archived as immutable predictions
    unless --no-archive."""
    from mip.engine.attribution import AttributionEngine
    from mip.engine.report import build_symbol_report, render_symbol_markdown, render_symbol_text

    fmt = _pick_format(as_json, markdown)
    factory = open_session_factory()
    with session_scope(factory) as session:
        pairs = AttributionEngine(session).assessed(symbols=[symbol], portfolio=portfolio)
        symbol_pairs = pairs[symbol.strip().upper()]
        report = build_symbol_report(symbol_pairs, _options(horizon, top, min_confidence))
        _archive(session, [a for a, _ in symbol_pairs], no_archive)
        if fmt == "json":
            typer.echo(json_lib.dumps(report.to_dict(), indent=2))
        elif fmt == "markdown":
            typer.echo(render_symbol_markdown(report))
        else:
            typer.echo(render_symbol_text(report))


@app.command("portfolio")
def portfolio_report(
    portfolio: str = typer.Option(..., "--portfolio", help="Portfolio to report on."),
    horizon: str = typer.Option("1m", "--horizon", help="Focus horizon for ranked sections."),
    top: int = typer.Option(10, "--top", help="Rows per ranked section."),
    min_confidence: float = typer.Option(0.40, "--min-confidence", help="Maintain-section gate."),
    as_json: bool = typer.Option(False, "--json", help="JSON output."),
    markdown: bool = typer.Option(False, "--markdown", help="Markdown output."),
    no_archive: bool = typer.Option(
        False, "--no-archive", help="Skip archiving these predictions."
    ),
) -> None:
    """Portfolio decision report: overview, seven ranked sections, and a
    summary row per holding. The underlying assessments are archived as
    immutable predictions unless --no-archive."""
    from mip.engine.attribution import AttributionEngine
    from mip.engine.report import (
        build_portfolio_report,
        render_portfolio_markdown,
        render_portfolio_text,
    )

    fmt = _pick_format(as_json, markdown)
    factory = open_session_factory()
    with session_scope(factory) as session:
        by_symbol = AttributionEngine(session).assessed(portfolio=portfolio)
        report = build_portfolio_report(
            by_symbol, portfolio, _options(horizon, top, min_confidence)
        )
        _archive(session, [a for pairs in by_symbol.values() for a, _ in pairs], no_archive)
        if fmt == "json":
            typer.echo(json_lib.dumps(report.to_dict(), indent=2))
        elif fmt == "markdown":
            typer.echo(render_portfolio_markdown(report))
        else:
            typer.echo(render_portfolio_text(report))
