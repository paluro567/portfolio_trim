"""Sector Rotation Model gate tests against Postgres.

Fixture: SPY drifts steadily up (+0.05%/session). XLK — the Information
Technology sector ETF, FK-linked — alternates 40-session phases: +0.45%/day
(outperforming) then -0.35%/day (underperforming). TEST1 (sector-classified)
and TEST2 (industry-classified) are sector-sensitive by construction:
+0.6%/day in outperform phases, -0.5%/day in underperform phases (plus a
small deterministic wobble so returns are not degenerate). Every expected
regime label is derived straight from the seeded arrays, not from the model.
"""

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
from mip.models.sector import HORIZONS, REL_THRESHOLDS, SectorRotationModel
from mip.repositories.features import FeatureRepository
from mip.repositories.instruments import InstrumentRepository
from mip.repositories.prices import PriceRepository
from tests.integration.test_feature_pipeline import weekdays
from tests.integration.test_research_engine import restore_logging  # noqa: F401

pytestmark = pytest.mark.integration

START = date(2024, 1, 1)
TODAY = date(2026, 7, 10)
DAYS = weekdays(START, TODAY)
CYCLE = 40  # sessions per phase; even phases outperform, odd underperform

NEW_FEATURES = (  # added for this model; backfill must not touch anything else
    "rel_ret_spy_5d",
    "rel_ret_spy_126d",
    "rel_ret_sector_5d",
    "rel_ret_sector_126d",
    "rel_ret_spy_accel_21d",
)


