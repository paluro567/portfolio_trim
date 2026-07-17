"""Prediction Archive & Outcome Evaluation against Postgres: real
archiving, immutability, maturity detection, outcome correctness, and the
seven CLI commands — end to end on the synthetic environment."""

import json
from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy import select
from typer.testing import CliRunner

from mip.core.db import session_scope
from mip.domain.models import DailyPrice, Instrument, TradingDay
from mip.engine.trim import TrimScoreEngine
from mip.evaluation.archive import PredictionArchiver
from mip.evaluation.outcomes import OutcomeEvaluator
from mip.repositories.predictions import PredictionRepository
from tests.integration.test_decision_evidence import build_features
from tests.integration.test_portfolio import (
    TODAY,
    import_everything,
    portfolio_env,  # noqa: F401
)
from tests.integration.test_research_engine import restore_logging  # noqa: F401

pytestmark = pytest.mark.integration

MATURE_AS_OF = TODAY - timedelta(days=450)  # every horizon expires before TODAY
RECENT_AS_OF = TODAY - timedelta(days=20)  # only 1w and 2w expire


def archive_assessments(session, as_of):
    assessments = TrimScoreEngine(session).assess(symbols=["AAA"], as_of=as_of)["AAA"]
    return assessments, PredictionArchiver(session).archive(assessments)


def test_archive_is_immutable_and_dedupes(portfolio_env, tmp_path) -> None:
    import_everything(portfolio_env, tmp_path)
    build_features(portfolio_env, tmp_path)
    with session_scope(portfolio_env) as session:
        assessments, first = archive_assessments(session, MATURE_AS_OF)
        assert first.inserted == 6 and first.skipped == 0

        # re-archiving the identical predictions inserts nothing
        again = PredictionArchiver(session).archive(assessments)
        assert again.inserted == 0 and again.skipped == 6

        # a conflicting prediction at the same natural key can NEVER
        # overwrite what was first archived
        tampered = replace(assessments[0], trim_score=assessments[0].trim_score + 7.0)
        forced = PredictionArchiver(session).archive([tampered])
        assert forced.inserted == 0 and forced.skipped == 1
        repo = PredictionRepository(session)
        stored = {p.horizon: p for p, _ in repo.all_predictions()}
        assert stored[assessments[0].horizon].trim_score == assessments[0].trim_score
        # archived values are the assessment's, verbatim
        for a in assessments:
            row = stored[a.horizon]
            assert row.confidence == a.confidence
            assert row.expected_excess_return == a.expected_excess_return
            assert row.recommendation_label == a.recommendation_label
            assert row.portfolio_key == "" and row.as_of == a.as_of


def test_maturity_detection_and_outcome_correctness(portfolio_env, tmp_path) -> None:
    import_everything(portfolio_env, tmp_path)
    build_features(portfolio_env, tmp_path)
    with session_scope(portfolio_env) as session:
        archive_assessments(session, MATURE_AS_OF)
        summary = OutcomeEvaluator(session).evaluate_matured()
        assert summary.evaluated == 6 and summary.pending == 0

        # idempotent: a second sweep changes nothing
        second = OutcomeEvaluator(session).evaluate_matured()
        assert second.evaluated == 0 and second.unchanged == 6 and second.pending == 0

        # hand-verify the 1w outcome against raw calendar and closes
        repo = PredictionRepository(session)
        rows = repo.with_outcomes()
        assert len(rows) == 6
        one_week = next((p, o) for p, o, _ in rows if p.horizon == "1w")
        prediction, outcome = one_week
        sessions = session.scalars(
            select(TradingDay.calendar_date).order_by(TradingDay.calendar_date)
        ).all()
        entry = max(d for d in sessions if d <= MATURE_AS_OF)
        exit_ = [d for d in sessions if d > entry][4]  # 5th session after entry
        assert outcome.entry_date == entry and outcome.exit_date == exit_
        instrument_id = session.scalar(select(Instrument.id).where(Instrument.symbol == "AAA"))
        closes = {
            d: c
            for d, c in session.execute(
                select(DailyPrice.price_date, DailyPrice.close).where(
                    DailyPrice.instrument_id == instrument_id,
                    DailyPrice.price_date.in_([entry, exit_]),
                )
            ).all()
        }
        assert outcome.entry_price == closes[entry] and outcome.exit_price == closes[exit_]
        expected_return = float(closes[exit_] / closes[entry]) - 1.0
        assert outcome.actual_return == pytest.approx(expected_return, rel=1e-9)
        if prediction.baseline_return is not None:
            assert outcome.actual_excess_return == pytest.approx(
                outcome.actual_return - prediction.baseline_return
            )
            assert outcome.prediction_error == pytest.approx(
                outcome.actual_excess_return - prediction.expected_excess_return
            )
            assert outcome.outperformed == (
                outcome.actual_excess_return > prediction.expected_excess_return
            )
        else:
            assert outcome.actual_excess_return is None
            assert outcome.direction_correct is None


