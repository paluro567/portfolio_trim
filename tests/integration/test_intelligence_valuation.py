"""Valuation Model gate tests against Postgres, with SYNTHETIC historical
fundamentals snapshots (the real platform has one snapshot; the model's
insufficiency path is exactly what VALN exercises).

Cycles are four 63-session phases per ~calendar year, so snapshot YoY
comparisons land on the same phase one year earlier and each phase's
revenue growth is exact by construction. Each stock tells ONE story so
episode-start effects cannot cancel:

  VALG  A expensive + strong growth/margins -> keeps rising (justified),
        C cheap + improving growth -> recovers, D filler. Cycle A,D,C,D.
  VALB  B expensive + weak growth/margins -> declines (vulnerable),
        D filler. Cycle B,D,D,D.
  VALT  value trap: glory era, then cheap-forever with zero growth and 2%
        margins, drifting lower in trap sub-phases split by reliefs.
  VALN  prices for years, snapshots only in the last 15 sessions — the
        honest-insufficiency and no-backfill case.

A small deterministic wobble keeps forward returns non-degenerate (identical
cycles would give zero within-study variance)."""

import math
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session, sessionmaker
from typer.testing import CliRunner

from mip.core.config import Settings
from mip.core.db import session_scope
from mip.domain.enums import InstrumentType, RunStatus
from mip.domain.models import CompanyFundamentals, MacroObservation, MacroSeries, TradingDay
from mip.features.pipeline import FeaturePipeline
from mip.features.registry import build_registry
from mip.models.valuation import HORIZONS, ValuationModel
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

NEW_FEATURES = ("profit_margin", "debt_to_equity", "pe_trailing_chg_63d", "pe_forward_chg_63d")

PHASE_LEN = 63
TAIL = 40  # history ends 40 sessions into the headline phase

#                 pe,   ps, margin, growth, daily drift
PHASES = {
    "A": (60.0, 20.0, 0.30, 0.40, +0.0060),  # expensive, justified
    "B": (60.0, 20.0, 0.05, 0.02, -0.0045),  # expensive, vulnerable
    "C": (15.0, 5.0, 0.15, 0.30, +0.0040),  # cheap, improving
    "D": (30.0, 10.0, 0.15, 0.15, +0.0005),  # middling filler
}


def _schedule(tail_phase: str, backward_cycle: list[str]) -> list[str]:
    per_session = [tail_phase] * TAIL
    while len(per_session) < N:
        for phase in backward_cycle:
            per_session.extend([phase] * PHASE_LEN)
    return list(reversed(per_session[:N]))


def _prices(schedule: list[str], drift_of) -> list[float]:
    values = [100.0]
    for i in range(1, N):
        values.append(values[-1] * (1 + drift_of(schedule[i]) + 0.0003 * math.sin(0.9 * i)))
    return [round(v, 6) for v in values]


SCHED_G = _schedule("A", ["D", "C", "D", "A"])  # forward cycle: A, D, C, D
SCHED_B = _schedule("B", ["D", "D", "D", "B"])  # forward cycle: B, D, D, D
VALG = _prices(SCHED_G, lambda p: PHASES[p][4])
VALB = _prices(SCHED_B, lambda p: PHASES[p][4])

GLORY = 500
#                     pe, margin, daily drift
VALT_PHASES = {
    "glory": (50.0, 0.25, +0.0040),
    "trap": (10.0, 0.02, -0.0035),
    "relief": (20.0, 0.10, +0.0005),
}


def _valt_schedule() -> list[str]:
    per_session = ["trap"] * TAIL  # tail sits inside a trap sub-phase
    while len(per_session) < N - GLORY:
        per_session.extend(["relief"] * 40)
        per_session.extend(["trap"] * 80)
    return ["glory"] * GLORY + list(reversed(per_session[: N - GLORY]))


SCHED_T = _valt_schedule()
VALT = _prices(SCHED_T, lambda p: VALT_PHASES[p][2])

SPY = [round(400.0 * 1.0003**i, 6) for i in range(N)]

