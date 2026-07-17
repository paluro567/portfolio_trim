"""Momentum Exhaustion Model gate tests against Postgres.

Two stocks with opposite momentum physics, known by construction:

- TESTC (continuation, sector-classified): 90-session advances whose
  strength ESCALATES cycle over cycle, separated by 60-session mild drifts.
  History ends 80 sessions into the strongest run ever, so strong-momentum
  conditions are active by construction and every comparable historical
  episode was followed by more strength -> scores must sit above neutral.

- TESTX (exhaustion, unclassified): 70-session escalating advances that
  each roll straight into a 20-session crash (high volatility) plus a
  40-session drift lower. History ends 68 sessions into the strongest run,
  right where every previous run rolled over -> scores must sit below
  neutral. A mid-crash as_of exercises the high-volatility breakdown regime.

Escalation matters: the final run is the strongest in history, so "top
decile of its own history" conditions hold at the tail deterministically
instead of hinging on ties between identical cycles."""

import math
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session, sessionmaker
from typer.testing import CliRunner

from mip.core.config import Settings
from mip.core.db import session_scope
from mip.domain.enums import InstrumentType, RunStatus
from mip.domain.models import TradingDay
from mip.features.pipeline import FeaturePipeline
from mip.features.registry import build_registry
from mip.models.momentum import HORIZONS, MomentumExhaustionModel
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

NEW_FEATURES = ("vol_ratio_21_63", "ma50_ma200_spread_chg_21d")


def _schedule(tail: tuple[int, str], repeating: list[tuple[int, str]]) -> list[tuple[str, int]]:
    """Per-session (phase, backward-cycle-index) built from the END so the
    tail lands exactly where the tests need it; head is truncated."""
    blocks: list[tuple[int, str, int]] = [(tail[0], tail[1], 0)]
    cycle = 1
    while sum(b[0] for b in blocks) < N:
        for length, phase in repeating:
            blocks.append((length, phase, cycle))
        cycle += 1
    per_session: list[tuple[str, int]] = []
    for length, phase, b in blocks:
        per_session.extend([(phase, b)] * length)
    return list(reversed(per_session[:N]))


def _prices(schedule: list[tuple[str, int]], rates: dict[str, float], step: float) -> list[float]:
    """Daily drift by phase; strong-phase strength decays with the backward
    cycle index (the FINAL run is the strongest). Crash days carry a large
    deterministic wobble so volatility genuinely expands there."""
    values = [100.0]
    for i in range(1, N):
        phase, b = schedule[i]
        if phase == "strong":
            base, amp = rates["strong"] - step * b, 0.0004
        elif phase == "mild":
            base, amp = rates["mild"], 0.0004
        elif phase == "crash":
            # violent two-way tape: crash windows must sit in the top
            # quintile of the volatility distribution (above most phase-
            # boundary windows) without drowning the drift signal
            base, amp = rates["crash"], 0.018
        else:  # drift
            base, amp = rates["drift"], 0.001
        values.append(values[-1] * (1 + base + amp * math.sin(0.8 * i)))
    return [round(v, 6) for v in values]


# 150-session advances separated by EQUALLY long mild stretches: episodes
# fire once the long windows fill (~day 90 of a run) and still have 60+
# strong sessions ahead, while the long mild phases keep the unconditional
# baseline low enough that continuation shows positive excess even at 3m
SCHED_C = _schedule((130, "strong"), [(150, "mild"), (150, "strong")])
TESTC = _prices(SCHED_C, {"strong": 0.011, "mild": 0.0005}, step=0.0004)

# decline = 20 crash sessions then 40 drift sessions (built backward: the
# drift block sits closer to the next run, the crash right after the peak)
SCHED_X = _schedule((68, "strong"), [(40, "drift"), (20, "crash"), (70, "strong")])
TESTX = _prices(SCHED_X, {"strong": 0.013, "crash": -0.015, "drift": -0.004}, step=0.0004)

