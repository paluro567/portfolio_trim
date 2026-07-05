"""Phase 3 gate tests: FRED macro ingestion against Postgres with a fake
provider (no network)."""

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from mip.core.config import Settings
from mip.core.db import session_scope
from mip.domain.enums import IssueSeverity, RunStatus
from mip.domain.models import DataQualityIssue, DataRevision, MacroObservation
from mip.ingestion.archive import RawDataArchive
from mip.ingestion.fred_service import MacroIngestionService
from mip.ingestion.validation import (
    RULE_FREQUENCY_MISMATCH,
    RULE_STALE_SERIES,
    RULE_VALUE_OUT_OF_RANGE,
)
from mip.providers.base import empty_macro_frame
from mip.reference.macro_catalog import MacroCatalog, SeriesDef
from mip.repositories.macro import MacroRepository

pytestmark = pytest.mark.integration

TODAY = date(2026, 6, 30)

DGS10 = SeriesDef(
    code="DGS10",
    name="10y Treasury",
    category="Treasury",
    frequency="D",
    publication_lag_days=1,
    min_value=-2,
    max_value=25,
)
CPITEST = SeriesDef(
    code="CPITEST",
    name="Test CPI",
    category="Inflation",
    frequency="M",
    publication_lag_days=45,
    min_value=0,
    max_value=1000,
)
CATALOG = MacroCatalog(version=1, series=(DGS10, CPITEST))


def daily_frame(start: date, end: date, level: float = 4.0) -> pd.DataFrame:
    days = []
    day = start
    while day <= end:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return pd.DataFrame(
        {"obs_date": days, "value": [round(level + i * 0.01, 4) for i in range(len(days))]}
    )


def monthly_frame(months: list[date], start_level: float = 300.0) -> pd.DataFrame:
    return pd.DataFrame(
        {"obs_date": months, "value": [round(start_level + i, 2) for i in range(len(months))]}
    )


MONTHS_2026 = [date(2026, m, 1) for m in range(1, 6)]  # Jan..May


class FakeFred:
    name = "FRED"

    def __init__(self) -> None:
        self.frames: dict[str, pd.DataFrame] = {}
        self.calls: list[tuple[str, date, date]] = []

    def set(self, code: str, frame: pd.DataFrame) -> None:
        self.frames[code] = frame

    def patch(self, code: str, d: date, value: float) -> None:
        frame = self.frames[code]
        frame.loc[frame["obs_date"] == d, "value"] = value

    def fetch_series(self, provider_code: str, start: date, end: date) -> pd.DataFrame:
        self.calls.append((provider_code, start, end))
        frame = self.frames.get(provider_code, empty_macro_frame())
        if frame.empty:
            return frame.copy()
        return frame[(frame["obs_date"] >= start) & (frame["obs_date"] <= end)].reset_index(
            drop=True
        )


class MacroEnv:
    def __init__(
        self, factory: sessionmaker[Session], settings: Settings, provider: FakeFred
    ) -> None:
        self.factory = factory
        self.settings = settings
        self.provider = provider
        self.today = TODAY
        self.catalog = CATALOG

    def ingest(self, codes: list[str] | None = None):
        with session_scope(self.factory) as session:
            service = MacroIngestionService(
                session=session,
                provider=self.provider,
                archive=RawDataArchive(self.settings.rawdata_root),
                settings=self.settings,
                catalog=self.catalog,
                sleep=lambda _s: None,
                today=lambda: self.today,
            )
            run, outcomes = service.ingest(codes)
            return (
                run.id,
                run.status,
                run.rows_inserted,
                run.rows_updated,
                run.error_detail,
                {o.code: o for o in outcomes},
            )

    def observations(self, code: str) -> dict[date, tuple]:
        with session_scope(self.factory) as session:
            series = MacroRepository(session).get_series("FRED", code)
            rows = session.scalars(
                select(MacroObservation).where(MacroObservation.series_id == series.id)
            )
            return {r.obs_date: (r.value, r.first_seen_at, r.last_updated_at) for r in rows}

    def issues(self, rule: str) -> list[DataQualityIssue]:
        with session_scope(self.factory) as session:
            issues = list(
                session.scalars(select(DataQualityIssue).where(DataQualityIssue.rule == rule))
            )
            session.expunge_all()
            return issues

    def revisions(self) -> list[DataRevision]:
        with session_scope(self.factory) as session:
            rows = list(session.scalars(select(DataRevision)))
            session.expunge_all()
            return rows


