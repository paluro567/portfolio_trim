"""Earnings Behavior Model gate tests against Postgres.

Quarterly reports every 63 sessions, alternating a +25% EPS beat with a
-25% miss, each followed by a one-session ±5% reaction pop and then a
40-session drift whose DIRECTION defines the stock's behavioral archetype:

  EARN1 trend-follower: beats -> +0.6%/day, misses -> -0.5%/day
  EARN2 fader/reverser: beats -> -0.4%/day, misses -> +0.5%/day
  EARN3 thin history:  EARN1's prices but only its last 3 reports seeded

Every expected direction is known by construction; a small deterministic
wobble keeps forward returns non-degenerate."""

import math
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session, sessionmaker
from typer.testing import CliRunner

from mip.core.config import Settings
from mip.core.db import session_scope
from mip.domain.enums import InstrumentType, RunStatus
from mip.domain.models import EarningsObservation, TradingDay
from mip.features.pipeline import FeaturePipeline
from mip.features.registry import build_registry
from mip.models.earnings import EVENT_WINDOW_DAYS, HORIZONS, EarningsBehaviorModel
from mip.repositories.features import FeatureRepository
from mip.repositories.instruments import InstrumentRepository
from mip.repositories.prices import PriceRepository
from tests.integration.test_feature_pipeline import weekdays
from tests.integration.test_research_engine import restore_logging  # noqa: F401

pytestmark = pytest.mark.integration

START = date(2019, 1, 1)
TODAY = date(2026, 7, 10)
DAYS = weekdays(START, TODAY)
N = len(DAYS)

NEW_FEATURES = ("gap_1d",)

EVENTS = list(range(30, N - 5, 63))  # quarterly report sessions
BEATS = [e for k, e in enumerate(EVENTS) if k % 2 == 0]
MISSES = [e for k, e in enumerate(EVENTS) if k % 2 == 1]
DRIFT_LEN = 40
POP = 0.05


def _prices(beat_drift: float, miss_drift: float) -> list[float]:
    """Reaction pop the session after each report, then a 40-session drift
    whose sign encodes the archetype, then a quiet crawl to the next one."""
    values = [100.0]
    for i in range(1, N):
        move = 0.0002
        for e in EVENTS:
            if i == e + 1:
                move = POP if e in BEATS else -POP
                break
            if e + 1 < i <= e + DRIFT_LEN:
                move = beat_drift if e in BEATS else miss_drift
                break
        values.append(values[-1] * (1 + move + 0.0004 * math.sin(0.9 * i)))
    return [round(v, 6) for v in values]


EARN1 = _prices(+0.006, -0.005)  # trend-follower
EARN2 = _prices(-0.004, +0.005)  # fader/reverser
SPY = [round(400.0 * 1.0003**i, 6) for i in range(N)]

LAST_BEAT = max(e for e in BEATS if e + 3 < N)
LAST_MISS = max(e for e in MISSES if e + 3 < N)
BEAT_AS_OF = DAYS[LAST_BEAT + 3]
MISS_AS_OF = DAYS[LAST_MISS + 3]


@pytest.fixture()
def earnings_env(
    migrated_schema: None,
    session_factory: sessionmaker[Session],
    test_database_url: str,
    tmp_path,
):
    with session_scope(session_factory) as session:
        repo = InstrumentRepository(session)
        spy = repo.create_instrument("SPY", InstrumentType.ETF, effective_date=START)
        earn1 = repo.create_instrument("EARN1", InstrumentType.STOCK, effective_date=START)
        earn2 = repo.create_instrument("EARN2", InstrumentType.STOCK, effective_date=START)
        earn3 = repo.create_instrument("EARN3", InstrumentType.STOCK, effective_date=START)

        session.add_all(
            TradingDay(exchange="NYSE", calendar_date=d) for d in weekdays(START, date(2026, 7, 31))
        )

        prices = PriceRepository(session)
        for instrument, closes in ((spy, SPY), (earn1, EARN1), (earn2, EARN2), (earn3, EARN1)):
            prices.insert_rows(
                [
                    {
                        "instrument_id": instrument.id,
                        "price_date": d,
                        "open": Decimal(str(c)),  # open == close: gap_1d == 1d move
                        "high": Decimal(str(round(c * 1.01, 6))),
                        "low": Decimal(str(round(c * 0.99, 6))),
                        "close": Decimal(str(c)),
                        "adj_close": Decimal(str(c)),
                        "volume": 1000,
                    }
                    for d, c in zip(DAYS, closes, strict=True)
                ],
                run_id=None,
            )

        def report(instrument_id: int, e: int) -> EarningsObservation:
            actual = 1.25 if e in BEATS else 0.75
            return EarningsObservation(
                instrument_id=instrument_id,
                earnings_date=DAYS[e],
                observed_at=datetime.combine(
                    DAYS[e] + timedelta(days=1), datetime.min.time(), tzinfo=UTC
                ),
                time_of_day="AMC",
                eps_estimate=Decimal("1.00"),
                eps_actual=Decimal(str(actual)),
                is_confirmed=True,
            )

        for e in EVENTS:
            session.add(report(earn1.id, e))
            session.add(report(earn2.id, e))
        for e in EVENTS[-3:]:  # EARN3: too little history to score
            session.add(report(earn3.id, e))

    settings = Settings(
        database_url=test_database_url,
        rawdata_root=tmp_path,
        history_start_date=START,
        _env_file=None,
    )
    with session_scope(session_factory) as session:
        pipeline = FeaturePipeline(session=session, settings=settings, today=lambda: TODAY)
        run, _ = pipeline.build(["EARN1", "EARN2", "EARN3", "SPY"])
        assert run.status is RunStatus.SUCCESS
    return session_factory


