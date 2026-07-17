"""Interest Rate Sensitivity Model gate tests against Postgres.

Fixture: DGS10 moves in a sawtooth (29 sessions up at +2bp/day, 29 down at
-2bp/day) so threshold crossings create MANY historical episodes; DGS2 is
flat (no 2Y regimes). TEST1 is rate-sensitive by construction: it drifts
-0.10%/session while rates rise and +0.20%/session while they fall (plus a
small deterministic wobble so returns are not degenerate). Rising-rate
regimes must therefore score BELOW 50 — and every number is derivable from
the seeded arrays, not from the model."""

import math
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session, sessionmaker
from typer.testing import CliRunner

from mip.core.config import Settings
from mip.core.db import session_scope
from mip.domain.enums import InstrumentType, RunStatus
from mip.domain.models import MacroObservation, MacroSeries, TradingDay
from mip.features.pipeline import FeaturePipeline
from mip.models.rates import HORIZONS, InterestRateModel
from mip.repositories.instruments import InstrumentRepository
from mip.repositories.prices import PriceRepository
from tests.integration.test_feature_pipeline import weekdays
from tests.integration.test_research_engine import restore_logging  # noqa: F401

pytestmark = pytest.mark.integration

START = date(2024, 1, 1)
TODAY = date(2026, 7, 10)
DAYS = weekdays(START, TODAY)
CYCLE = 29  # not a multiple of 5: cycles drift across weekdays