@pytest.fixture()
def env(
    migrated_schema: None,
    session_factory: sessionmaker[Session],
    test_database_url: str,
    tmp_path: Path,
) -> MacroEnv:
    settings = Settings(
        database_url=test_database_url,
        rawdata_root=tmp_path / "RawData",
        history_start_date=date(2026, 1, 1),
        retry_max_attempts=3,
        retry_backoff_seconds=0.01,
        _env_file=None,
    )
    return MacroEnv(session_factory, settings, FakeFred())


# -- gate: idempotency ------------------------------------------------------


def test_reingest_is_idempotent(env: MacroEnv) -> None:
    env.provider.set("DGS10", daily_frame(date(2026, 6, 1), date(2026, 6, 26)))

    _, status1, inserted1, updated1, _, _ = env.ingest(["DGS10"])
    before = env.observations("DGS10")

    _, status2, inserted2, updated2, _, _ = env.ingest(["DGS10"])
    after = env.observations("DGS10")

    assert status1 is RunStatus.SUCCESS and inserted1 == len(before)
    assert status2 is RunStatus.SUCCESS
    assert inserted2 == 0 and updated2 == 0
    assert before == after  # identical values AND timestamps


# -- gate: header/detail integrity -------------------------------------------


def test_unknown_series_code_fails_loudly(env: MacroEnv) -> None:
    env.provider.set("DGS10", daily_frame(date(2026, 6, 1), date(2026, 6, 5)))

    _, status, _, _, error_detail, outcomes = env.ingest(["DGS10", "NOPE"])

    assert status is RunStatus.PARTIAL
    assert outcomes["NOPE"].status == "failed"
    assert "not in fred_series.yaml" in error_detail["failed_series"]["NOPE"]
    assert outcomes["DGS10"].status == "ok"  # isolation


def test_new_catalog_entry_needs_no_migration(env: MacroEnv) -> None:
    new_series = SeriesDef(
        code="NEWSER",
        name="Newly Added",
        category="Test",
        frequency="M",
        publication_lag_days=30,
        min_value=0,
        max_value=100,
    )
    env.catalog = MacroCatalog(version=2, series=(DGS10, CPITEST, new_series))
    env.provider.set("NEWSER", monthly_frame(MONTHS_2026, start_level=50.0))

    _, status, inserted, _, _, _ = env.ingest(["NEWSER"])

    assert status is RunStatus.SUCCESS and inserted == len(MONTHS_2026)
    with session_scope(env.factory) as session:
        header = MacroRepository(session).get_series("FRED", "NEWSER")
        assert header is not None
        assert header.publication_lag_days == 30  # header row from catalog, no DDL


def test_catalog_metadata_changes_propagate(env: MacroEnv) -> None:
    env.provider.set("DGS10", daily_frame(date(2026, 6, 1), date(2026, 6, 5)))
    env.ingest(["DGS10"])

    revised = SeriesDef(
        code="DGS10",
        name="10y Treasury",
        category="Treasury",
        frequency="D",
        publication_lag_days=2,
        min_value=-2,
        max_value=25,  # lag corrected
    )
    env.catalog = MacroCatalog(version=2, series=(revised, CPITEST))
    env.ingest(["DGS10"])

    with session_scope(env.factory) as session:
        header = MacroRepository(session).get_series("FRED", "DGS10")
        assert header.publication_lag_days == 2


# -- gate: frequency conformity ------------------------------------------------


def test_monthly_series_with_extra_observation_flagged(env: MacroEnv) -> None:
    frame = monthly_frame(MONTHS_2026)
    extra = pd.DataFrame({"obs_date": [date(2026, 1, 15)], "value": [300.5]})
    env.provider.set("CPITEST", pd.concat([frame, extra], ignore_index=True))

    _, status, inserted, _, _, _ = env.ingest(["CPITEST"])

    assert status is RunStatus.SUCCESS
    assert inserted == len(MONTHS_2026) + 1  # rows load
    issues = env.issues(RULE_FREQUENCY_MISMATCH)
    assert len(issues) == 1
    assert issues[0].severity is IssueSeverity.WARNING


