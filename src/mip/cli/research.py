"""`mip research` — conditional forward-return studies over the feature store."""

import json
from datetime import date as date_type
from pathlib import Path

import typer

from mip.cli._deps import open_session_factory
from mip.core.db import session_scope

app = typer.Typer(
    help="Historical research engine (query, describe, export).", no_args_is_help=True
)

FILTER_HELP = (
    "Condition '<feature> <op> <value>', e.g. 'vix_level > 25'. Repeatable (ANDed). "
    "Prefix with a symbol to condition on another instrument's feature, "
    "e.g. 'XLK:rel_ret_spy_21d > 0'."
)


def _build_query(symbol, filters, from_, to, horizons, mode):
    from mip.research import ResearchQuery, ResearchWindow, SampleMode, parse_filter
    from mip.research.query import DEFAULT_HORIZONS

    return ResearchQuery(
        symbol=symbol.strip().upper(),
        filters=tuple(parse_filter(f) for f in filters),
        window=ResearchWindow(
            start=date_type.fromisoformat(from_) if from_ else None,
            end=date_type.fromisoformat(to) if to else None,
        ),
        horizons=(
            tuple(int(h.strip()) for h in horizons.split(",")) if horizons else DEFAULT_HORIZONS
        ),
        mode=SampleMode(mode),
    )


def _run(symbol, filters, from_, to, horizons, mode):
    from mip.core.exceptions import ConfigurationError
    from mip.research import ResearchEngine

    query = _build_query(symbol, filters, from_, to, horizons, mode)
    factory = open_session_factory()
    try:
        with session_scope(factory) as session:
            return ResearchEngine(session).run(query)
    except ConfigurationError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc


def _pct(value: float | None) -> str:
    return f"{value * 100:+.2f}%" if value is not None else "     —"


@app.command("query")
def query(
    symbol: str = typer.Argument(..., help="Target symbol (forward returns measured on it)."),
    filters: list[str] = typer.Option(..., "--filter", "-f", help=FILTER_HELP),
    from_: str = typer.Option(None, "--from", help="Earliest event date (YYYY-MM-DD)."),
    to: str = typer.Option(None, "--to", help="Latest event date (YYYY-MM-DD)."),
    horizons: str = typer.Option(None, "--horizons", help="Sessions, comma-separated."),
    mode: str = typer.Option(
        "events",
        "--mode",
        help="'events' = first day of each matching episode; 'all' = every matching day.",
    ),
) -> None:
    """Run a study and print the statistical summary per horizon."""
    result = _run(symbol, filters, from_, to, horizons, mode)

    typer.echo(result.query.describe())
    typer.echo(f"events: {len(result.event_dates)}  (eligible days: {result.eligible_days})")
    if result.event_dates:
        shown = ", ".join(d.isoformat() for d in result.event_dates[:8])
        more = len(result.event_dates) - 8
        typer.echo(f"dates: {shown}" + (f" … +{more} more" if more > 0 else ""))
    typer.echo("")
    header = (
        f"{'HZN':>4} {'N':>5} {'MEAN':>8} {'MEDIAN':>8} {'HIT':>6} {'VOL':>7} "
        f"{'MAXGAIN':>8} {'MAXLOSS':>8} {'Q25':>8} {'Q75':>8} "
        f"{'CI95_LO':>8} {'CI95_HI':>8} {'BASE':>8}"
    )
    typer.echo(header)
    for horizon in result.query.horizons:
        m = result.metrics[horizon]
        base = result.baseline[horizon]
        hit = f"{m.hit_rate * 100:.0f}%" if m.hit_rate is not None else "—"
        vol = f"{m.volatility * 100:.2f}" if m.volatility is not None else "—"
        typer.echo(
            f"{horizon:>4} {m.sample_size:>5} {_pct(m.mean):>8} {_pct(m.median):>8} "
            f"{hit:>6} {vol:>7} {_pct(m.max_gain):>8} {_pct(m.max_loss):>8} "
            f"{_pct(m.q25):>8} {_pct(m.q75):>8} {_pct(m.ci_low):>8} {_pct(m.ci_high):>8} "
            f"{_pct(base.mean):>8}"
        )
    typer.echo("\nBASE = unconditional mean over all eligible days (same horizon).")


@app.command("describe")
def describe() -> None:
    """Explain query semantics and list the features available as filters."""
    from mip.repositories.features import FeatureRepository
    from mip.research.query import DEFAULT_HORIZONS, OPERATORS

    typer.echo("Research queries: forward returns of SYMBOL after historical conditions.")
    typer.echo(f"  operators: {' '.join(sorted(OPERATORS))}")
    typer.echo(f"  default horizons (sessions): {', '.join(str(h) for h in DEFAULT_HORIZONS)}")
    typer.echo("  mode 'events': first day of each matching episode (independent samples)")
    typer.echo("  mode 'all':    every matching day (overlapping windows, larger n)")
    typer.echo("  cross-symbol filter: 'XLK:rel_ret_spy_21d > 0' (sector vs SPY, etc.)")
    typer.echo("\nAvailable features (filters read the stored, publication-lag-safe values):")

    factory = open_session_factory()
    with session_scope(factory) as session:
        definitions = FeatureRepository(session).list_definitions()
        if not definitions:
            typer.echo("  none — run: mip features build --all")
            raise typer.Exit()
        for d in definitions:
            typer.echo(f"  {d.name:24} {d.scope.value:10} {d.description[:70]}")