def test_unexpired_horizons_stay_pending(portfolio_env, tmp_path) -> None:
    import_everything(portfolio_env, tmp_path)
    build_features(portfolio_env, tmp_path)
    with session_scope(portfolio_env) as session:
        archive_assessments(session, RECENT_AS_OF)
        summary = OutcomeEvaluator(session).evaluate_matured()
        # 20 calendar days = 14 weekday sessions: 1w and 2w matured only
        assert summary.evaluated == 2
        assert summary.pending == 4
        repo = PredictionRepository(session)
        assert {p.horizon for p, _, _ in repo.with_outcomes()} == {"1w", "2w"}
        assert {p.horizon for p, _ in repo.pending()} == {"1m", "3m", "6m", "1y"}


def test_cli_full_flow(
    portfolio_env, tmp_path, monkeypatch, test_database_url, restore_logging
) -> None:
    import_everything(portfolio_env, tmp_path)
    build_features(portfolio_env, tmp_path)
    monkeypatch.setenv("MIP_DATABASE_URL", test_database_url)
    from mip.cli.main import app

    runner = CliRunner()
    scored = runner.invoke(app, ["trim", "score", "AAA", "--as-of", MATURE_AS_OF.isoformat()])
    assert scored.exit_code == 0, scored.output
    assert "archived 6 new prediction(s)" in scored.output

    pending = runner.invoke(app, ["evaluate", "pending"])
    assert pending.exit_code == 0, pending.output
    assert "pending: 6" in pending.output

    matured = runner.invoke(app, ["evaluate", "matured"])
    assert matured.exit_code == 0, matured.output
    assert "evaluated 6 matured prediction(s)" in matured.output

    for command, marker in (
        (["evaluate", "calibration"], "confidence calibration"),
        (["evaluate", "models"], "model analytics"),
        (["evaluate", "horizons"], "horizon analytics"),
        (["evaluate", "trim"], "trim-score buckets"),
    ):
        result = runner.invoke(app, command)
        assert result.exit_code == 0, (command, result.output)
        assert marker in result.output or "no matured predictions" in result.output

    regimes = runner.invoke(app, ["evaluate", "regimes"])
    assert regimes.exit_code == 0, regimes.output
    assert "trend" in regimes.output or "no regime labels" in regimes.output

    horizons_json = runner.invoke(app, ["evaluate", "horizons", "--json"])
    assert horizons_json.exit_code == 0
    payload = json.loads(horizons_json.output[horizons_json.output.index("[") :])
    assert [h["horizon"] for h in payload] == ["1w", "2w", "1m", "3m", "6m", "1y"]
    trim_json = runner.invoke(app, ["evaluate", "trim", "--json"])
    parsed = json.loads(trim_json.output[trim_json.output.index("{") :])
    assert {"buckets", "monotonic", "rank_correlation"} <= set(parsed)

    # deterministic: the analytics report identically on a second run
    assert runner.invoke(app, ["evaluate", "horizons", "--json"]).output == horizons_json.output

    # --no-archive is honored
    quiet = runner.invoke(
        app, ["trim", "score", "AAA", "--as-of", MATURE_AS_OF.isoformat(), "--no-archive"]
    )
    assert quiet.exit_code == 0 and "archived" not in quiet.output


def test_report_cli_archives_predictions(
    portfolio_env, tmp_path, monkeypatch, test_database_url, restore_logging
) -> None:
    import_everything(portfolio_env, tmp_path)
    build_features(portfolio_env, tmp_path)
    monkeypatch.setenv("MIP_DATABASE_URL", test_database_url)
    from mip.cli.main import app

    runner = CliRunner()
    result = runner.invoke(app, ["report", "symbol", "AAA"])
    assert result.exit_code == 0, result.output
    assert "archived 6 new prediction(s)" in result.output
    with session_scope(portfolio_env) as session:
        assert len(PredictionRepository(session).all_predictions()) == 6

    again = runner.invoke(app, ["report", "symbol", "AAA"])
    assert again.exit_code == 0
    assert "archived 0 new prediction(s); 6 already recorded" in again.output