# -- gate: revision detection ---------------------------------------------------


def test_revised_value_updates_and_is_ledgered(env: MacroEnv) -> None:
    env.provider.set("CPITEST", monthly_frame(MONTHS_2026))
    env.ingest(["CPITEST"])
    original = env.observations("CPITEST")

    revised_month = date(2026, 3, 1)  # within the 6-month overlap
    env.provider.patch("CPITEST", revised_month, 999.99)
    _, status, _, updated, _, outcomes = env.ingest(["CPITEST"])

    assert status is RunStatus.SUCCESS and updated == 1
    assert outcomes["CPITEST"].revisions == 1

    revisions = env.revisions()
    assert len(revisions) == 1
    assert revisions[0].table_name == "macro_observations"
    assert revisions[0].entity_key == f"CPITEST/{revised_month}"
    assert revisions[0].field == "value"
    assert revisions[0].old_value == "302.000000"
    assert revisions[0].new_value == "999.990000"

    after = env.observations("CPITEST")
    assert float(after[revised_month][0]) == 999.99
    assert after[revised_month][2] > original[revised_month][2]  # last_updated bumped
    assert after[revised_month][1] == original[revised_month][1]  # first_seen preserved


# -- gate: FRED '.' -> NULL ------------------------------------------------------


def test_missing_marker_stored_as_null_not_zero(env: MacroEnv) -> None:
    frame = daily_frame(date(2026, 6, 1), date(2026, 6, 5))
    frame.loc[frame["obs_date"] == date(2026, 6, 3), "value"] = float("nan")
    env.provider.set("DGS10", frame)

    _, _, inserted, _, _, _ = env.ingest(["DGS10"])

    observations = env.observations("DGS10")
    assert inserted == len(observations)
    assert date(2026, 6, 3) in observations  # row exists
    assert observations[date(2026, 6, 3)][0] is None  # NULL, not zero


# -- gate: invalid values quarantined --------------------------------------------


def test_out_of_range_value_quarantined_with_sidecar(env: MacroEnv) -> None:
    frame = daily_frame(date(2026, 6, 1), date(2026, 6, 5))
    frame.loc[frame["obs_date"] == date(2026, 6, 3), "value"] = 99.0  # yield of 99%
    env.provider.set("DGS10", frame)

    _, _, _, _, _, outcomes = env.ingest(["DGS10"])

    assert outcomes["DGS10"].quarantined == 1
    assert date(2026, 6, 3) not in env.observations("DGS10")
    issues = env.issues(RULE_VALUE_OUT_OF_RANGE)
    assert len(issues) == 1 and issues[0].entity_key == "DGS10/2026-06-03"
    sidecars = list((env.settings.rawdata_root / "macro" / "DGS10").glob("*.rejected.csv"))
    assert len(sidecars) == 1


# -- gate: staleness ---------------------------------------------------------------


def test_stale_series_flagged(env: MacroEnv) -> None:
    env.provider.set("DGS10", daily_frame(date(2026, 1, 2), date(2026, 2, 27)))
    env.today = date(2026, 6, 30)  # silent for ~4 months; allowance is 1 + 3 days

    env.ingest(["DGS10"])

    issues = env.issues(RULE_STALE_SERIES)
    assert len(issues) == 1
    assert issues[0].severity is IssueSeverity.WARNING


# -- gate: publication lag enforcement ----------------------------------------------


def test_observations_invisible_before_publication_lag(env: MacroEnv) -> None:
    env.provider.set("CPITEST", monthly_frame(MONTHS_2026))
    env.ingest(["CPITEST"])

    may = date(2026, 5, 1)  # lag 45 -> knowable from 2026-06-15
    with session_scope(env.factory) as session:
        repo = MacroRepository(session)
        series = repo.get_series("FRED", "CPITEST")

        before = repo.observations_available_as_of(series.id, may + timedelta(days=44))
        after = repo.observations_available_as_of(series.id, may + timedelta(days=45))

        assert may not in {o.obs_date for o in before}  # not yet public
        assert may in {o.obs_date for o in after}  # lag elapsed
        # earlier months (lag long elapsed) visible in both
        assert date(2026, 1, 1) in {o.obs_date for o in before}