def evaluate(factory, symbol, as_of=None):
    with session_scope(factory) as session:
        return EarningsBehaviorModel(session).evaluate(symbol, as_of=as_of)


def test_fixture_shape() -> None:
    assert len(EVENTS) >= 28  # ~7 years of quarters
    assert len(BEATS) >= 13 and len(MISSES) >= 13
    assert (BEAT_AS_OF - DAYS[LAST_BEAT]).days <= EVENT_WINDOW_DAYS


# -- the four behavioral archetypes, known by construction -------------------------


def test_post_beat_continuation(earnings_env) -> None:
    scores = {s.horizon: s for s in evaluate(earnings_env, "EARN1", as_of=BEAT_AS_OF)}
    s = scores["1m"]
    assert "large beat" in s.active_regimes
    assert "rally after report" in s.active_regimes  # pop is inside ret_5d by day 3
    assert "beat in bull market" in s.active_regimes
    # ON the gap session itself, the gap regime is the most specific reaction
    on_gap_day = evaluate(earnings_env, "EARN1", as_of=DAYS[LAST_BEAT + 1])[0]
    assert "gap up on report" in on_gap_day.active_regimes
    for horizon in ("1m", "3m"):
        assert scores[horizon].score > 55.0, horizon
        top = scores[horizon].strongest_supporting_regimes[0]
        assert top.excess > 0 and top.mean > top.baseline_mean
    assert "continued higher" in s.explanation
    assert "comparable earnings events" in s.explanation
    assert "% hit rate" in s.explanation


def test_post_beat_fade(earnings_env) -> None:
    """Identical beat + gap-up setup as EARN1 — but this stock's history
    says beats fade, and the model must learn that per stock."""
    scores = {s.horizon: s for s in evaluate(earnings_env, "EARN2", as_of=BEAT_AS_OF)}
    s = scores["1m"]
    assert "large beat" in s.active_regimes
    for horizon in ("1m", "3m"):
        assert scores[horizon].score < 45.0, horizon
        top = scores[horizon].strongest_negative_regimes[0]
        assert top.excess < 0


def test_post_miss_continued_weakness(earnings_env) -> None:
    scores = {s.horizon: s for s in evaluate(earnings_env, "EARN1", as_of=MISS_AS_OF)}
    s = scores["1m"]
    assert "large miss" in s.active_regimes
    for horizon in ("1m", "3m"):
        assert scores[horizon].score < 45.0, horizon


def test_post_miss_recovery(earnings_env) -> None:
    scores = {s.horizon: s for s in evaluate(earnings_env, "EARN2", as_of=MISS_AS_OF)}
    s = scores["1m"]
    assert "large miss" in s.active_regimes
    for horizon in ("1m", "3m"):
        assert scores[horizon].score > 55.0, horizon


# -- honesty paths ------------------------------------------------------------------


def test_outside_event_window_is_neutral(earnings_env) -> None:
    as_of = DAYS[LAST_MISS + 45]  # ~9 weeks after the report
    scores = evaluate(earnings_env, "EARN1", as_of=as_of)
    for s in scores:
        assert s.score == 50.0 and s.confidence == 0.0
        assert "post-earnings window" in s.explanation


def test_insufficient_earnings_history_is_neutral(earnings_env) -> None:
    scores = evaluate(earnings_env, "EARN3", as_of=BEAT_AS_OF)
    for s in scores:
        assert s.score == 50.0 and s.confidence == 0.0
        assert s.expected_return is None


