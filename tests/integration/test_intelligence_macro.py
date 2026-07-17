"""Macro Regime Model gate tests against Postgres.

A synthetic economy alternates 260-session regimes (each longer than the
12-month YoY windows, so inflation/growth features cannot alias), history
ending 230 sessions into an easing block:

  TIGHT: CPI accelerating, Fed hiking, curve inverting, unemployment
         rising, payrolls/retail/housing/sentiment fading, VIX ramping,
         SPY drifting lower  (inflation shock -> tightening -> inversion
         -> recession-like)
  EASE:  disinflation, Fed cutting, curve re-steepening, labor healing,
         growth series recovering, VIX crushed, SPY rallying (easing ->
         soft landing -> risk-on)

MACRO1 is pro-cyclical (+0.5%/day in EASE, -0.35%/day in TIGHT); MACRO2 is
counter-cyclical (+0.25%/day in TIGHT, -0.15%/day in EASE) — the SAME
macro regime must score in opposite directions for the two stocks, purely
from their own histories. All macro observations carry realistic
publication lags, so detection sees only what was knowable."""

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
from mip.features.registry import build_registry
from mip.models.macro import HORIZONS, MacroRegimeModel
from mip.repositories.features import FeatureRepository
from mip.repositories.instruments import InstrumentRepository
from mip.repositories.prices import PriceRepository
from tests.integration.test_feature_pipeline import weekdays
from tests.integration.test_research_engine import restore_logging  # noqa: F401

pytestmark = pytest.mark.integration

# Blocks must be LONGER than the 12-month YoY windows, else every trailing
# year contains the same tight/ease mixture and yoy/accel features alias to
# noise; long blocks in turn need a long history for >= 5 episodes.
START = date(2013, 1, 1)
TODAY = date(2026, 7, 10)
DAYS = weekdays(START, TODAY)
N = len(DAYS)

NEW_FEATURES = (
    "curve_slope_10y2y_chg_63d",
    "fedfunds_chg_6m",
    "unrate_chg_6m",
    "umcsent_chg_6m",
    "vix_chg_21d",
    "payems_yoy",
    "gdpc1_yoy",
    "houst_yoy",
    "rsafs_yoy",
)

BLOCK = 260  # ~12.4 months per phase: YoY windows sit inside one phase
TAIL = 230  # history ends this many sessions into an easing block


def _schedule() -> list[tuple[str, int]]:
    """(phase, sessions-into-block) per session, built backward."""
    per_session: list[str] = ["ease"] * TAIL
    while len(per_session) < N:
        per_session.extend(["tight"] * BLOCK)
        per_session.extend(["ease"] * BLOCK)
    forward = list(reversed(per_session[:N]))
    out, k = [], 0
    for i, phase in enumerate(forward):
        k = k + 1 if i > 0 and forward[i - 1] == phase else 0
        out.append((phase, k))
    return out


SCHED = _schedule()


def _drivers() -> dict[str, list[float]]:
    """Daily macro drivers, sampled monthly/quarterly into observations."""
    ff, dgs2, dgs10, unrate = [2.5], [2.5], [3.5], [5.0]
    cpi, payems, rsafs, houst, umcsent, gdp = (
        [100.0],
        [150000.0],
        [500000.0],
        [1400.0],
        [85.0],
        [20000.0],
    )
    vix = [20.0]
    for i in range(1, N):
        phase, k = SCHED[i]
        tight = phase == "tight"
        ff.append(min(6.5, max(0.25, ff[-1] + (0.012 if tight else -0.012))))
        dgs2.append(min(7.0, max(0.25, dgs2[-1] + (0.012 if tight else -0.012))))
        dgs10.append(min(6.5, max(0.5, dgs10[-1] + (0.004 if tight else -0.004))))
        unrate.append(min(10.0, max(3.0, unrate[-1] + (0.003 if tight else -0.003))))
        cpi.append(cpi[-1] * (1 + (0.00045 if tight else 0.00008)))
        payems.append(payems[-1] * (1 + (-0.00010 if tight else 0.00040)))
        rsafs.append(rsafs[-1] * (1 + (-0.00015 if tight else 0.00050)))
        houst.append(houst[-1] * (1 + (-0.00060 if tight else 0.00070)))
        umcsent.append(min(110.0, max(50.0, umcsent[-1] + (-0.10 if tight else 0.12))))
        gdp.append(gdp[-1] * (1 + (-0.00005 if tight else 0.00030)))
        vix.append(18.0 + 14.0 * k / BLOCK if tight else max(14.0, 30.0 - 16.0 * k / BLOCK))
    return {
        "FEDFUNDS": ff,
        "DGS2": dgs2,
        "DGS10": dgs10,
        "UNRATE": unrate,
        "CPIAUCSL": cpi,
        "PAYEMS": payems,
        "RSAFS": rsafs,
        "HOUST": houst,
        "UMCSENT": umcsent,
        "GDPC1": gdp,
        "VIXCLS": vix,
    }


