"""`mip attribution` — the exact accounting of a trim assessment."""

import json as json_lib

import typer

from mip.cli._deps import open_session_factory
from mip.core.db import session_scope


def attribution(
    symbol: str = typer.Argument(..., help="Symbol to attribute."),
    horizon: str = typer.Option(None, "--horizon", help="One horizon (default: 1m table view)."),
    portfolio: str = typer.Option(None, "--portfolio", help="Include portfolio overlay."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Decompose the trim score into named contributions that sum exactly
    back to it: neutral baseline, per-model evidence, portfolio overlay,
    and any clip residual."""
    from mip.engine.attribution import AttributionEngine

    factory = open_session_factory()
    with session_scope(factory) as session:
        results = AttributionEngine(session).report(symbols=[symbol], portfolio=portfolio)
        reports = results[symbol.strip().upper()]
        if horizon is not None:
            reports = [r for r in reports if r.horizon == horizon]
            if not reports:
                known = sorted({r.horizon for r in results[symbol.strip().upper()]})
                typer.echo(f"unknown horizon {horizon!r}; use one of {known}", err=True)
                raise typer.Exit(2)
        if as_json:
            payload = {reports[0].symbol: [r.to_dict() for r in reports]}
            typer.echo(json_lib.dumps(payload, indent=2))
            return

        r = reports[0] if horizon is not None else next(x for x in reports if x.horizon == "1m")
        details = {c.model_name: c for c in r.evidence_contributions}
        typer.echo(f"{r.symbol} — {r.horizon} trim attribution (as of {r.as_of})")
        typer.echo(f"\nTRIM SCORE: {r.trim_score:.2f}  confidence {r.confidence:.2f}")
        typer.echo("\nDECOMPOSITION (sums exactly to the trim score):")
        typer.echo(f"  {'neutral baseline':<28} {'':>8} {r.neutral_baseline:>8.2f}")
        for item in r.contribution_ranking:
            note = ""
            if item.kind == "model":
                c = details[item.name]
                note = (
                    f"   [{c.direction.replace('_', ' ')}; excess "
                    f"{c.expected_excess_return * 100:+.2f}pp, conf {c.confidence:.2f}]"
                )
            typer.echo(
                f"  {item.name:<28} {item.contribution:>+8.2f} {item.cumulative:>8.2f}{note}"
            )
        typer.echo(f"  {'-' * 46}")
        typer.echo(f"  {'trim score':<28} {'':>8} {r.trim_score:>8.2f}")

        typer.echo("\nSUMMARY:")
        typer.echo(f"  strongest toward trim:   {r.strongest_positive_contributor or '—'}")
        typer.echo(f"  strongest against trim:  {r.strongest_negative_contributor or '—'}")
        if r.largest_uncertainty:
            typer.echo(
                f"  largest uncertainty:     {r.largest_uncertainty['model']} "
                f"(se {r.largest_uncertainty['standard_error'] * 100:.2f}pp)"
            )
        if r.dominant_historical_regime:
            regime = r.dominant_historical_regime
            typer.echo(f"  dominant regime:         [{regime['model']}] {regime['description']}")
        typer.echo(f"  portfolio driver:        {r.dominant_portfolio_driver or '—'}")

        typer.echo(
            f"\nNOT IN THE DECOMPOSITION: neutral: "
            f"{', '.join(r.neutral_models) or 'none'}; omitted: "
            f"{', '.join(r.omitted_models) or 'none'}; "
            f"contradiction {r.contradictory_evidence:.2f}"
        )
