"""`mip evaluate` — prediction archive status and outcome analytics.

Measurement only: nothing here tunes, recalibrates, or feeds back into
any model.
"""

import json as json_lib

import typer

from mip.cli._deps import open_session_factory
from mip.core.db import session_scope

app = typer.Typer(
    help="Self-evaluation: archived predictions vs realized outcomes "
    "(accuracy, calibration, model usefulness, horizon reliability, regimes).",
    no_args_is_help=True,
)

NO_DATA = (
    "no matured predictions yet — predictions are archived whenever "
    "`mip trim score` or `mip report` runs; once horizons expire, run "
    "`mip evaluate matured` first"
)


def _fmt(value, spec: str = ".2f") -> str:
    return format(value, spec) if value is not None else "—"


def _evaluated_rows(session) -> list[dict]:
    from mip.evaluation.analytics import evaluated_row
    from mip.repositories.predictions import PredictionRepository

    return [
        evaluated_row(prediction, outcome, symbol)
        for prediction, outcome, symbol in PredictionRepository(session).with_outcomes()
    ]


@app.command("pending")
def pending() -> None:
    """Archived predictions whose horizon has not yet been evaluated."""
    from mip.repositories.predictions import PredictionRepository

    factory = open_session_factory()
    with session_scope(factory) as session:
        repo = PredictionRepository(session)
        rows = repo.pending()
        evaluated = len(repo.with_outcomes())
        typer.echo(f"archive: {len(rows) + evaluated} predictions ({evaluated} evaluated)")
        if not rows:
            typer.echo("pending: none")
            return
        by_horizon: dict[str, list] = {}
        for prediction, symbol in rows:
            by_horizon.setdefault(prediction.horizon, []).append((prediction, symbol))
        typer.echo(f"pending: {len(rows)}")
        typer.echo(f"{'HZN':>4} {'N':>5}  {'OLDEST AS-OF':<13} {'NEWEST AS-OF':<13} SYMBOLS")
        from mip.engine.trim import HORIZON_SESSIONS

        for horizon in HORIZON_SESSIONS:
            subset = by_horizon.get(horizon, [])
            if not subset:
                continue
            dates = [p.as_of for p, _ in subset]
            symbols = sorted({s for _, s in subset})
            preview = ", ".join(symbols[:6]) + (" …" if len(symbols) > 6 else "")
            typer.echo(
                f"{horizon:>4} {len(subset):>5}  {min(dates).isoformat():<13} "
                f"{max(dates).isoformat():<13} {preview}"
            )


@app.command("matured")
def matured() -> None:
    """Evaluate every matured prediction against realized closes
    (idempotent; predictions themselves are never modified)."""
    from mip.evaluation.outcomes import OutcomeEvaluator

    factory = open_session_factory()
    with session_scope(factory) as session:
        summary = OutcomeEvaluator(session).evaluate_matured()
        typer.echo(
            f"evaluated {summary.evaluated} matured prediction(s); "
            f"{summary.unchanged} unchanged; {summary.pending} still pending"
        )
        rows = _evaluated_rows(session)
        scored = [r for r in rows if r["direction_correct"] is not None]
        if scored:
            accuracy = sum(r["direction_correct"] for r in scored) / len(scored)
            mae = sum(r["absolute_error"] for r in scored) / len(scored)
            typer.echo(
                f"archive now holds {len(rows)} evaluated prediction(s): "
                f"direction accuracy {accuracy:.0%}, MAE {mae * 100:.2f}pp "
                f"(over {len(scored)} with combinable evidence)"
            )


@app.command("calibration")
def calibration(as_json: bool = typer.Option(False, "--json")) -> None:
    """Is confidence honest? Empirical accuracy per confidence bucket."""
    from mip.evaluation.analytics import calibration_table

    factory = open_session_factory()
    with session_scope(factory) as session:
        table = calibration_table(_evaluated_rows(session))
        if as_json:
            typer.echo(json_lib.dumps(table, indent=2))
            return
        if not any(bucket["n"] for bucket in table):
            typer.echo(NO_DATA)
            return
        typer.echo("confidence calibration (direction accuracy by stated confidence):")
        typer.echo(f"{'BUCKET':<12} {'N':>5} {'MEAN CONF':>10} {'ACCURACY':>9} {'MAE':>8}")
        for b in table:
            mae = (
                f"{b['mean_absolute_error'] * 100:.2f}pp"
                if b["mean_absolute_error"] is not None
                else "—"
            )
            typer.echo(
                f"{b['bucket']:<12} {b['n']:>5} {_fmt(b['mean_confidence']):>10} "
                f"{_fmt(b['direction_accuracy'], '.0%'):>9} {mae:>8}"
            )


@app.command("models")
def models(as_json: bool = typer.Option(False, "--json")) -> None:
    """Per-model usefulness measured against realized excess returns."""
    from mip.evaluation.analytics import model_analytics

    factory = open_session_factory()
    with session_scope(factory) as session:
        table = model_analytics(_evaluated_rows(session))
        if as_json:
            typer.echo(json_lib.dumps(table, indent=2))
            return
        if not table:
            typer.echo(NO_DATA)
            return
        typer.echo("model analytics (measurement only — weights are never changed):")
        typer.echo(
            f"{'MODEL':<26} {'N':>4} {'DIR ACC':>8} {'MAE':>8} {'INFO GAIN':>10} "
            f"{'AGREE':>6} {'CONTRA':>7} {'WEIGHT':>7}"
        )
        for m in table:
            gain = (
                f"{m['information_gain'] * 100:+.2f}pp"
                if m["information_gain"] is not None
                else "—"
            )
            mae = f"{m['mae'] * 100:.2f}pp" if m["mae"] is not None else "—"
            typer.echo(
                f"{m['model']:<26} {m['n']:>4} {_fmt(m['directional_accuracy'], '.0%'):>8} "
                f"{mae:>8} {gain:>10} {_fmt(m['agreement_rate'], '.0%'):>6} "
                f"{_fmt(m['contradiction_rate'], '.0%'):>7} {_fmt(m['avg_weight_share'], '.1%'):>7}"
            )


