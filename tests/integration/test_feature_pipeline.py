"""Phase 5 gate tests: the feature pipeline end-to-end against Postgres."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from mip.core.config import Settings
from mip.core.db import session_scope
from mip.core.exceptions import ConfigurationError
from mip.domain.enums import InstrumentType, RunStatus
from mip.domain.models import (
    EarningsObservation,
    FeatureDefinition,
    FeatureStoreDaily,
    FeatureStoreMarketDaily,
    MacroObservation,
    MacroSeries,
    TradingDay,
)
from mip.features.pipeline import FeaturePipeline
from mip.repositories.features import FeatureRepository
from mip.repositories.instruments import InstrumentRepository
from mip.repositories.prices import PriceRepository

pytestmark = pytest.mark.integration

START = date(2026, 2, 2)  # a Monday
TODAY = date(2026, 7, 10)


def weekdays(start: date, end: date) -> list[date]:
    days, day = [], start
    while day <= end:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


TRADING_DAYS = weekdays(START, date(2026, 7, 31))
PRICE_DAYS = weekdays(START, TODAY)


def close_for(symbol: str, i: int) -> float:
    base = {"TEST1": 100.0, "SPY": 400.0, "XLT": 200.0}[symbol]
    step = {"TEST1": 0.5, "SPY": 1.0, "XLT": 0.25}[symbol]
    return base + i * step


@pytest.fixture()
def env(
    migrated_schema: None,
    session_factory: sessionmaker[Session],
    test_database_url: str,
    tmp_path: Path,
):
    with session_scope(session_factory) as session:
        repo = InstrumentRepository(session)
        sector = repo.get_or_create_sector("Testing")
        industry = repo.get_or_create_industry(sector, "Widgets")
        test1 = repo.create_instrument(
            "TEST1", InstrumentType.STOCK, industry=industry, effective_date=START
        )
        spy = repo.create_instrument("SPY", InstrumentType.ETF, effective_date=START)
        xlt = repo.create_instrument("XLT", InstrumentType.ETF, sector=sector, effective_date=START)
        sector.etf_instrument_id = xlt.id

        session.add_all(TradingDay(exchange="NYSE", calendar_date=d) for d in TRADING_DAYS)

        prices = PriceRepository(session)
        for instrument, symbol in ((test1, "TEST1"), (spy, "SPY"), (xlt, "XLT")):
            prices.insert_rows(
                [
                    {
                        "instrument_id": instrument.id,
                        "price_date": d,
                        "open": Decimal(str(close_for(symbol, i) * 0.99)),
                        "high": Decimal(str(close_for(symbol, i) * 1.02)),
                        "low": Decimal(str(close_for(symbol, i) * 0.98)),
                        "close": Decimal(str(close_for(symbol, i))),
                        "adj_close": Decimal(str(close_for(symbol, i))),
                        "volume": 1000,
                    }
                    for i, d in enumerate(PRICE_DAYS)
                ],
                run_id=None,
            )

        # macro: DGS10/DGS2/VIXCLS daily lag 1; CPI monthly lag 45
        def add_series(code: str, freq: str, lag: int) -> MacroSeries:
            series = MacroSeries(
                provider="FRED",
                provider_code=code,
                name=code,
                frequency=freq,
                publication_lag_days=lag,
            )
            session.add(series)
            session.flush()
            return series

        dgs10 = add_series("DGS10", "D", 1)
        dgs2 = add_series("DGS2", "D", 1)
        vix = add_series("VIXCLS", "D", 1)
        cpi = add_series("CPIAUCSL", "M", 45)
        fed = add_series("FEDFUNDS", "M", 32)

        for i, d in enumerate(PRICE_DAYS):
            session.add(
                MacroObservation(series_id=dgs10.id, obs_date=d, value=Decimal(str(4.0 + i * 0.01)))
            )
            session.add(
                MacroObservation(series_id=dgs2.id, obs_date=d, value=Decimal(str(3.5 + i * 0.005)))
            )
            session.add(
                MacroObservation(
                    series_id=vix.id,
                    obs_date=d,
                    value=Decimal("30") if d == date(2026, 6, 1) else Decimal("18"),
                )
            )
        months = [date(2025, m, 1) for m in range(1, 13)] + [date(2026, m, 1) for m in range(1, 7)]
        for j, m in enumerate(months):
            session.add(MacroObservation(series_id=cpi.id, obs_date=m, value=Decimal(str(300 + j))))
            session.add(MacroObservation(series_id=fed.id, obs_date=m, value=Decimal("4.33")))

        # earnings: one reported event; one future announcement observed 2026-07-01
        session.add(
            EarningsObservation(
                instrument_id=test1.id,
                earnings_date=date(2026, 5, 6),
                observed_at=datetime(2026, 5, 7, 9, 0, tzinfo=UTC),
                eps_actual=Decimal("1.5"),
                eps_estimate=Decimal("1.4"),
                is_confirmed=True,
            )
        )
        session.add(
            EarningsObservation(
                instrument_id=test1.id,
                earnings_date=date(2026, 8, 5),
                observed_at=datetime(2026, 7, 1, 9, 0, tzinfo=UTC),
                eps_estimate=Decimal("1.6"),
                is_confirmed=False,
            )
        )

    settings = Settings(
        database_url=test_database_url,
        rawdata_root=tmp_path,
        history_start_date=START,
        _env_file=None,
    )
    return session_factory, settings


def build(env, symbols=None, registry=None, rebuild_from=None):
    factory, settings = env
    with session_scope(factory) as session:
        pipeline = FeaturePipeline(
            session=session, settings=settings, registry=registry, today=lambda: TODAY
        )
        run, stats = pipeline.build(symbols, rebuild_from=rebuild_from)
        return run.status, stats


def value_of(env, feature: str, day: date, symbol: str | None = None) -> float | None:
    factory, _ = env
    with session_scope(factory) as session:
        definition = FeatureRepository(session).get_definition(feature)
        if symbol is None:
            row = session.scalar(
                select(FeatureStoreMarketDaily.value).where(
                    FeatureStoreMarketDaily.feature_id == definition.id,
                    FeatureStoreMarketDaily.feature_date == day,
                )
            )
        else:
            instrument = InstrumentRepository(session).get_by_symbol(symbol)
            row = session.scalar(
                select(FeatureStoreDaily.value).where(
                    FeatureStoreDaily.feature_id == definition.id,
                    FeatureStoreDaily.instrument_id == instrument.id,
                    FeatureStoreDaily.feature_date == day,
                )
            )
        return float(row) if row is not None else None


def snapshot_store(env) -> dict:
    factory, _ = env
    with session_scope(factory) as session:
        rows = session.execute(
            select(
                FeatureStoreDaily.instrument_id,
                FeatureStoreDaily.feature_date,
                FeatureStoreDaily.feature_id,
                FeatureStoreDaily.value,
                FeatureStoreDaily.computed_at,
            )
        ).all()
        market = session.execute(
            select(
                FeatureStoreMarketDaily.feature_date,
                FeatureStoreMarketDaily.feature_id,
                FeatureStoreMarketDaily.value,
                FeatureStoreMarketDaily.computed_at,
            )
        ).all()
        return {"instrument": set(rows), "market": set(market)}


# -- gates ---------------------------------------------------------------


def test_build_produces_golden_values(env) -> None:
    status, stats = build(env, ["TEST1"])
    assert status is RunStatus.SUCCESS
    assert stats.market_rows > 0 and stats.instrument_rows > 0

    # ret_5d on 2026-02-16 (index 10): close(10)/close(5) - 1
    day = PRICE_DAYS[10]
    expected = close_for("TEST1", 10) / close_for("TEST1", 5) - 1
    assert value_of(env, "ret_5d", day, "TEST1") == pytest.approx(expected, abs=1e-8)

    # rel_ret_spy_21d on index 30
    day = PRICE_DAYS[30]
    own = close_for("TEST1", 30) / close_for("TEST1", 9) - 1
    spy = close_for("SPY", 30) / close_for("SPY", 9) - 1
    assert value_of(env, "rel_ret_spy_21d", day, "TEST1") == pytest.approx(own - spy, abs=1e-8)

    # sector ETF resolved through industry -> sector -> FK
    sector_rel = value_of(env, "rel_ret_sector_21d", day, "TEST1")
    xlt = close_for("XLT", 30) / close_for("XLT", 9) - 1
    assert sector_rel == pytest.approx(own - xlt, abs=1e-8)

    # curve slope on a mid-sample day: obs of the PRIOR session (lag 1)
    idx = 60
    day = PRICE_DAYS[idx]
    slope = (4.0 + (idx - 1) * 0.01) - (3.5 + (idx - 1) * 0.005)
    assert value_of(env, "curve_slope_10y2y", day) == pytest.approx(slope, abs=1e-8)

    # fundamentals absent (no snapshots seeded) -> absent rows, not zeros
    assert value_of(env, "pe_trailing", day, "TEST1") is None


def test_publication_lag_enforced_in_store(env) -> None:
    build(env, ["TEST1"])

    # vix_level: lag 1 -> spike obs 2026-06-01 is visible on 06-02, not 06-01
    assert value_of(env, "vix_level", date(2026, 6, 1)) == pytest.approx(18.0)
    assert value_of(env, "vix_level", date(2026, 6, 2)) == pytest.approx(30.0)

    # cpi_yoy: May 2026 obs (index 16, value 316, yoy vs 304) public Jun 15;
    # June obs (317 vs 305) public Jul 16 > TODAY -> July dates still use May
    may_yoy = 316 / 304 - 1
    assert value_of(env, "cpi_yoy", date(2026, 7, 10)) == pytest.approx(may_yoy, abs=1e-8)
    # before Jun 15, April CPI (315 vs 303) was the latest public
    assert value_of(env, "cpi_yoy", date(2026, 6, 12)) == pytest.approx(315 / 303 - 1, abs=1e-8)


def test_days_until_earnings_is_pit_safe(env) -> None:
    build(env, ["TEST1"])
    # announcement observed 2026-07-01: absent before, present after
    assert value_of(env, "days_until_earnings", date(2026, 6, 30), "TEST1") is None
    expected = (date(2026, 8, 5) - date(2026, 7, 2)).days
    assert value_of(env, "days_until_earnings", date(2026, 7, 2), "TEST1") == pytest.approx(
        expected
    )
    # days_since uses the reported May event across history after it
    assert value_of(env, "days_since_earnings", date(2026, 7, 2), "TEST1") == pytest.approx(
        (date(2026, 7, 2) - date(2026, 5, 6)).days
    )


def test_rebuild_is_idempotent_including_timestamps(env) -> None:
    build(env, ["TEST1"])
    before = snapshot_store(env)

    status, stats = build(env, ["TEST1"])  # incremental re-run
    after = snapshot_store(env)

    assert status is RunStatus.SUCCESS
    assert stats.market_rows == 0 and stats.instrument_rows == 0  # nothing distinct
    assert before == after  # identical values AND computed_at


def test_full_rebuild_reproduces_identical_values(env) -> None:
    build(env, ["TEST1"])
    before = {
        (r[0], r[1], r[2], r[3]) for r in snapshot_store(env)["instrument"]
    }  # drop computed_at

    build(env, ["TEST1"], rebuild_from=START)
    after = {(r[0], r[1], r[2], r[3]) for r in snapshot_store(env)["instrument"]}

    assert before == after  # deterministic reproduction


def test_version_bump_required_for_param_change(env) -> None:
    build(env, ["TEST1"])

    from mip.features.price import RollingReturn

    hacked = RollingReturn(5)
    object.__setattr__(hacked.spec, "params", {"window": 6, "price": "adj_close"})
    with pytest.raises(ConfigurationError, match="bump the version"):
        build(env, ["TEST1"], registry=[hacked])

    bumped = RollingReturn(5)
    object.__setattr__(bumped.spec, "params", {"window": 6, "price": "adj_close"})
    object.__setattr__(bumped.spec, "version", 2)
    status, _ = build(env, ["TEST1"], registry=[bumped])
    assert status is RunStatus.SUCCESS

    factory, _ = env
    with session_scope(factory) as session:
        versions = session.scalars(
            select(FeatureDefinition.version).where(FeatureDefinition.name == "ret_5d")
        ).all()
        assert sorted(versions) == [1, 2]  # old definition & rows retained


def test_matrix_builder_shapes_and_broadcasts(env) -> None:
    build(env, ["TEST1"])
    factory, _ = env
    with session_scope(factory) as session:
        matrix = FeatureRepository(session).get_matrix(
            ["ret_5d", "vol_21d", "vix_level"],
            ["TEST1"],
            date(2026, 6, 1),
            date(2026, 6, 30),
        )

    assert list(matrix.index.names) == ["date", "symbol"]
    assert {"ret_5d", "vol_21d", "vix_level"} <= set(matrix.columns)
    assert set(matrix.index.get_level_values("symbol")) == {"TEST1"}
    # market feature broadcast onto the symbol rows
    june2 = matrix.loc[(date(2026, 6, 2), "TEST1")]
    assert june2["vix_level"] == pytest.approx(30.0)


def test_features_only_on_trading_days_and_partition_routing(env) -> None:
    build(env, ["TEST1"])
    factory, _ = env
    with session_scope(factory) as session:
        dates = session.scalars(select(FeatureStoreMarketDaily.feature_date).distinct()).all()
        assert all(d.weekday() < 5 for d in dates)

        in_partition = session.execute(
            text("SELECT count(*) FROM feature_store_daily_y2026")
        ).scalar_one()
        total = session.execute(
            select(text("count(*)")).select_from(FeatureStoreDaily)
        ).scalar_one()
        assert in_partition == total > 0  # all 2026 rows routed to the 2026 partition
