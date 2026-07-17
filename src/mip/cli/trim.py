"""`mip trim` — horizon-specific trim assessments from combined evidence.

Labels summarize historical evidence; they are not trade instructions or
personalized financial advice.
"""

import json as json_lib

import typer

from mip.cli._deps import open_session_factory
from mip.core.db import session_scope

app = typer.Typer(
    help="Trim assessments: how strongly does the evidence support reducing "
    "exposure over each horizon? (Never: will the stock go down.)",
    no_args_is_help=True,
)

DISCLAIMER = "labels summarize historical evidence — not trade instructions or financial advice"


def _fmt(value, spec: str = "+.2%") -> str:
    return format(value, spec) if value is not None else "—"


@app.command("score")
def score(
    symbols: list[str] = typer.Argument(None, help="Symbols to assess."),
    portfolio: str = typer.Option(None, "--portfolio", help="Assess portfolio holdings."),
    as_of: str = typer.Option(None, "--as-of", help="Point-in-time date (YYYY-MM-DD)."),
    no_archive: bool = typer.Option(
        False, "--no-archive", help="Skip archiving these predictions."
    ),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Trim scores per horizon: evidence-only score, bounded portfolio
    adjustment, final score, and confidence-gated label. Every assessment
    is archived as an immutable prediction unless --no-archive."""
    from datetime import date as date_type

    from mip.engine.trim import TrimScoreEngine
    from mip.evaluation.archive import PredictionArchiver

    as_of_date = date_type.fromisoformat(as_of) if as_of else None
    factory = open_session_factory()
    with session_scope(factory) as session:
        results = TrimScoreEngine(session).assess(
            symbols=symbols or None, portfolio=portfolio, as_of=as_of_date
        )
        if not no_archive:
            archived = PredictionArchiver(session).archive(
                a for items in results.values() for a in items
            )
            typer.echo(
                f"(archived {archived.inserted} new prediction(s); "
                f"{archived.skipped} already recorded)",
                err=True,
            )
        if as_json:
            payload = {s: [a.to_dict() for a in items] for s, items in results.items()}
            typer.echo(json_lib.dumps(payload, indent=2))
            return
        downgrade_seen = False
        for symbol, items in results.items():
            first = items[0]
            context = ""
            if first.portfolio_name:
                context = (
                    f"  [{first.portfolio_name}: weight {_fmt(first.portfolio_weight, '.1%')}, "
                    f"risk {_fmt(first.risk_contribution, '.0%')}]"
                )
            typer.echo(f"\n{symbol} — trim assessment (as of {first.as_of}){context}")
            typer.echo(
                f"{'HZN':>4} {'TRIM':>6} {'EVID':>6} {'ADJ':>6} {'CONF':>5} "
                f"{'EXCESS':>8}  {'LABEL':<22} {'PRIMARY DRIVER'}"
            )
            for a in items:
                driver = a.primary_trim_drivers[0] if a.primary_trim_drivers else "—"
                mark = "*" if a.diagnostics.label_downgraded else ""
                downgrade_seen = downgrade_seen or bool(mark)
                typer.echo(
                    f"{a.horizon:>4} {a.trim_score:>6.1f} {a.evidence_trim_score:>6.1f} "
                    f"{a.portfolio_adjustment:>+6.1f} {a.confidence:>5.2f} "
                    f"{_fmt(a.expected_excess_return):>8}  {a.recommendation_label + mark:<22} "
                    f"{driver}"
                )
        if downgrade_seen:
            typer.echo("\n* label downgraded for insufficient confidence (raw score shown)")
        typer.echo(f"\n({DISCLAIMER})")


@app.command("explain")
def explain(
    symbol: str = typer.Argument(..., help="Symbol to explain."),
    horizon: str = typer.Option("1m", "--horizon"),
    portfolio: str = typer.Option(None, "--portfolio"),
) -> None:
    """Full trim reasoning for one symbol and horizon: score derivation,
    evidence for and against trimming, portfolio adjustment, cross-horizon
    signals, and limitations."""
    from mip.engine.trim import TrimScoreEngine

    factory = open_session_factory()
    with session_scope(factory) as session:
        results = TrimScoreEngine(session).assess(symbols=[symbol], portfolio=portfolio)
        items = {a.horizon: a for a in results[symbol.strip().upper()]}
        if horizon not in items:
            typer.echo(f"unknown horizon {horizon!r}; use one of {sorted(items)}", err=True)
            raise typer.Exit(2)
        a = items[horizon]
        d = a.diagnostics

        typer.echo(f"{a.symbol} — {a.horizon} trim assessment (as of {a.as_of})")
        typer.echo(
            f"\nTRIM SCORE: {a.trim_score:.1f}  (evidence {a.evidence_trim_score:.1f} "
            f"{a.portfolio_adjustment:+.1f} portfolio adjustment)"
        )
        gate = f"  [downgraded from {d.label_before_gate!r}]" if d.label_downgraded else ""
        typer.echo(f"LABEL: {a.recommendation_label}{gate}")
        typer.echo(f"CONFIDENCE: {a.confidence:.2f}  data quality: {a.data_quality_label}")

        typer.echo("\nEVIDENCE FOR TRIMMING:")
        contributions = {c.model: c for c in a.model_contributions}
        shown = False
        for model in a.primary_trim_drivers:
            c = contributions[model]
            typer.echo(
                f"  {model}: expected excess {c.effect * 100:+.2f}pp "
                f"(weight {c.weight_share:.1%} of combination)"
            )
            shown = True
        if a.portfolio_adjustment > 0:
            typer.echo(
                f"  portfolio: +{a.portfolio_adjustment:.1f} points "
                f"(weight term {d.weight_term:+.1f}, risk-share term {d.risk_term:+.1f})"
            )
            shown = True
        if a.strongest_supporting_reason:
            r = a.strongest_supporting_reason
            typer.echo(
                f"  strongest: [{r['model']}] {r['description']} — n={r['n']}, "
                f"excess {r['excess'] * 100:+.1f}pp, hit rate {r['hit_rate'] * 100:.0f}%"
            )
            shown = True
        if not shown:
            typer.echo("  none")

        typer.echo("EVIDENCE AGAINST TRIMMING:")
        shown = False
        for model in a.primary_hold_strengths:
            c = contributions[model]
            typer.echo(
                f"  {model}: expected excess {c.effect * 100:+.2f}pp "
                f"(weight {c.weight_share:.1%} of combination)"
            )
            shown = True
        if a.portfolio_adjustment < 0:
            typer.echo(
                f"  portfolio: {a.portfolio_adjustment:.1f} points diversification benefit "
                f"(weight term {d.weight_term:+.1f}, risk-share term {d.risk_term:+.1f})"
            )
            shown = True
        if a.strongest_opposing_reason:
            r = a.strongest_opposing_reason
            typer.echo(
                f"  strongest: [{r['model']}] {r['description']} — n={r['n']}, "
                f"excess {r['excess'] * 100:+.1f}pp, hit rate {r['hit_rate'] * 100:.0f}%"
            )
            shown = True
        if not shown:
            typer.echo("  none")

        baseline = (
            a.expected_return - a.expected_excess_return
            if None not in (a.expected_return, a.expected_excess_return)
            else None
        )
        typer.echo(
            f"\nHISTORICAL EXPECTATION ({a.horizon}): return {_fmt(a.expected_return)}, "
            f"baseline {_fmt(baseline)}, excess {_fmt(a.expected_excess_return)}, "
            f"band [{_fmt(a.expected_downside)}, {_fmt(a.expected_upside)}]"
        )
        typer.echo(
            f"EVIDENCE QUALITY: {len(a.participating_models)} participating"
            + (f" ({', '.join(a.participating_models)})" if a.participating_models else "")
            + f", {len(a.neutral_models)} neutral, {len(a.omitted_models)} omitted; "
            f"contradiction {a.contradictory_evidence:.2f}; "
            f"effective sample {a.effective_sample_size:.1f}"
        )

        typer.echo("\nPORTFOLIO ADJUSTMENT:")
        if a.portfolio_name:
            typer.echo(
                f"  {a.portfolio_name}: weight {_fmt(a.portfolio_weight, '.1%')}, "
                f"risk contribution {_fmt(a.risk_contribution, '.0%')}, "
                f"diversification {_fmt(a.diversification_contribution, '+.2%')}"
            )
            typer.echo(
                f"  adjustment {a.portfolio_adjustment:+.1f} = clip(weight term "
                f"{d.weight_term:+.1f} + risk-share term {d.risk_term:+.1f}, "
                f"±{d.adjustment_bound:.0f})" + ("  [capped]" if d.adjustment_capped else "")
            )
            for flag in a.concentration_flags:
                typer.echo(f"  - {flag}")
        else:
            typer.echo("  none (no portfolio given)")

        typer.echo("\nCROSS-HORIZON NOTES:")
        if d.cross_horizon_notes:
            for note in d.cross_horizon_notes:
                typer.echo(f"  - {note}")
        else:
            typer.echo("  none — assessments evolve smoothly across horizons")

        typer.echo("\nLIMITATIONS:")
        for note in a.limitations:
            typer.echo(f"  - {note}")