@app.command("horizons")
def horizons(as_json: bool = typer.Option(False, "--json")) -> None:
    """Per-horizon reliability: RMSE, MAE, direction, Sharpe, calibration."""
    from mip.evaluation.analytics import horizon_analytics

    factory = open_session_factory()
    with session_scope(factory) as session:
        table = horizon_analytics(_evaluated_rows(session))
        if as_json:
            typer.echo(json_lib.dumps(table, indent=2))
            return
        if not any(h["n"] for h in table):
            typer.echo(NO_DATA)
            return
        typer.echo("horizon analytics:")
        typer.echo(
            f"{'HZN':>4} {'N':>4} {'RMSE':>8} {'MAE':>8} {'DIR ACC':>8} {'AVG EXC':>8} "
            f"{'SHARPE':>7} {'CONF':>5} {'GAP':>6}"
        )
        for h in table:
            rmse = f"{h['rmse'] * 100:.2f}pp" if h["rmse"] is not None else "—"
            mae = f"{h['mae'] * 100:.2f}pp" if h["mae"] is not None else "—"
            excess = (
                f"{h['avg_actual_excess'] * 100:+.2f}%"
                if h["avg_actual_excess"] is not None
                else "—"
            )
            typer.echo(
                f"{h['horizon']:>4} {h['n']:>4} {rmse:>8} {mae:>8} "
                f"{_fmt(h['direction_accuracy'], '.0%'):>8} {excess:>8} "
                f"{_fmt(h['sharpe']):>7} {_fmt(h['avg_confidence']):>5} "
                f"{_fmt(h['calibration_gap'], '+.2f'):>6}"
            )


@app.command("trim")
def trim(as_json: bool = typer.Option(False, "--json")) -> None:
    """Are trim scores meaningful? Realized excess by trim bucket."""
    from mip.evaluation.analytics import trim_analytics

    factory = open_session_factory()
    with session_scope(factory) as session:
        result = trim_analytics(_evaluated_rows(session))
        if as_json:
            typer.echo(json_lib.dumps(result, indent=2))
            return
        if result["n"] == 0:
            typer.echo(NO_DATA)
            return
        typer.echo("trim-score buckets vs realized excess:")
        typer.echo(f"{'BUCKET':<9} {'N':>5} {'AVG TRIM':>9} {'AVG EXCESS':>11} {'HIT RATE':>9}")
        for b in result["buckets"]:
            excess = (
                f"{b['avg_actual_excess'] * 100:+.2f}%"
                if b["avg_actual_excess"] is not None
                else "—"
            )
            typer.echo(
                f"{b['bucket']:<9} {b['n']:>5} {_fmt(b['avg_trim_score'], '.1f'):>9} "
                f"{excess:>11} {_fmt(b['hit_rate'], '.0%'):>9}"
            )
        typer.echo(
            f"monotonic: {result['monotonic']} ({result['inversions']} inversion(s)); "
            f"rank correlation {_fmt(result['rank_correlation'], '+.2f')} "
            "(meaningful scores are negative)"
        )


@app.command("regimes")
def regimes(as_json: bool = typer.Option(False, "--json")) -> None:
    """Prediction quality by the market regime it was made in."""
    from mip.evaluation.regimes import RegimeClassifier, regime_analytics
    from mip.repositories.predictions import PredictionRepository

    factory = open_session_factory()
    with session_scope(factory) as session:
        rows = _evaluated_rows(session)
        if not rows:
            typer.echo(NO_DATA)
            return
        through = max(row["as_of"] for row in rows)
        classifier = RegimeClassifier.from_repository(PredictionRepository(session), through)
        table = regime_analytics(rows, classifier)
        if as_json:
            typer.echo(json_lib.dumps(table, indent=2))
            return
        if not table:
            typer.echo(
                "no regime labels available (needs SPY prices and FRED "
                "VIXCLS/FEDFUNDS/CPIAUCSL history covering the archived dates)"
            )
            return
        typer.echo("regime analytics (declared thresholds; environment at prediction time):")
        typer.echo(
            f"{'DIMENSION':<11} {'REGIME':<16} {'N':>4} {'DIR ACC':>8} {'MAE':>8} {'AVG EXC':>8}"
        )
        for r in table:
            mae = f"{r['mae'] * 100:.2f}pp" if r["mae"] is not None else "—"
            excess = (
                f"{r['avg_actual_excess'] * 100:+.2f}%"
                if r["avg_actual_excess"] is not None
                else "—"
            )
            typer.echo(
                f"{r['dimension']:<11} {r['regime']:<16} {r['n']:>4} "
                f"{_fmt(r['direction_accuracy'], '.0%'):>8} {mae:>8} {excess:>8}"
            )