DRIVERS = _drivers()
LAGS = {
    "FEDFUNDS": ("M", 32),
    "DGS2": ("D", 1),
    "DGS10": ("D", 1),
    "UNRATE": ("M", 35),
    "CPIAUCSL": ("M", 45),
    "PAYEMS": ("M", 35),
    "RSAFS": ("M", 45),
    "HOUST": ("M", 48),
    "UMCSENT": ("M", 30),
    "GDPC1": ("Q", 120),
    "VIXCLS": ("D", 1),
}


def _prices(ease_drift: float, tight_drift: float) -> list[float]:
    values = [100.0]
    for i in range(1, N):
        drift = ease_drift if SCHED[i][0] == "ease" else tight_drift
        values.append(values[-1] * (1 + drift + 0.0004 * math.sin(0.9 * i)))
    return [round(v, 6) for v in values]


MACRO1 = _prices(+0.0050, -0.0035)  # pro-cyclical
MACRO2 = _prices(-0.0015, +0.0025)  # counter-cyclical / defensive
SPY = _prices(+0.0012, -0.0006)


def last_index_of(phase: str, day_in_block: int) -> int:
    for i in range(N - 1, -1, -1):
        if SCHED[i] == (phase, day_in_block):
            return i
    raise AssertionError(f"no session at day {day_in_block} of a {phase} block")


TIGHT_AS_OF = DAYS[last_index_of("tight", 230)]  # deep enough for lagged monthlies


@pytest.fixture()
def macro_env(
    migrated_schema: None,
    session_factory: sessionmaker[Session],
    test_database_url: str,
    tmp_path,
):
    with session_scope(session_factory) as session:
        repo = InstrumentRepository(session)
        spy = repo.create_instrument("SPY", InstrumentType.ETF, effective_date=START)
        macro1 = repo.create_instrument("MACRO1", InstrumentType.STOCK, effective_date=START)
        macro2 = repo.create_instrument("MACRO2", InstrumentType.STOCK, effective_date=START)

        session.add_all(
            TradingDay(exchange="NYSE", calendar_date=d) for d in weekdays(START, date(2026, 7, 31))
        )

        prices = PriceRepository(session)
        for instrument, closes in ((spy, SPY), (macro1, MACRO1), (macro2, MACRO2)):
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

        # macro series: daily as-is; monthly/quarterly sampled at period starts
        month_starts = {}
        for i, d in enumerate(DAYS):
            month_starts.setdefault((d.year, d.month), i)
        for code, values in DRIVERS.items():
            freq, lag = LAGS[code]
            series = MacroSeries(
                provider="FRED",
                provider_code=code,
                name=code,
                frequency=freq,
                publication_lag_days=lag,
            )
            session.add(series)
            session.flush()
            if freq == "D":
                observations = [(DAYS[i], values[i]) for i in range(N)]
            else:
                observations = []
                for (year, month), i in sorted(month_starts.items()):
                    if freq == "Q" and month not in (1, 4, 7, 10):
                        continue
                    observations.append((date(year, month, 1), values[i]))
            session.add_all(
                MacroObservation(series_id=series.id, obs_date=d, value=Decimal(str(round(v, 6))))
                for d, v in observations
            )

    settings = Settings(
        database_url=test_database_url,
        rawdata_root=tmp_path,
        history_start_date=START,
        _env_file=None,
    )
    with session_scope(session_factory) as session:
        pipeline = FeaturePipeline(session=session, settings=settings, today=lambda: TODAY)
        run, _ = pipeline.build(["MACRO1", "MACRO2", "SPY"])
        assert run.status is RunStatus.SUCCESS
    return session_factory