def up(i: int) -> bool:
    return (i // CYCLE) % 2 == 0


def _series(base_up: float, base_down: float, wobble: float = 0.0) -> list[float]:
    values = [100.0]
    for i in range(1, len(DAYS)):
        base = base_up if up(i) else base_down
        values.append(values[-1] * (1 + base + wobble * math.sin(0.7 * i)))
    return [round(v, 6) for v in values]  # what the store will see (NUMERIC 6dp seed)


SPY = [round(400.0 * 1.0005**i, 6) for i in range(len(DAYS))]
XLK = _series(+0.0045, -0.0035)
TEST1 = _series(+0.0060, -0.0050, wobble=0.0005)


# -- expected regimes, derived from the arrays (independent arithmetic) --------


def _ret(closes: list[float], i: int, window: int) -> float:
    return closes[i] / closes[i - window] - 1.0


def _q(value: float) -> float:
    return round(value, 8)  # store quantizes to NUMERIC(20,8)


def expected_active_labels(i: int, symbol: str = "TEST1") -> list[str]:
    """Walk the documented candidate order per family, most specific first:
    divergence -> conditional (high-vol absent here; bull=1 by construction)
    -> strong threshold -> mild threshold. One label max per family."""
    labels = []
    for window in (5, 21, 63, 126):
        strong, mild = REL_THRESHOLDS[window]
        xlk_ret = _q(_ret(XLK, i, window))
        spy_ret = _q(_ret(SPY, i, window))
        rel = _q(_ret(XLK, i, window) - _ret(SPY, i, window))
        if xlk_ret > 0 and spy_ret < 0:
            labels.append(f"XLK up, SPY down/{window}d")
        elif xlk_ret < 0 and spy_ret > 0:
            labels.append(f"XLK down, SPY up/{window}d")
        elif rel <= -mild:  # bull regime is always 1 (SPY monotonic above MA200)
            labels.append(f"XLK -{mild * 100:g}% vs SPY, bull mkt/{window}d")
        elif rel >= strong:
            labels.append(f"XLK +{strong * 100:g}% vs SPY/{window}d")
        elif rel >= mild:
            labels.append(f"XLK +{mild * 100:g}% vs SPY/{window}d")
        elif rel <= -strong:
            labels.append(f"XLK -{strong * 100:g}% vs SPY/{window}d")

        rel_sector = _q(_ret(TEST1, i, window) - _ret(XLK, i, window))
        if rel_sector >= strong:
            labels.append(f"{symbol} +{strong * 100:g}% vs XLK/{window}d")
        elif rel_sector >= mild:
            labels.append(f"{symbol} +{mild * 100:g}% vs XLK/{window}d")
        elif rel_sector <= -strong:
            labels.append(f"{symbol} -{strong * 100:g}% vs XLK/{window}d")
        elif rel_sector <= -mild:
            labels.append(f"{symbol} -{mild * 100:g}% vs XLK/{window}d")

    rel_now = _ret(XLK, i, 21) - _ret(SPY, i, 21)
    rel_prev = _ret(XLK, i - 21, 21) - _ret(SPY, i - 21, 21)
    accel = _q(rel_now - rel_prev)
    if accel >= 0.05:
        labels.append("XLK accel +5%/21d")
    elif accel >= 0.02:
        labels.append("XLK accel +2%/21d")
    elif accel <= -0.05:
        labels.append("XLK accel -5%/21d")
    elif accel <= -0.02:
        labels.append("XLK accel -2%/21d")
    return labels


# -- fixture ---------------------------------------------------------------


@pytest.fixture()
def sector_env(
    migrated_schema: None,
    session_factory: sessionmaker[Session],
    test_database_url: str,
    tmp_path,
):
    with session_scope(session_factory) as session:
        repo = InstrumentRepository(session)
        spy = repo.create_instrument("SPY", InstrumentType.ETF, effective_date=START)
        xlk = repo.create_instrument("XLK", InstrumentType.ETF, effective_date=START)
        sector = repo.get_or_create_sector("Information Technology")
        sector.etf_instrument_id = xlk.id
        session.flush()
        industry = repo.get_or_create_industry(sector, "Semiconductors")
        test1 = repo.create_instrument(
            "TEST1", InstrumentType.STOCK, sector=sector, effective_date=START
        )
        test2 = repo.create_instrument(
            "TEST2", InstrumentType.STOCK, industry=industry, effective_date=START
        )

        session.add_all(
            TradingDay(exchange="NYSE", calendar_date=d) for d in weekdays(START, date(2026, 7, 31))
        )

        prices = PriceRepository(session)
        for instrument, closes in ((spy, SPY), (xlk, XLK), (test1, TEST1), (test2, TEST1)):
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
        run, _ = pipeline.build(["TEST1", "TEST2", "XLK", "SPY"])
        assert run.status is RunStatus.SUCCESS
    return session_factory


def evaluate(factory, symbol="TEST1", as_of=None):
    with session_scope(factory) as session:
        return SectorRotationModel(session).evaluate(symbol, as_of=as_of)


TAIL = len(DAYS) - 1
DOWN_AS_OF_INDEX = 15 * CYCLE + 30  # deep inside an underperformance phase


def test_fixture_shape() -> None:
    """The assertions below assume the history ends well inside an
    outperformance phase and covers the mid-phase down index."""
    assert up(TAIL) and TAIL % CYCLE >= 10
    assert DOWN_AS_OF_INDEX < len(DAYS) and not up(DOWN_AS_OF_INDEX)


# -- gates ---------------------------------------------------------------


def test_sector_etf_resolved_via_fk_for_sector_and_industry_paths(sector_env) -> None:
    for symbol in ("TEST1", "TEST2"):  # direct sector FK / industry->sector join
        scores = evaluate(sector_env, symbol)
        assert scores[0].active_regimes, symbol
        assert any("XLK" in label for label in scores[0].active_regimes), symbol


def test_active_regimes_match_seeded_arrays(sector_env) -> None:
    scores = evaluate(sector_env)
    expected = expected_active_labels(TAIL)
    assert expected, "fixture must end inside an active regime"
    assert list(scores[0].active_regimes) == expected
    assert scores[0].as_of == DAYS[TAIL]


def test_no_double_counting_of_nested_regimes(sector_env) -> None:
    """Strong outperformance also satisfies the mild threshold — only ONE
    sector-vs-SPY label per window may appear (most specific)."""
    labels = list(evaluate(sector_env)[0].active_regimes)
    assert len(labels) == len(set(labels))
    for window in (5, 21, 63, 126):
        per_window = [
            label
            for label in labels
            if label.endswith(f"/{window}d") and "vs XLK" not in label and "accel" not in label
        ]
        assert len(per_window) <= 1, per_window


def test_sector_outperformance_scores_bullish(sector_env) -> None:
    """History ends inside an outperformance phase; TEST1 rallies in those
    phases by construction, so short horizons must score above neutral."""
    scores = {s.horizon: s for s in evaluate(sector_env)}
    for horizon in ("1w", "2w", "1m"):
        s = scores[horizon]
        assert s.sample_size >= 5
        assert 0.0 <= s.score <= 100.0 and 0.0 <= s.confidence <= 1.0
        assert s.score > 55.0, f"{horizon}: sector outperformance must score bullish"
        assert s.strongest_supporting_regimes
        top = s.strongest_supporting_regimes[0]
        assert top.excess > 0 and top.mean > top.baseline_mean


def test_sector_underperformance_scores_bearish(sector_env) -> None:
    scores = {s.horizon: s for s in evaluate(sector_env, as_of=DAYS[DOWN_AS_OF_INDEX])}
    for horizon in ("1w", "2w", "1m"):
        s = scores[horizon]
        assert s.score < 45.0, f"{horizon}: sector underperformance must score bearish"
        assert s.strongest_negative_regimes
        top = s.strongest_negative_regimes[0]
        assert top.excess < 0 and top.mean < top.baseline_mean


def test_evidence_is_internally_consistent(sector_env) -> None:
    scores = {s.horizon: s for s in evaluate(sector_env)}
    s = scores["1w"]
    as_of = s.as_of
    evidence = list(s.strongest_supporting_regimes) + list(s.strongest_negative_regimes)
    assert evidence
    for e in evidence:
        assert e.n >= 5  # min-sample filter
        assert e.excess == pytest.approx(e.mean - e.baseline_mean)
        assert 0.0 <= e.hit_rate <= 1.0
        assert START <= e.first_event <= e.last_event <= as_of


def test_explanation_cites_real_evidence(sector_env) -> None:
    scores = {s.horizon: s for s in evaluate(sector_env)}
    s = scores["1m"]
    lead = max(
        list(s.strongest_negative_regimes) + list(s.strongest_supporting_regimes),
        key=lambda e: abs(e.excess / e.se),
    )
    assert f"the {lead.n} past environments" in s.explanation
    assert f"{lead.mean * 100:+.1f}%" in s.explanation
    assert "TEST1" in s.explanation and "1m" in s.explanation
    assert "sector regimes" in s.explanation


def test_point_in_time_no_future_evidence(sector_env) -> None:
    as_of = DAYS[len(DAYS) // 2]
    scores = evaluate(sector_env, as_of=as_of)
    for s in scores:
        assert s.as_of == as_of
        for evidence in s.strongest_supporting_regimes + s.strongest_negative_regimes:
            assert evidence.last_event <= as_of  # no event selected after as_of


def test_reproducible(sector_env) -> None:
    first = [s.to_dict() for s in evaluate(sector_env)]
    second = [s.to_dict() for s in evaluate(sector_env)]
    assert first == second


def test_score_stability_day_over_day(sector_env) -> None:
    """One more trading day of information must not swing the verdict."""
    latest = {s.horizon: s.score for s in evaluate(sector_env)}
    previous = {s.horizon: s.score for s in evaluate(sector_env, as_of=DAYS[-2])}
    for horizon in HORIZONS:
        assert abs(latest[horizon] - previous[horizon]) < 15.0


def test_insufficient_evidence_is_honestly_neutral(sector_env) -> None:
    """Early in history regimes are active but episodes are too few: the
    model must refuse to score rather than extrapolate."""
    scores = evaluate(sector_env, as_of=DAYS[90])
    for s in scores:
        assert s.score == 50.0 and s.confidence == 0.0
        assert s.expected_return is None
        assert "fewer than" in s.explanation or "No sector-rotation regime" in s.explanation


def test_unclassified_instrument_is_neutral_with_explanation(sector_env) -> None:
    scores = evaluate(sector_env, "SPY")  # no sector classification
    for s in scores:
        assert s.score == 50.0 and s.confidence == 0.0
        assert "no sector→ETF mapping" in s.explanation


def test_as_of_before_stored_features_is_neutral(sector_env) -> None:
    """Regression twin of the rates fix: predating all features must yield
    the standard neutral output, not a crash or ConfigurationError."""
    scores = evaluate(sector_env, as_of=date(2023, 6, 1))
    assert [s.horizon for s in scores] == list(HORIZONS)
    for s in scores:
        assert s.score == 50.0 and s.confidence == 0.0
        assert "insufficient data" in s.explanation.lower()


def test_diagnostics_expose_overlap_and_saturation(sector_env) -> None:
    scores = {s.horizon: s for s in evaluate(sector_env)}
    s = scores["1m"]
    diag = s.diagnostics
    assert diag is not None
    assert diag.active_regimes == len(s.active_regimes)
    assert 1 <= diag.evidence_studies <= diag.active_regimes
    # active regimes fire around the same phase turns: overlap must be
    # measured as real, positive correlation — not assumed away
    assert 0.0 < diag.mean_cross_correlation <= 1.0
    assert abs(diag.z_clipped) <= 4.0
    assert diag.saturated == (abs(diag.z_raw) > 4.0)
    assert s.to_dict()["diagnostics"]["saturated"] == diag.saturated
    if diag.saturated:
        assert "Score saturated" in s.explanation


def test_backfill_does_not_alter_existing_feature_values(
    migrated_schema, session_factory, test_database_url, tmp_path
) -> None:
    """Build with the pre-extension registry, then backfill the full one:
    previously stored values must be byte-identical afterward."""
    with session_scope(session_factory) as session:
        repo = InstrumentRepository(session)
        spy = repo.create_instrument("SPY", InstrumentType.ETF, effective_date=START)
        xlk = repo.create_instrument("XLK", InstrumentType.ETF, effective_date=START)
        sector = repo.get_or_create_sector("Information Technology")
        sector.etf_instrument_id = xlk.id
        test1 = repo.create_instrument(
            "TEST1", InstrumentType.STOCK, sector=sector, effective_date=START
        )
        session.add_all(
            TradingDay(exchange="NYSE", calendar_date=d) for d in weekdays(START, date(2026, 7, 31))
        )
        prices = PriceRepository(session)
        for instrument, closes in ((spy, SPY), (xlk, XLK), (test1, TEST1)):
            prices.insert_rows(
                [
                    {
                        "instrument_id": instrument.id,
                        "price_date": d,
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
        run, _ = pipeline.build(["TEST1"])
        assert run.status is RunStatus.SUCCESS

    def snapshot(session) -> dict:
        features = FeatureRepository(session)
        instrument = InstrumentRepository(session).get_by_symbol("TEST1")
        values = {}
        for name in ("rel_ret_spy_21d", "rel_ret_sector_63d", "ret_21d"):
            definition = features.get_definition(name)
            series = features.get_instrument_series(definition.id, instrument.id)
            values[name] = list(zip(series.index, series.values, strict=True))
        return values

    with session_scope(session_factory) as session:
        before = snapshot(session)
        assert before["rel_ret_spy_21d"]  # non-empty premise

    with session_scope(session_factory) as session:
        pipeline = FeaturePipeline(session=session, settings=settings, today=lambda: TODAY)
        run, _ = pipeline.build(["TEST1"], rebuild_from=START)
        assert run.status is RunStatus.SUCCESS

    with session_scope(session_factory) as session:
        assert snapshot(session) == before  # existing values untouched
        features = FeatureRepository(session)
        instrument = InstrumentRepository(session).get_by_symbol("TEST1")
        for name in NEW_FEATURES:  # and the new features are now populated
            definition = features.get_definition(name)
            assert definition is not None, name
            series = features.get_instrument_series(definition.id, instrument.id)
            assert not series.empty, name


def test_cli_sector_command(sector_env, monkeypatch, test_database_url, restore_logging) -> None:
    monkeypatch.setenv("MIP_DATABASE_URL", test_database_url)
    from mip.cli.main import app

    result = CliRunner().invoke(app, ["intelligence", "sector", "TEST1", "TEST2"])
    assert result.exit_code == 0, result.output
    assert "TEST1" in result.output and "TEST2" in result.output
    assert "active sector regimes" in result.output

    result = CliRunner().invoke(app, ["intelligence", "sector", "TEST1", "--json"])
    assert result.exit_code == 0, result.output
    import json

    payload = json.loads(result.output[result.output.index("[") :])
    assert payload[0]["symbol"] == "TEST1"
    assert len(payload[0]["scores"]) == len(HORIZONS)
    assert payload[0]["scores"][0]["model"] == "sector_rotation"