@app.command("export")
def export(
    symbol: str = typer.Argument(..., help="Target symbol."),
    filters: list[str] = typer.Option(..., "--filter", "-f", help=FILTER_HELP),
    out: Path = typer.Option(..., "--out", "-o", help="Output file path."),
    format_: str = typer.Option(None, "--format", help="csv | json (default: by extension)."),
    from_: str = typer.Option(None, "--from", help="Earliest event date (YYYY-MM-DD)."),
    to: str = typer.Option(None, "--to", help="Latest event date (YYYY-MM-DD)."),
    horizons: str = typer.Option(None, "--horizons", help="Sessions, comma-separated."),
    mode: str = typer.Option("events", "--mode", help="'events' or 'all'."),
) -> None:
    """Run a study and write it to disk: CSV = per-event forward returns,
    JSON = full summary (query, events, metrics, baseline)."""
    fmt = (format_ or out.suffix.lstrip(".")).lower()
    if fmt not in ("csv", "json"):
        typer.echo(f"error: unsupported format {fmt!r} (csv|json)", err=True)
        raise typer.Exit(2)

    result = _run(symbol, filters, from_, to, horizons, mode)
    if fmt == "csv":
        frame = result.forward_returns.copy()
        frame.index.name = "event_date"
        frame.to_csv(out, float_format="%.8f")
    else:
        out.write_text(json.dumps(result.to_dict(), indent=2))
    typer.echo(f"wrote {len(result.event_dates)} events to {out} ({fmt})")


@app.command("analogues")
def analogues(
    symbol: str = typer.Argument(..., help="Symbol to find analogues for."),
    as_of: str = typer.Option(None, "--as-of", help="Historical date (YYYY-MM-DD)."),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """The most similar historical combined states and what followed them."""
    from datetime import date as date_type

    from mip.research.analogues import AnalogueEngine

    factory = open_session_factory()
    with session_scope(factory) as session:
        result = AnalogueEngine(session).find(
            symbol, as_of=date_type.fromisoformat(as_of) if as_of else None
        )
        if as_json:
            typer.echo(json.dumps(result.to_dict(), indent=2))
            return
        typer.echo(f"{result.symbol} — historical analogues (as of {result.as_of})")
        if result.insufficient:
            typer.echo(f"  insufficient: {result.insufficient}")
            return
        typer.echo(
            f"{'DATE':<12} {'OVERALL':>7} {'MARKET':>7} {'SECTOR':>7} "
            f"{'COMPANY':>8} {'CATALYST':>9}"
        )
        for a in result.analogues:
            sector = f"{a.sector:.2f}" if a.sector is not None else "—"
            catalyst = f"{a.catalysts:.2f}" if a.catalysts is not None else "—"
            typer.echo(
                f"{a.date.isoformat():<12} {a.overall:>7.2f} {a.market:>7.2f} "
                f"{sector:>7} {a.company:>8.2f} {catalyst:>9}"
            )
        typer.echo(
            f"\n{'HZN':>4} {'N':>3} {'W-MEAN':>8} {'MEDIAN':>8} {'P(+)':>5} {'>SPY':>5} {'MDD':>7}"
        )
        for label, o in result.outcomes.items():
            if o.n == 0:
                typer.echo(f"{label:>4}   0        —        —     —     —       —")
                continue
            beat = f"{o.p_beat_spy * 100:.0f}%" if o.p_beat_spy is not None else "—"
            typer.echo(
                f"{label:>4} {o.n:>3} {o.weighted_mean_return * 100:>+7.2f}% "
                f"{o.median_return * 100:>+7.2f}% {o.p_positive * 100:>4.0f}% {beat:>5} "
                f"{o.median_max_drawdown * 100:>6.1f}%"
            )


@app.command("environment")
def environment(
    as_of: str = typer.Option(None, "--as-of", help="Historical date (YYYY-MM-DD)."),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Deterministic market-environment labels from stored features."""
    from datetime import date as date_type

    from mip.research.analogues import AnalogueEngine

    factory = open_session_factory()
    with session_scope(factory) as session:
        labels = AnalogueEngine(session).environment(
            date_type.fromisoformat(as_of) if as_of else None
        )
        if as_json:
            typer.echo(json.dumps(labels, indent=2))
            return
        for key, value in labels.items():
            shown = f"{value:.2f}" if isinstance(value, float) else (value or "unavailable")
            typer.echo(f"{key.replace('_', ' '):<24} {shown}")


@app.command("catalysts")
def catalysts(
    symbol: str = typer.Argument(..., help="Symbol to inspect."),
    as_of: str = typer.Option(None, "--as-of", help="Historical date (YYYY-MM-DD)."),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Point-in-time catalyst snapshot (confirmed data only; unavailable is
    labeled, never estimated)."""
    from datetime import date as date_type

    from mip.research.analogues import AnalogueEngine

    factory = open_session_factory()
    with session_scope(factory) as session:
        snapshot = AnalogueEngine(session).catalyst_state(
            symbol, date_type.fromisoformat(as_of) if as_of else None
        )
        if as_json:
            typer.echo(json.dumps(snapshot, indent=2))
            return
        for key, value in snapshot.items():
            shown = f"{value:.4g}" if value is not None else "unavailable"
            typer.echo(f"{key.replace('_', ' '):<24} {shown}")