XLT = [round(100.0 * 1.0002**i, 6) for i in range(N)]
SPY = [round(400.0 * 1.0003**i, 6) for i in range(N)]

LAST_RUN_START_X = N - 68  # final strong run of TESTX
CRASH_AS_OF_X = DAYS[N - 68 - 60 + 20]  # 20 sessions into the last crash+drift decline


@pytest.fixture()
def momentum_env(
    migrated_schema: None,
    session_factory: sessionmaker[Session],
    test_database_url: str,
    tmp_path,
):
    with session_scope(session_factory) as session:
        repo = InstrumentRepository(session)
        spy = repo.create_instrument("SPY", InstrumentType.ETF, effective_date=START)
        xlt = repo.create_instrument("XLT", InstrumentType.ETF, effective_date=START)
        sector = repo.get_or_create_sector("Testtech")
        sector.etf_instrument_id = xlt.id
        session.flush()
        testc = repo.create_instrument(
            "TESTC", InstrumentType.STOCK, sector=sector, effective_date=START
        )
        testx = repo.create_instrument("TESTX", InstrumentType.STOCK, effective_date=START)

        session.add_all(
            TradingDay(exchange="NYSE", calendar_date=d) for d in weekdays(START, date(2026, 7, 31))
        )

        prices = PriceRepository(session)
        for instrument, closes in ((spy, SPY), (xlt, XLT), (testc, TESTC), (testx, TESTX)):
            prices.insert_rows(
                [
                    {
                        "instrument_id": instrument.id,
                        "price_date": d,
                        "open": Decimal(str(c)),
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

    settings = Settings(
        database_url=test_database_url,
        rawdata_root=tmp_path,
        history_start_date=START,
        _env_file=None,
    )
    with session_scope(session_factory) as session:
        pipeline = FeaturePipeline(session=session, settings=settings, today=lambda: TODAY)
        run, _ = pipeline.build(["TESTC", "TESTX", "XLT", "SPY"])
        assert run.status is RunStatus.SUCCESS
    return session_factory


def evaluate(factory, symbol, as_of=None):
    with session_scope(factory) as session:
        return MomentumExhaustionModel(session).evaluate(symbol, as_of=as_of)


def test_fixture_shape() -> None:
    assert SCHED_C[-1][0] == "strong" and SCHED_C[-130][0] == "strong"
    assert SCHED_X[-1][0] == "strong" and SCHED_X[-68][0] == "strong"
    assert SCHED_X[N - 68 - 60 + 10][0] == "crash"  # crash sits right after the peak
    assert SCHED_X[N - 68 - 15][0] == "drift"  # drift leads into the next run


# -- continuation by construction ------------------------------------------------


def test_continuation_stock_scores_favorably(momentum_env) -> None:
    scores = {s.horizon: s for s in evaluate(momentum_env, "TESTC")}
    lit = scores["1m"].active_regimes
    assert "broad momentum ≥ p70" in lit  # strongest run in history, all windows hot
    assert "MA bull, spread widening" in lit
    assert "rising, confirmed vs XLT" in lit  # sector FK resolved, confirmation
    for horizon in ("1m", "3m"):
        s = scores[horizon]
        assert s.score > 55.0, f"{horizon}: continuation history must score favorably"
        assert s.strongest_supporting_regimes  # continuation evidence
        top = s.strongest_supporting_regimes[0]
        assert top.excess > 0 and top.mean > top.baseline_mean
        assert s.baseline_return is not None and s.excess_return is not None
        assert s.excess_return == pytest.approx(s.expected_return - s.baseline_return)


# -- exhaustion by construction ---------------------------------------------------


def test_exhaustion_stock_scores_unfavorably(momentum_env) -> None:
    """Strong momentum that historically rolled over: the SAME kind of
    condition that is favorable for TESTC must be unfavorable at the horizon
    where the rollover lands. By construction that is 3m — runs persist
    ~3 more weeks after top-decile momentum first appears (so short horizons
    are not bearish) and the 130-session cycle has already recovered by 6m."""
    scores = {s.horizon: s for s in evaluate(momentum_env, "TESTX")}
    assert any(label.startswith("63d ret ≥ p9") for label in scores["3m"].active_regimes) or any(
        "broad momentum" in label for label in scores["3m"].active_regimes
    )
    s = scores["3m"]
    assert s.score < 45.0, "3m: exhaustion history must score unfavorably"
    assert s.strongest_negative_regimes  # exhaustion evidence
    top = s.strongest_negative_regimes[0]
    assert top.excess < 0 and top.mean < top.baseline_mean


def test_high_vol_breakdown_regime_mid_crash(momentum_env) -> None:
    scores = {s.horizon: s for s in evaluate(momentum_env, "TESTX", as_of=CRASH_AS_OF_X)}
    s = scores["1m"]
    assert "high-vol breakdown" in s.active_regimes
    assert s.score < 45.0  # crashes here resolve into further drift lower


def test_unclassified_stock_skips_relative_family_only(momentum_env) -> None:
    scores = evaluate(momentum_env, "TESTX")
    assert scores[0].active_regimes  # model still works without a sector ETF
    assert not any(" vs " in label for label in scores[0].active_regimes)
    assert not any("lagging strong" in label for label in scores[0].active_regimes)


# -- statistical hygiene -----------------------------------------------------------


def test_overlap_correction_and_diagnostics(momentum_env) -> None:
    scores = {s.horizon: s for s in evaluate(momentum_env, "TESTC")}
    s = scores["1m"]
    diag = s.diagnostics
    assert diag is not None
    assert diag.active_regimes == len(s.active_regimes)
    assert 1 <= diag.evidence_studies <= diag.active_regimes
    assert 0.0 <= diag.mean_cross_correlation <= 1.0
    assert abs(diag.z_clipped) <= 4.0
    assert diag.saturated == (abs(diag.z_raw) > 4.0)
    if diag.saturated:
        assert "Score saturated" in s.explanation
    for e in s.strongest_supporting_regimes + s.strongest_negative_regimes:
        assert e.n_eff <= e.n + 1e-9  # overlap-adjusted n_eff never exceeds raw n
        assert e.n >= 5
    payload = s.to_dict()
    assert payload["diagnostics"]["evidence_studies"] == diag.evidence_studies
    assert "baseline_return" in payload and "excess_return" in payload


def test_explanation_cites_real_evidence(momentum_env) -> None:
    scores = {s.horizon: s for s in evaluate(momentum_env, "TESTX")}
    s = scores["1m"]
    lead = max(
        list(s.strongest_negative_regimes) + list(s.strongest_supporting_regimes),
        key=lambda e: abs(e.excess / e.se),
    )
    assert f"Across {lead.n} historical episodes" in s.explanation
    assert "independent-equivalent" in s.explanation
    assert f"{lead.mean * 100:+.1f}%" in s.explanation
    assert f"{lead.baseline_mean * 100:+.1f}%" in s.explanation
    assert f"{lead.excess * 100:+.1f}pp" in s.explanation
    assert "TESTX" in s.explanation and "1m" in s.explanation


def test_point_in_time_no_future_evidence(momentum_env) -> None:
    as_of = DAYS[2 * N // 3]
    scores = evaluate(momentum_env, "TESTX", as_of=as_of)
    for s in scores:
        assert s.as_of == as_of
        for evidence in s.strongest_supporting_regimes + s.strongest_negative_regimes:
            assert evidence.last_event <= as_of


def test_reproducible(momentum_env) -> None:
    first = [s.to_dict() for s in evaluate(momentum_env, "TESTC")]
    second = [s.to_dict() for s in evaluate(momentum_env, "TESTC")]
    assert first == second


def test_score_stability_day_over_day(momentum_env) -> None:
    latest = {s.horizon: s.score for s in evaluate(momentum_env, "TESTC")}
    previous = {s.horizon: s.score for s in evaluate(momentum_env, "TESTC", as_of=DAYS[-2])}
    for horizon in HORIZONS:
        assert abs(latest[horizon] - previous[horizon]) < 15.0


def test_insufficient_history_is_honestly_neutral(momentum_env) -> None:
    """Before a year of history no percentile condition is available and
    trend structure has no MA200 — the model must refuse to score."""
    scores = evaluate(momentum_env, "TESTX", as_of=DAYS[100])
    for s in scores:
        assert s.score == 50.0 and s.confidence == 0.0
        assert s.expected_return is None


def test_as_of_before_stored_features_is_neutral(momentum_env) -> None:
    scores = evaluate(momentum_env, "TESTX", as_of=date(2018, 6, 1))
    for s in scores:
        assert s.score == 50.0 and s.confidence == 0.0
        assert "insufficient data" in s.explanation.lower()


# -- feature backfill --------------------------------------------------------------


def test_backfill_does_not_alter_existing_feature_values(
    migrated_schema, session_factory, test_database_url, tmp_path
) -> None:
    with session_scope(session_factory) as session:
        repo = InstrumentRepository(session)
        spy = repo.create_instrument("SPY", InstrumentType.ETF, effective_date=START)
        testc = repo.create_instrument("TESTC", InstrumentType.STOCK, effective_date=START)
        session.add_all(
            TradingDay(exchange="NYSE", calendar_date=d) for d in weekdays(START, date(2026, 7, 31))
        )
        prices = PriceRepository(session)
        for instrument, closes in ((spy, SPY), (testc, TESTC)):
            prices.insert_rows(
                [
                    {
                        "instrument_id": instrument.id,
                        "price_date": d,
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
        run, _ = pipeline.build(["TESTC"])
        assert run.status is RunStatus.SUCCESS

    def snapshot(session) -> dict:
        features = FeatureRepository(session)
        instrument = InstrumentRepository(session).get_by_symbol("TESTC")
        values = {}
        for name in ("vol_21d", "vol_63d", "ma50_ma200_spread", "ret_63d"):
            definition = features.get_definition(name)
            series = features.get_instrument_series(definition.id, instrument.id)
            values[name] = list(zip(series.index, series.values, strict=True))
        return values

    with session_scope(session_factory) as session:
        before = snapshot(session)
        assert before["vol_21d"]

    with session_scope(session_factory) as session:
        pipeline = FeaturePipeline(session=session, settings=settings, today=lambda: TODAY)
        run, _ = pipeline.build(["TESTC"], rebuild_from=START)
        assert run.status is RunStatus.SUCCESS

    with session_scope(session_factory) as session:
        assert snapshot(session) == before  # existing values untouched
        features = FeatureRepository(session)
        instrument = InstrumentRepository(session).get_by_symbol("TESTC")
        for name in NEW_FEATURES:
            definition = features.get_definition(name)
            assert definition is not None, name
            series = features.get_instrument_series(definition.id, instrument.id)
            assert not series.empty, name


# -- CLI ---------------------------------------------------------------------------


def test_cli_momentum_command(
    momentum_env, monkeypatch, test_database_url, restore_logging
) -> None:
    monkeypatch.setenv("MIP_DATABASE_URL", test_database_url)
    from mip.cli.main import app

    result = CliRunner().invoke(app, ["intelligence", "momentum", "TESTC", "TESTX"])
    assert result.exit_code == 0, result.output
    assert "TESTC" in result.output and "TESTX" in result.output
    assert "active momentum regimes" in result.output

    result = CliRunner().invoke(app, ["intelligence", "momentum", "TESTX", "--json"])
    assert result.exit_code == 0, result.output
    import json

    payload = json.loads(result.output[result.output.index("[") :])
    assert payload[0]["symbol"] == "TESTX"
    assert len(payload[0]["scores"]) == len(HORIZONS)
    assert payload[0]["scores"][0]["model"] == "momentum_exhaustion"
