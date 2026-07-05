"""Phase 4 gate tests: fundamentals snapshots and append-only earnings,
against Postgres with fake providers (no network)."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from mip.core.config import Settings
from mip.core.db import session_scope
from mip.core.exceptions import PermanentError
from mip.domain.enums import InstrumentType, IssueSeverity, RunStatus
from mip.domain.models import CompanyFundamentals, DataQualityIssue, EarningsObservation
from mip.ingestion.archive import RawDataArchive
from mip.ingestion.earnings_service import EarningsIngestionService
from mip.ingestion.fundamental_service import FundamentalIngestionService
from mip.ingestion.validation import (
    RULE_MARKETCAP_INCONSISTENT,
    RULE_NEGATIVE_FUNDAMENTAL,
)
from mip.providers.base import empty_earnings_frame
from mip.repositories.instruments import InstrumentRepository
from mip.repositories.prices import PriceRepository

pytestmark = pytest.mark.integration

D1, D2 = date(2026, 7, 1), date(2026, 7, 2)


def snapshot(**overrides: object) -> dict[str, float | None]:
    base: dict[str, float | None] = {
        "market_cap": 1_000_000_000.0,
        "trailing_pe": 25.0,
        "forward_pe": 22.0,
        "price_to_book": 5.0,
        "trailing_eps": 4.0,
        "forward_eps": 4.5,
        "dividend_yield": 0.01,
        "beta": 1.1,
        "shares_outstanding": 10_000_000,
        "revenue_ttm": 500_000_000.0,
        "profit_margin": 0.2,
        "debt_to_equity": 80.0,
    }
    base.update(overrides)  # type: ignore[arg-type]
    return base


class FakeFundamentals:
    name = "fake"

    def __init__(self) -> None:
        self.data: dict[str, dict[str, float | None]] = {}
        self.errors: dict[str, Exception] = {}

    def fetch_fundamentals(self, symbol: str) -> dict[str, float | None]:
        if symbol in self.errors:
            raise self.errors[symbol]
        return dict(self.data[symbol])


class FakeEarnings:
    name = "fake"

    def __init__(self) -> None:
        self.frames: dict[str, pd.DataFrame] = {}

    def set(self, symbol: str, rows: list[dict[str, object]]) -> None:
        self.frames[symbol] = pd.DataFrame(rows)

    def fetch_earnings(self, symbol: str) -> pd.DataFrame:
        return self.frames.get(symbol, empty_earnings_frame()).copy()


def earnings_row(
    d: date, estimate: float | None = 1.5, actual: float | None = None, tod: str = "AMC"
) -> dict[str, object]:
    return {
        "earnings_date": d,
        "time_of_day": tod,
        "eps_estimate": estimate if estimate is not None else float("nan"),
        "eps_actual": actual if actual is not None else float("nan"),
    }


class Phase4Env:
    def __init__(self, factory: sessionmaker[Session], settings: Settings) -> None:
        self.factory = factory
        self.settings = settings
        self.fundamentals = FakeFundamentals()
        self.earnings = FakeEarnings()
        self.today = D1
        self._tick = 0

    def _now(self) -> datetime:
        self._tick += 1  # strictly increasing observed_at across runs
        return datetime(2026, 7, 1, 12, 0, 0, self._tick, tzinfo=UTC)

    def ingest_fundamentals(self, symbols: list[str] | None = None):
        with session_scope(self.factory) as session:
            service = FundamentalIngestionService(
                session=session,
                provider=self.fundamentals,
                archive=RawDataArchive(self.settings.rawdata_root),
                settings=self.settings,
                sleep=lambda _s: None,
                today=lambda: self.today,
            )
            run, outcomes = service.ingest(symbols)
            return run.id, run.status, run.error_detail, {o.key: o for o in outcomes}

    def ingest_earnings(self, symbols: list[str] | None = None):
        with session_scope(self.factory) as session:
            service = EarningsIngestionService(
                session=session,
                provider=self.earnings,
                archive=RawDataArchive(self.settings.rawdata_root),
                settings=self.settings,
                sleep=lambda _s: None,
                today=lambda: self.today,
                now=self._now,
            )
            run, outcomes = service.ingest(symbols)
            return run.id, run.status, run.error_detail, {o.key: o for o in outcomes}

    def snapshots(self, symbol: str) -> dict[date, CompanyFundamentals]:
        with session_scope(self.factory) as session:
            instrument = InstrumentRepository(session).get_by_symbol(symbol)
            rows = list(
                session.scalars(
                    select(CompanyFundamentals).where(
                        CompanyFundamentals.instrument_id == instrument.id
                    )
                )
            )
            session.expunge_all()
            return {r.as_of_date: r for r in rows}

    def observations(self, symbol: str) -> list[EarningsObservation]:
        with session_scope(self.factory) as session:
            instrument = InstrumentRepository(session).get_by_symbol(symbol)
            rows = list(
                session.scalars(
                    select(EarningsObservation)
                    .where(EarningsObservation.instrument_id == instrument.id)
                    .order_by(EarningsObservation.earnings_date, EarningsObservation.observed_at)
                )
            )
            session.expunge_all()
            return rows

    def current_view(self, symbol: str) -> dict[date, dict]:
        with session_scope(self.factory) as session:
            instrument = InstrumentRepository(session).get_by_symbol(symbol)
            rows = session.execute(
                text("SELECT * FROM v_earnings_current WHERE instrument_id = :iid"),
                {"iid": instrument.id},
            ).mappings()
            return {row["earnings_date"]: dict(row) for row in rows}

    def issues(self, rule: str) -> list[DataQualityIssue]:
        with session_scope(self.factory) as session:
            issues = list(
                session.scalars(select(DataQualityIssue).where(DataQualityIssue.rule == rule))
            )
            session.expunge_all()
            return issues


@pytest.fixture()
def env(
    migrated_schema: None,
    session_factory: sessionmaker[Session],
    test_database_url: str,
    tmp_path: Path,
) -> Phase4Env:
    with session_scope(session_factory) as session:
        repo = InstrumentRepository(session)
        for symbol in ("FUND1", "EARN1", "BROKEN"):
            repo.create_instrument(symbol, InstrumentType.STOCK, effective_date=D1)

    settings = Settings(
        database_url=test_database_url,
        rawdata_root=tmp_path / "RawData",
        retry_max_attempts=2,
        retry_backoff_seconds=0.01,
        _env_file=None,
    )
    return Phase4Env(session_factory, settings)


# -- gate: snapshot semantics ---------------------------------------------


def test_snapshots_accumulate_across_dates(env: Phase4Env) -> None:
    env.fundamentals.data["FUND1"] = snapshot()

    env.today = D1
    env.ingest_fundamentals(["FUND1"])
    env.today = D2
    env.fundamentals.data["FUND1"] = snapshot(trailing_pe=26.5)
    env.ingest_fundamentals(["FUND1"])

    rows = env.snapshots("FUND1")
    assert set(rows) == {D1, D2}  # two fetch dates -> two rows (history)
    assert rows[D1].trailing_pe == Decimal("25.0000")  # D1 untouched
    assert rows[D2].trailing_pe == Decimal("26.5000")


def test_same_day_refetch_upserts_with_revision_ledger(env: Phase4Env) -> None:
    env.fundamentals.data["FUND1"] = snapshot()
    env.ingest_fundamentals(["FUND1"])

    # unchanged re-fetch: pure no-op
    _, _, _, outcomes = env.ingest_fundamentals(["FUND1"])
    assert outcomes["FUND1"].updated == 0 and outcomes["FUND1"].revisions == 0

    # changed re-fetch same day: upsert, never a duplicate row
    env.fundamentals.data["FUND1"] = snapshot(trailing_pe=27.0)
    _, _, _, outcomes = env.ingest_fundamentals(["FUND1"])

    rows = env.snapshots("FUND1")
    assert list(rows) == [D1]  # still exactly one row for the day
    assert rows[D1].trailing_pe == Decimal("27.0000")
    assert outcomes["FUND1"].updated == 1 and outcomes["FUND1"].revisions == 1

    with session_scope(env.factory) as session:
        from mip.domain.models import DataRevision

        revision = session.scalar(
            select(DataRevision).where(DataRevision.table_name == "company_fundamentals")
        )
        assert revision.entity_key == f"FUND1/{D1}"
        assert revision.field == "trailing_pe"
        assert revision.old_value == "25.0000" and revision.new_value == "27.0000"


def test_missing_fields_stored_as_null_without_quarantine(env: Phase4Env) -> None:
    env.fundamentals.data["FUND1"] = snapshot(
        trailing_pe=None, beta=None, revenue_ttm=None, debt_to_equity=None
    )
    _, status, _, outcomes = env.ingest_fundamentals(["FUND1"])

    assert status is RunStatus.SUCCESS
    assert outcomes["FUND1"].inserted == 1 and outcomes["FUND1"].quarantined == 0
    row = env.snapshots("FUND1")[D1]
    assert row.trailing_pe is None and row.beta is None
    assert row.market_cap == Decimal("1000000000.00")  # provided fields intact


def test_negative_field_nulled_and_ledgered(env: Phase4Env) -> None:
    env.fundamentals.data["FUND1"] = snapshot(market_cap=-42.0)
    _, _, _, outcomes = env.ingest_fundamentals(["FUND1"])

    row = env.snapshots("FUND1")[D1]
    assert row.market_cap is None  # nulled
    assert row.trailing_pe == Decimal("25.0000")  # snapshot kept
    issues = env.issues(RULE_NEGATIVE_FUNDAMENTAL)
    assert len(issues) == 1 and issues[0].severity is IssueSeverity.ERROR


# -- gate: cross-check against prices ----------------------------------------


def test_marketcap_price_shares_mismatch_flagged(env: Phase4Env) -> None:
    with session_scope(env.factory) as session:
        instrument = InstrumentRepository(session).get_by_symbol("FUND1")
        PriceRepository(session).insert_rows(
            [
                {
                    "instrument_id": instrument.id,
                    "price_date": D1 - timedelta(days=1),
                    "open": Decimal("99"),
                    "high": Decimal("101"),
                    "low": Decimal("98"),
                    "close": Decimal("100"),
                    "adj_close": Decimal("100"),
                    "volume": 1000,
                }
            ],
            run_id=None,
        )

    # close 100 * 10M shares = 1B, provider claims 5B -> unit-error tripwire
    env.fundamentals.data["FUND1"] = snapshot(market_cap=5_000_000_000.0)
    env.ingest_fundamentals(["FUND1"])

    issues = env.issues(RULE_MARKETCAP_INCONSISTENT)
    assert len(issues) == 1
    assert issues[0].severity is IssueSeverity.WARNING
    assert env.snapshots("FUND1")[D1].market_cap is not None  # stored, flagged


# -- gate: append-only earnings ------------------------------------------------


def test_earnings_append_only_with_shifted_date(env: Phase4Env) -> None:
    original_date, shifted_date = date(2026, 7, 30), date(2026, 8, 6)
    env.earnings.set("EARN1", [earnings_row(original_date)])
    env.ingest_earnings(["EARN1"])

    # identical re-fetch: appends nothing
    _, _, _, outcomes = env.ingest_earnings(["EARN1"])
    assert outcomes["EARN1"].inserted == 0
    assert len(env.observations("EARN1")) == 1

    # the announced date shifts: a NEW observation row; prior row untouched
    env.earnings.set("EARN1", [earnings_row(shifted_date)])
    _, _, _, outcomes = env.ingest_earnings(["EARN1"])

    observations = env.observations("EARN1")
    assert outcomes["EARN1"].inserted == 1
    assert [(o.earnings_date) for o in observations] == [original_date, shifted_date]
    assert observations[0].eps_estimate == Decimal("1.5000")  # original preserved


def test_state_change_appends_and_view_shows_latest(env: Phase4Env) -> None:
    event = date(2026, 7, 30)
    env.earnings.set("EARN1", [earnings_row(event, estimate=1.5)])
    env.ingest_earnings(["EARN1"])

    # after the report: actual EPS lands -> new observation, old kept
    env.earnings.set("EARN1", [earnings_row(event, estimate=1.5, actual=1.62)])
    env.ingest_earnings(["EARN1"])

    observations = env.observations("EARN1")
    assert len(observations) == 2  # full history survives
    assert observations[0].eps_actual is None
    assert observations[1].eps_actual == Decimal("1.6200")
    assert observations[1].is_confirmed is True

    current = env.current_view("EARN1")
    assert list(current) == [event]
    assert current[event]["eps_actual"] == Decimal("1.6200")  # view = latest state


def test_implausible_earnings_date_quarantined(env: Phase4Env) -> None:
    env.earnings.set("EARN1", [earnings_row(date(1970, 1, 1)), earnings_row(date(2026, 7, 30))])
    _, _, _, outcomes = env.ingest_earnings(["EARN1"])

    assert outcomes["EARN1"].quarantined == 1
    assert outcomes["EARN1"].inserted == 1  # plausible row loads
    assert [o.earnings_date for o in env.observations("EARN1")] == [date(2026, 7, 30)]


# -- gate: isolation + archive ----------------------------------------------------


def test_partial_failure_isolates_symbols(env: Phase4Env) -> None:
    env.fundamentals.data["FUND1"] = snapshot()
    env.fundamentals.errors["BROKEN"] = PermanentError("no fundamentals")

    _, status, error_detail, outcomes = env.ingest_fundamentals(["FUND1", "BROKEN"])

    assert status is RunStatus.PARTIAL
    assert outcomes["FUND1"].inserted == 1
    assert "no fundamentals" in error_detail["failed"]["BROKEN"]


def test_archives_written_for_both_domains(env: Phase4Env) -> None:
    env.fundamentals.data["FUND1"] = snapshot()
    env.earnings.set("EARN1", [earnings_row(date(2026, 7, 30))])

    env.ingest_fundamentals(["FUND1"])
    env.ingest_earnings(["EARN1"])

    assert list((env.settings.rawdata_root / "fundamentals" / "FUND1").glob("*.csv"))
    assert list((env.settings.rawdata_root / "earnings" / "EARN1").glob("*.csv"))
