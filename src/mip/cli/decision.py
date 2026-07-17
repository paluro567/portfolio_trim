"""`mip decision` — combined decision evidence (descriptive; no labels)."""

import json as json_lib

import typer

from mip.cli._deps import open_session_factory
from mip.core.db import session_scope

app = typer.Typer(
    help="Decision evidence: what does the total historical evidence suggest? "
    "(Never: what should I do.)",
    no_args_is_help=True,
)


def _fmt(value, spec: str = "+.2%") -> str:
    return format(value, spec) if value is not None else "—"


@app.command("evidence")
def evidence(
    symbols: list[str] = typer.Argument(None, help="Symbols to assess."),
    portfolio: str = typer.Option(None, "--portfolio", help="Assess portfolio holdings."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Combined evidence across all intelligence models, per horizon."""
    from mip.engine.evidence import DecisionEvidenceEngine

    factory = open_session_factory()
    with session_scope(factory) as session:
        results = DecisionEvidenceEngine(session).assess(
            symbols=symbols or None, portfolio=portfolio
        )
        if as_json:
            payload = {s: [e.to_dict() for e in items] for s, items in results.items()}
            typer.echo(json_lib.dumps(payload, indent=2))
            return
        for symbol, items in results.items():
            first = items[0]
            context = ""
            if first.portfolio_name:
                context = (
                    f"  [{first.portfolio_name}: weight "
                    f"{_fmt(first.portfolio_weight, '.1%')}, risk "
                    f"{_fmt(first.risk_contribution, '.0%')}]"
                )
            typer.echo(f"\n{symbol} — combined evidence (as of {first.as_of}){context}")
            typer.echo(
                f"{'HZN':>4} {'SCORE':>6} {'CONF':>5} {'STR':>5} {'CONTRA':>6} "
                f"{'EXP':>8} {'EXCESS':>8} {'N_EFF':>6} {'MODELS':>7}"
            )
            for e in items:
                models = f"{len(e.participating_models)}/7"
                typer.echo(
                    f"{e.horizon:>4} {e.combined_score:>6.1f} {e.combined_confidence:>5.2f} "
                    f"{e.evidence_strength:>5.2f} {e.contradictory_evidence:>6.2f} "
                    f"{_fmt(e.expected_return):>8} {_fmt(e.expected_excess_return):>8} "
                    f"{e.effective_sample_size:>6.1f} {models:>7}"
                )


@app.command("explain")
def explain(
    symbol: str = typer.Argument(..., help="Symbol to explain."),
    horizon: str = typer.Option("1m", "--horizon"),
    portfolio: str = typer.Option(None, "--portfolio"),
) -> None:
    """Full traceability for one symbol and horizon: positive and negative
    evidence, contradictions, model contributions, portfolio context,
    historical expectations, and confidence."""
    from mip.engine.evidence import DecisionEvidenceEngine

    factory = open_session_factory()
    with session_scope(factory) as session:
        results = DecisionEvidenceEngine(session).assess(symbols=[symbol], portfolio=portfolio)
        items = {e.horizon: e for e in results[symbol.strip().upper()]}
        if horizon not in items:
            typer.echo(f"unknown horizon {horizon!r}; use one of {sorted(items)}", err=True)
            raise typer.Exit(2)
        e = items[horizon]

        typer.echo(f"{e.symbol} — {e.horizon} decision evidence (as of {e.as_of})")
        typer.echo(
            f"\nCONFIDENCE: {e.combined_confidence:.2f}  strength {e.evidence_strength:.2f}"
            f"  contradiction {e.contradictory_evidence:.2f}"
            f"  effective sample {e.effective_sample_size:.1f}"
        )
        typer.echo(
            f"HISTORICAL EXPECTATIONS ({e.horizon}): return {_fmt(e.expected_return)}, "
            f"excess {_fmt(e.expected_excess_return)}, band "
            f"[{_fmt(e.expected_downside)}, {_fmt(e.expected_upside)}], "
            f"hit rate {_fmt(e.historical_hit_rate, '.0%')}"
        )

        typer.echo("\nMODEL CONTRIBUTIONS:")
        if not e.evidence_breakdown:
            typer.echo("  none — no model produced combinable evidence")
        for c in e.evidence_breakdown:
            typer.echo(
                f"  {c.model:<26} score {c.score:>5.1f}  effect {c.effect * 100:+6.2f}pp"
                f"  weight {c.weight_share:>5.1%}  contribution "
                f"{c.signed_contribution * 100:+6.2f}pp" + ("  [saturated]" if c.saturated else "")
            )
        if e.neutral_models:
            typer.echo(f"  neutral (no evidence, excluded): {', '.join(e.neutral_models)}")
        if e.omitted_models:
            typer.echo(f"  omitted (could not evaluate): {', '.join(e.omitted_models)}")

        typer.echo("\nPOSITIVE EVIDENCE:")
        if e.strongest_supporting_reason:
            r = e.strongest_supporting_reason
            typer.echo(
                f"  [{r['model']}] {r['description']} — n={r['n']}, excess "
                f"{r['excess'] * 100:+.1f}pp, hit rate {r['hit_rate'] * 100:.0f}%"
            )
        else:
            typer.echo("  none")
        typer.echo("NEGATIVE EVIDENCE:")
        if e.strongest_opposing_reason:
            r = e.strongest_opposing_reason
            typer.echo(
                f"  [{r['model']}] {r['description']} — n={r['n']}, excess "
                f"{r['excess'] * 100:+.1f}pp, hit rate {r['hit_rate'] * 100:.0f}%"
            )
        else:
            typer.echo("  none")

        typer.echo("\nCONTRADICTIONS:")
        if e.dominant_positive_models and e.dominant_negative_models:
            typer.echo(
                f"  {', '.join(e.dominant_positive_models)} point positive while "
                f"{', '.join(e.dominant_negative_models)} point negative "
                f"(contradiction {e.contradictory_evidence:.2f})"
            )
        else:
            typer.echo("  none — participating models agree in direction")

        typer.echo("\nPORTFOLIO CONSIDERATIONS:")
        if e.portfolio_name:
            typer.echo(
                f"  {e.portfolio_name}: weight {_fmt(e.portfolio_weight, '.1%')}, "
                f"risk contribution {_fmt(e.risk_contribution, '.0%')}, "
                f"diversification {_fmt(e.diversification_contribution, '+.2%')}"
            )
            for flag in e.concentration_flags:
                typer.echo(f"  - {flag}")
        else:
            typer.echo("  none (no portfolio given)")