def rising(i: int) -> bool:
    return (i // CYCLE) % 2 == 0


DGS10 = []
_level = 4.0
for i in range(len(DAYS)):
    _level += 0.02 if rising(i) else -0.02
    DGS10.append(round(_level, 6))

TEST1 = [100.0]
for i in range(1, len(DAYS)):
    base = -0.001 if rising(i) else 0.002
    TEST1.append(TEST1[-1] * (1 + base + 0.0005 * math.sin(0.7 * i)))


def expected_active_labels() -> list[str]:
    """Derived straight from the seeded DGS10 array: latest visible obs is
    the second-to-last (publication lag 1); most specific threshold wins."""
    i = len(DGS10) - 2
    labels = []
    for window in (5, 21, 63, 126):
        change = round(DGS10[i] - DGS10[i - window], 8)  # store quantizes to NUMERIC(20,8)
        for bps in (50, 25, 10):
            if change >= bps / 100:
                labels.append(f"10Y +{bps}bps/{window}d")
                break
            if change <= -bps / 100:
                labels.append(f"10Y -{bps}bps/{window}d")
                break
    return labels


@pytest.fixture()
def rate_env(
    migrated_schema: None,
    session_factory: sessionmaker[Session],
    test_database_url: str,
    tmp_path,
):
    with session_scope(session_factory) as session:
        repo = InstrumentRepository(session)
        test1 = repo.create_instrument("TEST1", InstrumentType.STOCK, effective_date=START)
        spy = repo.create_instrument("SPY", InstrumentType.ETF, effective_date=START)

        session.add_all(
            TradingDay(exchange="NYSE", calendar_date=d) for d in weekdays(START, date(2026, 7, 31))
        )

        prices = PriceRepository(session)
        for instrument, closes in (
            (test1, TEST1),
            (spy, [400 + 0.1 * i for i in range(len(DAYS))]),
        ):
            prices.insert_rows(
                [
                    {
                        "instrument_id": instrument.id,
                        "price_date": d,
                        "open": Decimal(str(round(c, 6))),
                        "high": Decimal(str(round(c * 1.01, 6))),
                        "low": Decimal(str(round(c * 0.99, 6))),
                        "close": Decimal(str(round(c, 6))),
                        "adj_close": Decimal(str(round(c, 6))),
                        "volume": 1000,
                    }
                    for d, c in zip(DAYS, closes, strict=True)
                ],
                run_id=None,
            )

        dgs10 = MacroSeries(
            provider="FRED",
            provider_code="DGS10",
            name="10y",
            frequency="D",
            publication_lag_days=1,
        )
        dgs2 = MacroSeries(
            provider="FRED",
            provider_code="DGS2",
            name="2y",
            frequency="D",
            publication_lag_days=1,
        )
        session.add_all([dgs10, dgs2])
        session.flush()
        for d, value in zip(DAYS, DGS10, strict=True):
            session.add(MacroObservation(series_id=dgs10.id, obs_date=d, value=Decimal(str(value))))
            session.add(MacroObservation(series_id=dgs2.id, obs_date=d, value=Decimal("3.5")))

    settings = Settings(
        database_url=test_database_url,
        rawdata_root=tmp_path,
        history_start_date=START,
        _env_file=None,
    )
    with session_scope(session_factory) as session:
        pipeline = FeaturePipeline(session=session, settings=settings, today=lambda: TODAY)
        run, _ = pipeline.build(["TEST1"])
        assert run.status is RunStatus.SUCCESS
    return session_factory


def evaluate(factory, symbol="TEST1", as_of=None):
    with session_scope(factory) as session:
        return InterestRateModel(session).evaluate(symbol, as_of=as_of)


# -- gates ---------------------------------------------------------------


def test_active_regimes_match_seeded_rates(rate_env) -> None:
    scores = evaluate(rate_env)
    expected = expected_active_labels()
    assert expected, "fixture must end inside an active regime"
    assert list(scores[0].active_regimes) == expected  # DGS2 flat: 10Y only


def test_rate_sensitive_stock_scores_directionally(rate_env) -> None:
    """TEST1 falls while rates rise (and vice versa) by construction: the
    score must sit on the same side of 50 as the seeded sensitivity."""
    scores = {s.horizon: s for s in evaluate(rate_env)}
    tail_rising = rising(len(DAYS) - 2)

    for horizon in ("1w", "2w", "1m"):
        s = scores[horizon]
        assert s.sample_size >= 5
        assert 0.0 <= s.score <= 100.0 and 0.0 <= s.confidence <= 1.0
        if tail_rising:
            assert s.score < 45.0, f"{horizon}: rising rates must score bearish"
            assert s.strongest_negative_regimes
            top = s.strongest_negative_regimes[0]
            assert top.excess < 0 and top.mean < top.baseline_mean
        else:
            assert s.score > 55.0, f"{horizon}: falling rates must score bullish"
            assert s.strongest_supporting_regimes


def test_explanation_cites_real_evidence(rate_env) -> None:
    scores = {s.horizon: s for s in evaluate(rate_env)}
    s = scores["1m"]
    lead = max(
        list(s.strongest_negative_regimes) + list(s.strongest_supporting_regimes),
        key=lambda e: abs(e.excess / e.se),
    )
    assert f"the {lead.n} past environments" in s.explanation
    assert f"{lead.mean * 100:+.1f}%" in s.explanation
    assert "TEST1" in s.explanation and "1m" in s.explanation


def test_point_in_time_no_future_evidence(rate_env) -> None:
    as_of = DAYS[len(DAYS) // 2]
    scores = evaluate(rate_env, as_of=as_of)
    for s in scores:
        assert s.as_of == as_of
        for evidence in s.strongest_supporting_regimes + s.strongest_negative_regimes:
            assert evidence.last_event <= as_of  # no event selected after as_of


def test_reproducible(rate_env) -> None:
    first = [s.to_dict() for s in evaluate(rate_env)]
    second = [s.to_dict() for s in evaluate(rate_env)]
    assert first == second


def test_score_stability_day_over_day(rate_env) -> None:
    """One more trading day of information must not swing the verdict."""
    latest = {s.horizon: s.score for s in evaluate(rate_env)}
    previous = {s.horizon: s.score for s in evaluate(rate_env, as_of=DAYS[-2])}
    for horizon in HORIZONS:
        assert abs(latest[horizon] - previous[horizon]) < 15.0


def test_as_of_before_stored_features_is_neutral(rate_env) -> None:
    """Regression: an as_of predating all stored features used to raise
    TypeError (empty RangeIndex vs Timestamp); it must be a neutral score."""
    scores = evaluate(rate_env, as_of=date(2023, 6, 1))
    assert [s.horizon for s in scores] == list(HORIZONS)
    for s in scores:
        assert s.as_of == date(2023, 6, 1)
        assert s.score == 50.0 and s.confidence == 0.0
        assert s.expected_return is None and s.sample_size == 0
        assert "insufficient data" in s.explanation.lower()


def test_diagnostics_expose_overlap_and_saturation(rate_env) -> None:
    scores = {s.horizon: s for s in evaluate(rate_env)}
    for horizon in ("1w", "1m", "3m"):
        s = scores[horizon]
        diag = s.diagnostics
        assert diag is not None
        assert diag.active_regimes == len(s.active_regimes)
        assert 1 <= diag.evidence_studies <= diag.active_regimes
        assert diag.max_n_eff > 0
        assert 0.0 <= diag.mean_cross_correlation <= 1.0
        assert 0.0 <= diag.agreement <= 1.0
        assert abs(diag.z_clipped) <= 4.0
        assert diag.saturated == (abs(diag.z_raw) > 4.0)
        assert s.to_dict()["diagnostics"]["saturated"] == diag.saturated
        if diag.saturated:
            assert "Score saturated" in s.explanation


def test_cli_rates_command(rate_env, monkeypatch, test_database_url, restore_logging) -> None:
    monkeypatch.setenv("MIP_DATABASE_URL", test_database_url)
    from mip.cli.main import app

    result = CliRunner().invoke(app, ["intelligence", "rates", "TEST1"])
    assert result.exit_code == 0, result.output
    assert "TEST1" in result.output and "active rate regimes" in result.output

    result = CliRunner().invoke(app, ["intelligence", "rates", "TEST1", "--json"])
    assert result.exit_code == 0, result.output
    import json

    payload = json.loads(result.output[result.output.index("[") :])
    assert payload[0]["symbol"] == "TEST1"
    assert len(payload[0]["scores"]) == len(HORIZONS)