def evaluate(factory, symbol, as_of=None):
    with session_scope(factory) as session:
        return MacroRegimeModel(session).evaluate(symbol, as_of=as_of)


def test_fixture_shape() -> None:
    assert SCHED[-1] == ("ease", TAIL - 1)
    assert (N - TAIL) / (2 * BLOCK) > 5.5  # >= 6 full macro cycles
    assert SCHED[last_index_of("tight", 230)][0] == "tight"


# -- regime detection: both macro states -----------------------------------------


def test_easing_environment_detected_at_tail(macro_env) -> None:
    s = evaluate(macro_env, "MACRO1")[0]  # tail = deep in an easing block
    lit = set(s.active_regimes)
    assert "easing cycle" in lit
    # disinflation shows up through the composite (accel < 0 is one of its
    # conditions); the inflation family itself is honestly quiet once
    # inflation is already low and only drifting lower
    assert lit & {"soft landing", "disinflation + easing", "risk-on environment"}, lit
    assert not lit & {"hot inflation, rising", "inflation accelerating"}, lit


def test_tightening_environment_detected(macro_env) -> None:
    s = evaluate(macro_env, "MACRO1", as_of=TIGHT_AS_OF)[0]
    lit = set(s.active_regimes)
    assert "tightening cycle" in lit
    assert lit & {"hot inflation, rising", "inflation accelerating"}, lit
    assert "inversion deepening" in lit  # yield-curve inversion
    assert "employment weakening" in lit
    assert lit & {"recession-like", "inflation + restrictive", "risk-off environment"}, lit


# -- per-stock directions in the SAME environment ---------------------------------


def test_procyclical_stock_scores_by_regime(macro_env) -> None:
    easing = {s.horizon: s for s in evaluate(macro_env, "MACRO1")}
    tightening = {s.horizon: s for s in evaluate(macro_env, "MACRO1", as_of=TIGHT_AS_OF)}
    for horizon in ("1m", "3m"):
        assert easing[horizon].score > 55.0, f"easing {horizon}"
        assert tightening[horizon].score < 45.0, f"tightening {horizon}"
    top = easing["1m"].strongest_supporting_regimes[0]
    assert top.excess > 0 and top.mean > top.baseline_mean
    assert "outperformed" in easing["1m"].explanation
    assert "% hit rate" in easing["1m"].explanation


def test_countercyclical_stock_scores_opposite(macro_env) -> None:
    """The SAME macro regimes, the opposite verdicts — evidence is per
    stock, never a global macro opinion."""
    easing = {s.horizon: s for s in evaluate(macro_env, "MACRO2")}
    tightening = {s.horizon: s for s in evaluate(macro_env, "MACRO2", as_of=TIGHT_AS_OF)}
    assert easing["1m"].active_regimes == evaluate(macro_env, "MACRO1")[0].active_regimes
    for horizon in ("1m", "3m"):
        assert easing[horizon].score < 45.0, f"easing {horizon}"
        assert tightening[horizon].score > 55.0, f"tightening {horizon}"


# -- honesty and PIT ----------------------------------------------------------------


def test_insufficient_macro_history_is_neutral(macro_env) -> None:
    scores = evaluate(macro_env, "MACRO1", as_of=DAYS[100])
    for s in scores:
        assert s.score == 50.0 and s.confidence == 0.0
        assert (
            "Insufficient macro history" in s.explanation
            or "fewer than" in s.explanation
            or "No macro regime" in s.explanation
        )