# 140-session rate legs at +-1.5bp/day (period 280, deliberately NOT a
# divisor of the 252-session valuation cycle so rate and valuation phases
# rotate against each other and every combination eventually co-occurs)
DGS10 = []
_level = 3.0
for _i in range(N):
    _level += 0.015 if (_i // 140) % 2 == 0 else -0.015
    DGS10.append(round(_level, 6))


def last_index_of(schedule: list[str], phase: str, day_in_phase: int) -> int:
    """Last session that is exactly `day_in_phase` sessions into `phase`."""
    for i in range(N - 1, -1, -1):
        if schedule[i] != phase or i < day_in_phase:
            continue
        run_start = i
        while run_start > 0 and schedule[run_start - 1] == phase:
            run_start -= 1
        if i - run_start == day_in_phase:
            return i
    raise AssertionError(f"no session at day {day_in_phase} of phase {phase}")


def rate_rising_expensive_index() -> int:
    """A session deep inside a rising-rate stretch while VALB is expensive
    (phase B) — derived from the seeded arrays, not from the model."""
    for i in range(N - 1, 150, -1):
        deep_in_up_leg = (i // 140) % 2 == 0 and i % 140 >= 70
        if deep_in_up_leg and SCHED_B[i] == "B" and DGS10[i - 1] - DGS10[i - 64] > 0.25:
            return i
    raise AssertionError("fixture must contain a rising-rate expensive stretch")


@pytest.fixture()
def valuation_env(
    migrated_schema: None,
    session_factory: sessionmaker[Session],
    test_database_url: str,
    tmp_path,
):
    with session_scope(session_factory) as session:
        repo = InstrumentRepository(session)
        spy = repo.create_instrument("SPY", InstrumentType.ETF, effective_date=START)
        valg = repo.create_instrument("VALG", InstrumentType.STOCK, effective_date=START)
        valb = repo.create_instrument("VALB", InstrumentType.STOCK, effective_date=START)
        valt = repo.create_instrument("VALT", InstrumentType.STOCK, effective_date=START)
        valn = repo.create_instrument("VALN", InstrumentType.STOCK, effective_date=START)

        session.add_all(
            TradingDay(exchange="NYSE", calendar_date=d) for d in weekdays(START, date(2026, 7, 31))
        )

        prices = PriceRepository(session)
        for instrument, closes in (
            (spy, SPY),
            (valg, VALG),
            (valb, VALB),
            (valt, VALT),
            (valn, VALT),
        ):
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

        # Phase-cycled snapshots: revenue is constant within each (phase,
        # calendar year) and multiplies by (1+growth) year over year, so the
        # YoY feature equals the phase's growth target by construction.
        def snapshot(instrument_id: int, i: int, schedule: list[str]) -> CompanyFundamentals:
            pe, ps, margin, growth, _ = PHASES[schedule[i]]
            year = DAYS[i].year - START.year
            revenue = 1e9 * (1.0 + growth) ** year
            return CompanyFundamentals(
                instrument_id=instrument_id,
                as_of_date=DAYS[i],
                trailing_pe=Decimal(str(pe)),
                forward_pe=Decimal(str(round(pe * 0.8, 4))),
                market_cap=Decimal(str(round(ps * revenue, 2))),
                revenue_ttm=Decimal(str(round(revenue, 2))),
                profit_margin=Decimal(str(margin)),
                debt_to_equity=Decimal("0.5"),
            )

        for instrument, schedule in ((valg, SCHED_G), (valb, SCHED_B)):
            for i in range(N):
                run_start = i
                while run_start > 0 and schedule[run_start - 1] == schedule[i]:
                    run_start -= 1
                offset = i - run_start
                if offset == 0 or offset == PHASE_LEN // 2:  # phase start + mid
                    session.add(snapshot(instrument.id, i, schedule))

        # VALT: revenue grows 40%/yr in the glory era, then decays at an
        # ACCELERATING rate — YoY growth declines strictly, so the trap tail
        # sits at its historical minimum (no degenerate quantile ties) and
        # market cap tracks the P/E pattern so P/S is cheap in traps too.
        def valt_snapshot(i: int) -> CompanyFundamentals:
            pe, margin, _ = VALT_PHASES[SCHED_T[i]]
            if i <= GLORY:
                revenue = 1e9 * (1.4 ** (i / 252.0))
            else:
                x = (i - GLORY) / 252.0
                revenue = 1e9 * (1.4 ** (GLORY / 252.0)) * math.exp(-0.02 * x - 0.015 * x * x)
            return CompanyFundamentals(
                instrument_id=valt.id,
                as_of_date=DAYS[i],
                trailing_pe=Decimal(str(pe)),
                forward_pe=Decimal(str(round(pe * 0.9, 4))),
                market_cap=Decimal(str(round((pe / 5.0) * revenue, 2))),
                revenue_ttm=Decimal(str(round(revenue, 2))),
                profit_margin=Decimal(str(margin)),
                debt_to_equity=Decimal("1.5"),
            )

        valt_indices = set(range(0, N, 21))  # monthly
        valt_indices |= {i for i in range(1, N) if SCHED_T[i] != SCHED_T[i - 1]}  # boundaries
        for i in sorted(valt_indices):
            session.add(valt_snapshot(i))

        for i in range(N - 15, N, 5):  # VALN: only the last 15 sessions
            session.add(
                CompanyFundamentals(
                    instrument_id=valn.id,
                    as_of_date=DAYS[i],
                    trailing_pe=Decimal("30"),
                    forward_pe=Decimal("25"),
                    market_cap=Decimal(str(5e9)),
                    revenue_ttm=Decimal(str(1e9)),
                    profit_margin=Decimal("0.1"),
                    debt_to_equity=Decimal("1.0"),
                )
            )

        dgs10 = MacroSeries(
            provider="FRED",
            provider_code="DGS10",
            name="10y",
            frequency="D",
            publication_lag_days=1,
        )
        session.add(dgs10)
        session.flush()
        for d, value in zip(DAYS, DGS10, strict=True):
            session.add(MacroObservation(series_id=dgs10.id, obs_date=d, value=Decimal(str(value))))

    settings = Settings(
        database_url=test_database_url,
        rawdata_root=tmp_path,
        history_start_date=START,
        _env_file=None,
    )
    with session_scope(session_factory) as session:
        pipeline = FeaturePipeline(session=session, settings=settings, today=lambda: TODAY)
        run, _ = pipeline.build(["VALG", "VALB", "VALT", "VALN", "SPY"])
        assert run.status is RunStatus.SUCCESS
    return session_factory


def evaluate(factory, symbol, as_of=None):
    with session_scope(factory) as session:
        return ValuationModel(session).evaluate(symbol, as_of=as_of)


def test_fixture_shape() -> None:
    assert SCHED_G[-1] == "A" and SCHED_G[-TAIL] == "A" and SCHED_G[-TAIL - 1] == "D"
    assert SCHED_B[-1] == "B" and SCHED_B[-TAIL - 1] == "D"
    assert SCHED_T[-1] == "trap"
    assert N > 6 * 252  # enough full cycles for resolved 1y forwards


# -- the four archetypes, known by construction -----------------------------------


def test_expensive_with_strong_growth_scores_favorably(valuation_env) -> None:
    scores = {s.horizon: s for s in evaluate(valuation_env, "VALG")}  # tail = mid-A
    s = scores["1m"]
    assert "expensive on P/E and P/S" in s.active_regimes
    assert "expensive, strong growth" in s.active_regimes
    assert "expensive, strong margins" in s.active_regimes
    for horizon in ("1m", "3m"):
        assert scores[horizon].score > 55.0, horizon
        top = scores[horizon].strongest_supporting_regimes[0]
        assert top.excess > 0 and top.mean > top.baseline_mean
    assert "Expensive but historically justified" in s.explanation


def test_expensive_with_weak_growth_scores_unfavorably(valuation_env) -> None:
    """Identical top-decile valuation to VALG's phase A — but weak growth
    and margins select the vulnerable regimes, and history punishes them."""
    scores = {s.horizon: s for s in evaluate(valuation_env, "VALB")}  # tail = mid-B
    s = scores["1m"]
    assert "expensive on P/E and P/S" in s.active_regimes
    assert "expensive, weak growth" in s.active_regimes
    assert "expensive, weak margins" in s.active_regimes
    for horizon in ("1m", "3m"):
        assert scores[horizon].score < 45.0, horizon
        top = scores[horizon].strongest_negative_regimes[0]
        assert top.excess < 0 and top.mean < top.baseline_mean
    assert "Expensive and historically vulnerable" in s.explanation


def test_cheap_with_improving_growth_scores_favorably(valuation_env) -> None:
    as_of = DAYS[last_index_of(SCHED_G, "C", 45)]
    scores = {s.horizon: s for s in evaluate(valuation_env, "VALG", as_of=as_of)}
    s = scores["1m"]
    assert "cheap, improving growth" in s.active_regimes
    assert "cheap, strong margins" in s.active_regimes
    assert s.score > 55.0
    assert "Cheap" in s.explanation or "favorable" in s.explanation


def test_value_trap_scores_unfavorably(valuation_env) -> None:
    scores = {s.horizon: s for s in evaluate(valuation_env, "VALT")}  # tail = trap
    s = scores["1m"]
    assert "cheap, weak growth" in s.active_regimes
    assert "cheap, weak margins" in s.active_regimes
    assert s.score < 45.0
    assert "value-trap" in s.explanation


# -- valuation change and rates ---------------------------------------------------


def test_multiple_expansion_and_normalization_detection(valuation_env) -> None:
    tail = evaluate(valuation_env, "VALG")[0]  # mid-A: P/E jumped D->A inside 63d
    assert "price up, fwd P/E expanding" in tail.active_regimes

    # VALB right after B: price still falling, trailing P/E collapsed 60->30
    early_d = DAYS[last_index_of(SCHED_B, "D", 20)]
    s = evaluate(valuation_env, "VALB", as_of=early_d)[0]
    assert "price down, multiple normalizing" in s.active_regimes
    assert "multiple compression" not in s.active_regimes  # most specific wins


def test_rate_conditioned_valuation_regime(valuation_env) -> None:
    as_of = DAYS[rate_rising_expensive_index()]
    s = evaluate(valuation_env, "VALB", as_of=as_of)[0]
    assert "expensive, rising rates" in s.active_regimes


# -- honesty: insufficiency and no backfilling ----------------------------------------


def test_insufficient_snapshot_history_is_honestly_neutral(valuation_env) -> None:
    scores = evaluate(valuation_env, "VALN")
    assert [s.horizon for s in scores] == list(HORIZONS)
    for s in scores:
        assert s.score == 50.0 and s.confidence == 0.0
        assert s.expected_return is None and s.diagnostics is None
        assert "Insufficient historical valuation evidence" in s.explanation
        assert "never backfilled" in s.explanation


def test_fundamentals_are_never_backfilled_before_first_snapshot(valuation_env) -> None:
    """VALN has ~8 years of prices but snapshots only in its last 15
    sessions: the stored pe_trailing series must begin at the first
    snapshot date — current fundamentals never leak into the past."""
    with session_scope(valuation_env) as session:
        features = FeatureRepository(session)
        valn = InstrumentRepository(session).get_by_symbol("VALN")
        definition = features.get_definition("pe_trailing")
        series = features.get_instrument_series(definition.id, valn.id)
        assert not series.empty
        assert series.index[0].date() >= DAYS[N - 15]
        assert len(series) <= 15


def test_point_in_time_no_future_evidence(valuation_env) -> None:
    as_of = DAYS[2 * N // 3]
    scores = evaluate(valuation_env, "VALG", as_of=as_of)
    for s in scores:
        assert s.as_of == as_of
        for evidence in s.strongest_supporting_regimes + s.strongest_negative_regimes:
            assert evidence.last_event <= as_of


# -- statistical hygiene ----------------------------------------------------------------


def test_overlap_correction_and_diagnostics(valuation_env) -> None:
    scores = {s.horizon: s for s in evaluate(valuation_env, "VALG")}
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
        assert e.n_eff <= e.n + 1e-9
        assert e.n >= 5
    payload = s.to_dict()
    assert payload["baseline_return"] is not None
    assert payload["excess_return"] == pytest.approx(s.expected_return - s.baseline_return)


def test_reproducible(valuation_env) -> None:
    first = [s.to_dict() for s in evaluate(valuation_env, "VALG")]
    second = [s.to_dict() for s in evaluate(valuation_env, "VALG")]
    assert first == second


def test_score_stability_day_over_day(valuation_env) -> None:
    latest = {s.horizon: s.score for s in evaluate(valuation_env, "VALG")}
    previous = {s.horizon: s.score for s in evaluate(valuation_env, "VALG", as_of=DAYS[-2])}
    for horizon in HORIZONS:
        assert abs(latest[horizon] - previous[horizon]) < 15.0


# -- feature backfill invariance --------------------------------------------------------


def test_backfill_does_not_alter_existing_feature_values(
    migrated_schema, session_factory, test_database_url, tmp_path
) -> None:
    with session_scope(session_factory) as session:
        repo = InstrumentRepository(session)
        spy = repo.create_instrument("SPY", InstrumentType.ETF, effective_date=START)
        valg = repo.create_instrument("VALG", InstrumentType.STOCK, effective_date=START)
        session.add_all(
            TradingDay(exchange="NYSE", calendar_date=d) for d in weekdays(START, date(2026, 7, 31))
        )
        prices = PriceRepository(session)
        for instrument, closes in ((spy, SPY), (valg, VALG)):
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
        for i in range(0, N, 21):
            session.add(
                CompanyFundamentals(
                    instrument_id=valg.id,
                    as_of_date=DAYS[i],
                    trailing_pe=Decimal(str(20 + (i % 5))),
                    forward_pe=Decimal("18"),
                    market_cap=Decimal(str(5e9)),
                    revenue_ttm=Decimal(str(1e9)),
                    profit_margin=Decimal("0.2"),
                    debt_to_equity=Decimal("0.8"),
                )
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
        run, _ = pipeline.build(["VALG"])
        assert run.status is RunStatus.SUCCESS

    def snapshot(session) -> dict:
        features = FeatureRepository(session)
        instrument = InstrumentRepository(session).get_by_symbol("VALG")
        values = {}
        for name in ("pe_trailing", "pe_forward", "price_to_sales", "ret_63d"):
            definition = features.get_definition(name)
            series = features.get_instrument_series(definition.id, instrument.id)
            values[name] = list(zip(series.index, series.values, strict=True))
        return values

    with session_scope(session_factory) as session:
        before = snapshot(session)
        assert before["pe_trailing"]

    with session_scope(session_factory) as session:
        pipeline = FeaturePipeline(session=session, settings=settings, today=lambda: TODAY)
        run, _ = pipeline.build(["VALG"], rebuild_from=START)
        assert run.status is RunStatus.SUCCESS

    with session_scope(session_factory) as session:
        assert snapshot(session) == before  # existing values untouched
        features = FeatureRepository(session)
        instrument = InstrumentRepository(session).get_by_symbol("VALG")
        for name in NEW_FEATURES:
            definition = features.get_definition(name)
            assert definition is not None, name
            series = features.get_instrument_series(definition.id, instrument.id)
            assert not series.empty, name


# -- CLI -----------------------------------------------------------------------------


def test_cli_valuation_command(
    valuation_env, monkeypatch, test_database_url, restore_logging
) -> None:
    monkeypatch.setenv("MIP_DATABASE_URL", test_database_url)
    from mip.cli.main import app

    result = CliRunner().invoke(app, ["intelligence", "valuation", "VALG", "VALN"])
    assert result.exit_code == 0, result.output
    assert "VALG" in result.output and "VALN" in result.output
    assert "active valuation regimes" in result.output
    assert "Insufficient historical valuation evidence" in result.output  # VALN

    result = CliRunner().invoke(app, ["intelligence", "valuation", "VALG", "--json"])
    assert result.exit_code == 0, result.output
    import json

    payload = json.loads(result.output[result.output.index("[") :])
    assert payload[0]["symbol"] == "VALG"
    assert len(payload[0]["scores"]) == len(HORIZONS)
    assert payload[0]["scores"][0]["model"] == "valuation"