def test_point_in_time_no_future_evidence(earnings_env) -> None:
    mid_beat = BEATS[len(BEATS) // 2]
    as_of = DAYS[mid_beat + 3]
    scores = evaluate(earnings_env, "EARN1", as_of=as_of)
    for s in scores:
        assert s.as_of == as_of
        for evidence in s.strongest_supporting_regimes + s.strongest_negative_regimes:
            assert evidence.last_event <= as_of


# -- statistical hygiene ---------------------------------------------------------------


def test_overlap_correction_and_diagnostics(earnings_env) -> None:
    scores = {s.horizon: s for s in evaluate(earnings_env, "EARN1", as_of=BEAT_AS_OF)}
    s = scores["1m"]
    diag = s.diagnostics
    assert diag is not None
    assert diag.active_regimes == len(s.active_regimes)
    assert 1 <= diag.evidence_studies <= diag.active_regimes
    # every family conditions on the same report days: the cross-study
    # correlation must be measured as substantial, not assumed independent
    assert diag.mean_cross_correlation > 0.3
    assert abs(diag.z_clipped) <= 4.0
    assert diag.saturated == (abs(diag.z_raw) > 4.0)
    if diag.saturated:
        assert "Score saturated" in s.explanation
    for e in s.strongest_supporting_regimes + s.strongest_negative_regimes:
        assert e.n_eff <= e.n + 1e-9
        assert e.n >= 5
    payload = s.to_dict()
    assert payload["baseline_return"] is not None
    assert payload["excess_return"] == pytest.approx(s.expected_return - s.baseline_return)


def test_reproducible(earnings_env) -> None:
    first = [s.to_dict() for s in evaluate(earnings_env, "EARN1", as_of=BEAT_AS_OF)]
    second = [s.to_dict() for s in evaluate(earnings_env, "EARN1", as_of=BEAT_AS_OF)]
    assert first == second


def test_score_stability_day_over_day(earnings_env) -> None:
    latest = {s.horizon: s.score for s in evaluate(earnings_env, "EARN1", as_of=BEAT_AS_OF)}
    previous = {
        s.horizon: s.score for s in evaluate(earnings_env, "EARN1", as_of=DAYS[LAST_BEAT + 2])
    }
    for horizon in HORIZONS:
        assert abs(latest[horizon] - previous[horizon]) < 15.0


# -- feature backfill invariance --------------------------------------------------------


def test_backfill_does_not_alter_existing_feature_values(
    migrated_schema, session_factory, test_database_url, tmp_path
) -> None:
    with session_scope(session_factory) as session:
        repo = InstrumentRepository(session)
        spy = repo.create_instrument("SPY", InstrumentType.ETF, effective_date=START)
        earn1 = repo.create_instrument("EARN1", InstrumentType.STOCK, effective_date=START)
        session.add_all(
            TradingDay(exchange="NYSE", calendar_date=d) for d in weekdays(START, date(2026, 7, 31))
        )
        prices = PriceRepository(session)
        for instrument, closes in ((spy, SPY), (earn1, EARN1)):
            prices.insert_rows(
                [
                    {
                        "instrument_id": instrument.id,
                        "price_date": d,
                        "open": Decimal(str(c)),
                        "close": Decimal(str(c)),
                        "adj_close": Decimal(str(c)),
                        "volume": 1000,
                    }
                    for d, c in zip(DAYS, closes, strict=True)
                ],
                run_id=None,
            )

    settings = Settings(
        database_url=test_database_url,
        rawdata_root=tmp_path,
        history_start_date=START,
        _env_file=None,
    )
    old_registry = [c for c in build_registry() if c.spec.name not in NEW_FEATURES]
    assert len(old_registry) == len(build_registry()) - len(NEW_FEATURES)

    with session_scope(session_factory) as session:
        pipeline = FeaturePipeline(
            session=session, settings=settings, registry=old_registry, today=lambda: TODAY
        )
        run, _ = pipeline.build(["EARN1"])
        assert run.status is RunStatus.SUCCESS

    def snapshot(session) -> dict:
        features = FeatureRepository(session)
        instrument = InstrumentRepository(session).get_by_symbol("EARN1")
        values = {}
        for name in ("ret_5d", "ret_63d", "vol_21d"):
            definition = features.get_definition(name)
            series = features.get_instrument_series(definition.id, instrument.id)
            values[name] = list(zip(series.index, series.values, strict=True))
        return values

    with session_scope(session_factory) as session:
        before = snapshot(session)
        assert before["ret_5d"]

    with session_scope(session_factory) as session:
        pipeline = FeaturePipeline(session=session, settings=settings, today=lambda: TODAY)
        run, _ = pipeline.build(["EARN1"], rebuild_from=START)
        assert run.status is RunStatus.SUCCESS

    with session_scope(session_factory) as session:
        assert snapshot(session) == before  # existing values untouched
        features = FeatureRepository(session)
        instrument = InstrumentRepository(session).get_by_symbol("EARN1")
        definition = features.get_definition("gap_1d")
        assert definition is not None
        series = features.get_instrument_series(definition.id, instrument.id)
        assert not series.empty


# -- CLI -----------------------------------------------------------------------------


def test_cli_earnings_command(
    earnings_env, monkeypatch, test_database_url, restore_logging
) -> None:
    monkeypatch.setenv("MIP_DATABASE_URL", test_database_url)
    from mip.cli.main import app

    result = CliRunner().invoke(app, ["intelligence", "earnings", "EARN1", "EARN2"])
    assert result.exit_code == 0, result.output
    assert "EARN1" in result.output and "EARN2" in result.output
    assert "active earnings regimes" in result.output

    result = CliRunner().invoke(app, ["intelligence", "earnings", "EARN1", "--json"])
    assert result.exit_code == 0, result.output
    import json

    payload = json.loads(result.output[result.output.index("[") :])
    assert payload[0]["symbol"] == "EARN1"
    assert len(payload[0]["scores"]) == len(HORIZONS)
    assert payload[0]["scores"][0]["model"] == "earnings_behavior"
