"""`mip intelligence` — run intelligence models over the platform data."""

import json as json_lib

import typer

from mip.cli._deps import open_session_factory
from mip.core.db import session_scope

app = typer.Typer(help="Intelligence models (evidence-based, explainable).", no_args_is_help=True)


def _pct(value: float | None) -> str:
    return f"{value * 100:+.2f}%" if value is not None else "      —"


@app.command("rates")
def rates(
    symbols: list[str] = typer.Argument(None, help="Symbols to evaluate."),
    all_instruments: bool = typer.Option(False, "--all", help="Whole universe."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Interest Rate Sensitivity: is the current rate environment
    historically favorable for these symbols?"""
    from mip.core.exceptions import ConfigurationError
    from mip.domain.enums import InstrumentType
    from mip.models.rates import InterestRateModel
    from mip.repositories.instruments import InstrumentRepository

    if bool(symbols) == all_instruments:
        typer.echo("Provide symbols or --all (not both).", err=True)
        raise typer.Exit(2)

    factory = open_session_factory()
    with session_scope(factory) as session:
        if all_instruments:
            targets = [
                i.symbol
                for i in InstrumentRepository(session).list_instruments()
                if i.is_active and i.instrument_type is not InstrumentType.INDEX
            ]
        else:
            targets = [s.strip().upper() for s in symbols]

        model = InterestRateModel(session)
        payload = []
        failed = False
        for symbol in targets:
            try:
                scores = model.evaluate(symbol)
            except ConfigurationError as exc:
                typer.echo(f"error: {symbol}: {exc}", err=True)
                failed = True
                continue
            if as_json:
                payload.append({"symbol": symbol, "scores": [s.to_dict() for s in scores]})
            else:
                _print_scores(symbol, scores)
        if as_json:
            typer.echo(json_lib.dumps(payload, indent=2))
    if failed:
        raise typer.Exit(1)


def _print_scores(symbol: str, scores: list) -> None:
    first = scores[0]
    typer.echo(f"\n{symbol} — {first.model} v{first.model_version} (as of {first.as_of})")
    regimes = ", ".join(first.active_regimes) if first.active_regimes else "none"
    typer.echo(f"active rate regimes: {regimes}")
    typer.echo(f"{'HZN':>4} {'SCORE':>6} {'CONF':>5} {'EXP_RET':>8} {'HIT':>5} {'N':>4}")
    for s in scores:
        hit = f"{s.historical_hit_rate * 100:.0f}%" if s.historical_hit_rate is not None else "—"
        typer.echo(
            f"{s.horizon:>4} {s.score:>6.1f} {s.confidence:>5.2f} "
            f"{_pct(s.expected_return):>8} {hit:>5} {s.sample_size:>4}"
        )
    # one explanation is enough for a terminal; --json carries all horizons
    lead = max(scores, key=lambda s: abs(s.score - 50.0))
    typer.echo(f"[{lead.horizon}] {lead.explanation}")