def test_point_in_time_no_future_evidence(macro_env) -> None:
    as_of = DAYS[2 * N // 3]
    scores = evaluate(macro_env, "MACRO1", as_of=as_of)
    for s in scores:
        assert s.as_of == as_of
        for evidence in s.strongest_supporting_regimes + s.strongest_negative_regimes:
            assert evidence.last_event <= as_of


# -- statistical hygiene ---------------------------------------------------------------


def test_overlap_correction_and_diagnostics(macro_env) -> None:
    scores = {s.horizon: s for s in evaluate(macro_env, "MACRO1")}
    s = scores["1m"]
    diag = s.diagnostics
    assert diag is not None
    assert diag.active_regimes == len(s.active_regimes)
    assert 1 <= diag.evidence_studies <= diag.active_regimes
    assert 0.0 <= diag.mean_cross_correlation <= 1.0
    # macro families all watch the same persistent environments; at longer
    # horizons the Bartlett kernel spans the lag offsets between families and
    # the shared episodes must show up as substantial measured correlation
    assert scores["6m"].diagnostics.mean_cross_correlation > 0.3
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


def test_reproducible(macro_env) -> None:
    first = [s.to_dict() for s in evaluate(macro_env, "MACRO1")]
    second = [s.to_dict() for s in evaluate(macro_env, "MACRO1")]
    assert first == second


def test_score_stability_day_over_day(macro_env) -> None:
    latest = {s.horizon: s.score for s in evaluate(macro_env, "MACRO1")}
    previous = {s.horizon: s.score for s in evaluate(macro_env, "MACRO1", as_of=DAYS[-2])}
    for horizon in HORIZONS:
        assert abs(latest[horizon] - previous[horizon]) < 15.0


# -- feature backfill invariance --------------------------------------------------------


def test_backfill_does_not_alter_existing_feature_values(
    migrated_schema, session_factory, test_database_url, tmp_path
) -> None:
    with session_scope(session_factory) as session:
        repo = InstrumentRepository(session)
        spy = repo.create_instrument("SPY", InstrumentType.ETF, effective_date=START)
        macro1 = repo.create_instrument("MACRO1", InstrumentType.STOCK, effective_date=START)
        session.add_all(
            TradingDay(exchange="NYSE", calendar_date=d) for d in weekdays(START, date(2026, 7, 31))
        )
        prices = PriceRepository(session)
        for instrument, closes in ((spy, SPY), (macro1, MACRO1)):
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
        for code in ("DGS2", "DGS10", "VIXCLS", "FEDFUNDS", "CPIAUCSL", "UNRATE"):
            freq, lag = LAGS[code]
            series = MacroSeries(
                provider="FRED",
                provider_code=code,
                name=code,
                frequency=freq,
                publication_lag_days=lag,
            )
            session.add(series)
            session.flush()
            step = 1 if freq == "D" else 21
            session.add_all(
                MacroObservation(
                    series_id=series.id,
                    obs_date=DAYS[i],
                    value=Decimal(str(round(DRIVERS[code][i], 6))),
                )
                for i in range(0, N, step)
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
        run, _ = pipeline.build(["MACRO1"])
        assert run.status is RunStatus.SUCCESS

    def snapshot(session) -> dict:
        features = FeatureRepository(session)
        values = {}
        for name in ("curve_slope_10y2y", "fedfunds_level", "cpi_yoy", "vix_pctile_252d"):
            definition = features.get_definition(name)
            series = features.get_market_series(definition.id)
            values[name] = list(zip(series.index, series.values, strict=True))
        return values

    with session_scope(session_factory) as session:
        before = snapshot(session)
        assert before["curve_slope_10y2y"]

    with session_scope(session_factory) as session:
        pipeline = FeaturePipeline(session=session, settings=settings, today=lambda: TODAY)
        run, _ = pipeline.build(["MACRO1"], rebuild_from=START)
        assert run.status is RunStatus.SUCCESS

    with session_scope(session_factory) as session:
        assert snapshot(session) == before  # existing values untouched
        features = FeatureRepository(session)
        for name in ("curve_slope_10y2y_chg_63d", "fedfunds_chg_6m", "unrate_chg_6m"):
            definition = features.get_definition(name)
            assert definition is not None, name
            series = features.get_market_series(definition.id)
            assert not series.empty, name


# -- CLI -----------------------------------------------------------------------------


def test_cli_macro_command(macro_env, monkeypatch, test_database_url, restore_logging) -> None:
    monkeypatch.setenv("MIP_DATABASE_URL", test_database_url)
    from mip.cli.main import app

    result = CliRunner().invoke(app, ["intelligence", "macro", "MACRO1", "MACRO2"])
    assert result.exit_code == 0, result.output
    assert "MACRO1" in result.output and "MACRO2" in result.output
    assert "active macro regimes" in result.output

    result = CliRunner().invoke(app, ["intelligence", "macro", "MACRO1", "--json"])
    assert result.exit_code == 0, result.output
    import json

    payload = json.loads(result.output[result.output.index("[") :])
    assert payload[0]["symbol"] == "MACRO1"
    assert len(payload[0]["scores"]) == len(HORIZONS)
    assert payload[0]["scores"][0]["model"] == "macro_regime"
