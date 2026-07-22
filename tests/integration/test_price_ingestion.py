"""Phase 2 gate tests: the full price-ingestion flow against Postgres,
with a fake provider (no network)."""

from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from mip.core.config import Settings
from mip.core.db import session_scope
from mip.core.exceptions import PermanentError, TransientError
from mip.domain.enums import InstrumentType, IssueSeverity, IssueStatus, RunStatus
from mip.domain.models import DailyPrice, DataQualityIssue, DataRevision, TradingDay
from mip.ingestion.archive import RawDataArchive
from mip.ingestion.price_service import PriceIngestionService
from mip.ingestion.validation import RULE_OHLC_INCOHERENT, RULE_RETURN_JUMP, RULE_ZERO_VOLUME
from mip.providers.base import PriceFetch, empty_action_frame, empty_price_frame
from mip.repositories.instruments import InstrumentRepository
from mip.repositories.quality import QualityRepository

pytestmark = pytest.mark.integration

JUNE_START, JUNE_END = date(2026, 6, 1), date(2026, 6, 30)


def weekdays(start: date, end: date) -> list[date]:
    day, out = start, []
    while day <= end:
        if day.weekday() < 5:
            out.append(day)
        day += timedelta(days=1)
    return out


def price_row(d: date, close: float, **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "price_date": d,
        "open": round(close * 0.99, 4),
        "high": round(close * 1.01, 4),
        "low": round(close * 0.98, 4),
        "close": close,
        "adj_close": close,
        "volume": 1_000,
    }
    base.update(overrides)
    return base


def steady_history(dates: list[date], level: float = 100.0) -> list[dict[str, object]]:
    return [price_row(d, round(level + i * 0.5, 2)) for i, d in enumerate(dates)]


class FakeProvider:
    name = "fake"

    def __init__(self) -> None:
        self.frames: dict[str, pd.DataFrame] = {}
        self.actions: dict[str, pd.DataFrame] = {}
        self.errors: dict[str, Exception] = {}
        self.calls: list[tuple[str, date, date]] = []

    def set_history(self, symbol: str, rows: list[dict[str, object]]) -> None:
        self.frames[symbol] = pd.DataFrame(rows)

    def set_actions(self, symbol: str, rows: list[dict[str, object]]) -> None:
        self.actions[symbol] = pd.DataFrame(rows)

    def patch(self, symbol: str, d: date, **changes: object) -> None:
        frame = self.frames[symbol]
        for column, value in changes.items():
            frame.loc[frame["price_date"] == d, column] = value

    def fetch_daily(self, symbol: str, start: date, end: date) -> PriceFetch:
        self.calls.append((symbol, start, end))
        if symbol in self.errors:
            raise self.errors[symbol]
        frame = self.frames.get(symbol, empty_price_frame())
        if not frame.empty:
            frame = frame[
                (frame["price_date"] >= start) & (frame["price_date"] <= end)
            ].reset_index(drop=True)
        actions = self.actions.get(symbol, empty_action_frame())
        if not actions.empty:
            actions = actions[
                (actions["ex_date"] >= start) & (actions["ex_date"] <= end)
            ].reset_index(drop=True)
        return PriceFetch(prices=frame.copy(), actions=actions.copy())


class PriceEnv:
    """One migrated database with instruments, calendar, archive, provider."""

    def __init__(
        self, factory: sessionmaker[Session], settings: Settings, provider: FakeProvider
    ) -> None:
        self.factory = factory
        self.settings = settings
        self.provider = provider
        self.today = JUNE_END

    def ingest(self, symbols: list[str] | None = None, full_refresh: bool = False):
        with session_scope(self.factory) as session:
            service = PriceIngestionService(
                session=session,
                provider=self.provider,
                archive=RawDataArchive(self.settings.rawdata_root),
                settings=self.settings,
                sleep=lambda _s: None,
                today=lambda: self.today,
                # deterministic clock: 11pm Eastern on `today`, i.e. well
                # after close+buffer, so `today` (a synthetic session) is
                # treated as COMPLETE and fetch_end resolves to it.
                now=lambda: datetime.combine(
                    self.today, time(23, 0), tzinfo=ZoneInfo("America/New_York")
                ),
            )
            run, outcomes = service.ingest(symbols, full_refresh=full_refresh)
            session.flush()
            return (
                run.id,
                run.status,
                run.rows_inserted,
                run.rows_updated,
                run.error_detail,
                {o.symbol: o for o in outcomes},
            )

    def prices(self, symbol: str) -> dict[date, tuple]:
        with session_scope(self.factory) as session:
            instrument = InstrumentRepository(session).get_by_symbol(symbol)
            rows = session.scalars(
                select(DailyPrice).where(DailyPrice.instrument_id == instrument.id)
            )
            return {
                r.price_date: (
                    r.open,
                    r.high,
                    r.low,
                    r.close,
                    r.adj_close,
                    r.volume,
                    r.first_seen_at,
                    r.last_updated_at,
                )
                for r in rows
            }

    def issues(self, rule: str | None = None) -> list[DataQualityIssue]:
        with session_scope(self.factory) as session:
            stmt = select(DataQualityIssue)
            if rule:
                stmt = stmt.where(DataQualityIssue.rule == rule)
            issues = list(session.scalars(stmt))
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
) -> PriceEnv:
    with session_scope(session_factory) as session:
        repo = InstrumentRepository(session)
        for symbol in ("TEST1", "TEST2", "JUMP", "SPLITCO", "BROKEN", "SNOWCO", "DIVCO"):
            repo.create_instrument(symbol, InstrumentType.STOCK, effective_date=JUNE_START)
        session.add_all(
            TradingDay(exchange="NYSE", calendar_date=d) for d in weekdays(JUNE_START, JUNE_END)
        )

    settings = Settings(
        database_url=test_database_url,
        rawdata_root=tmp_path / "RawData",
        history_start_date=JUNE_START,
        overlap_trading_days=5,
        retry_max_attempts=3,
        retry_backoff_seconds=0.01,
        _env_file=None,
    )
    return PriceEnv(session_factory, settings, FakeProvider())


DAYS = weekdays(JUNE_START, JUNE_END)  # 22 synthetic sessions


# -- gate: idempotency ---------------------------------------------------


def test_reingest_is_idempotent(env: PriceEnv) -> None:
    env.provider.set_history("TEST1", steady_history(DAYS))

    _, status1, inserted1, updated1, _, _ = env.ingest(["TEST1"])
    before = env.prices("TEST1")

    _, status2, inserted2, updated2, _, _ = env.ingest(["TEST1"])
    after = env.prices("TEST1")

    assert status1 is RunStatus.SUCCESS and inserted1 == len(DAYS)
    assert status2 is RunStatus.SUCCESS
    assert inserted2 == 0 and updated2 == 0  # second run is a no-op
    assert before == after  # identical values AND timestamps


# -- gate: incremental cursor with overlap --------------------------------


def test_incremental_cursor_includes_overlap(env: PriceEnv) -> None:
    cutoff = date(2026, 6, 15)
    early = [d for d in DAYS if d <= cutoff]
    env.provider.set_history("TEST1", steady_history(early))
    env.today = cutoff
    env.ingest(["TEST1"])

    env.provider.set_history("TEST1", steady_history(DAYS))  # history extends
    env.today = JUNE_END
    _, _, inserted, updated, _, _ = env.ingest(["TEST1"])

    symbol, start, end = env.provider.calls[-1]
    overlap_sessions = [d for d in early if d <= cutoff][-5:]
    assert start == overlap_sessions[0]  # 5 sessions re-fetched, not full history
    assert start < cutoff < end
    assert inserted == len(DAYS) - len(early)  # only genuinely new rows
    assert updated == 0  # unchanged overlap -> no updates


# -- gate: revision detection + adj_close tripwire -------------------------


def test_revision_detected_and_tripwire_full_refresh(env: PriceEnv) -> None:
    env.provider.set_history("TEST1", steady_history(DAYS))
    env.ingest(["TEST1"])
    original = env.prices("TEST1")

    inside_overlap = DAYS[-3]  # within the 5-session window
    outside_overlap = DAYS[2]  # only reachable via full refresh
    env.provider.patch("TEST1", inside_overlap, adj_close=55.5)
    env.provider.patch("TEST1", outside_overlap, adj_close=44.4)

    _, status, _, updated, _, outcomes = env.ingest(["TEST1"])

    assert status is RunStatus.SUCCESS
    assert outcomes["TEST1"].full_refresh is True  # tripwire fired
    assert env.provider.calls[-1][1] == JUNE_START  # refresh re-fetched full history
    assert updated == 2

    revised = {(r.entity_key, r.field): (r.old_value, r.new_value) for r in env.revisions()}
    assert (f"TEST1/{inside_overlap}", "adj_close") in revised
    assert (f"TEST1/{outside_overlap}", "adj_close") in revised

    after = env.prices("TEST1")
    assert float(after[inside_overlap][4]) == 55.5
    assert float(after[outside_overlap][4]) == 44.4
    for d in (inside_overlap, outside_overlap):
        first_seen, last_updated = after[d][6], after[d][7]
        assert last_updated > first_seen  # bumped
        assert after[d][6] == original[d][6]  # first_seen preserved
    untouched = DAYS[5]
    assert after[untouched] == original[untouched]


# -- gate: quarantine -----------------------------------------------------


def test_error_row_quarantined_with_sidecar(env: PriceEnv) -> None:
    bad_day = DAYS[3]
    rows = steady_history(DAYS[:8])
    rows[3] = price_row(bad_day, 100.0, high=90.0, low=95.0)  # high < low
    env.provider.set_history("TEST2", rows)
    env.today = DAYS[7]

    _, status, inserted, _, _, outcomes = env.ingest(["TEST2"])

    assert status is RunStatus.SUCCESS
    assert inserted == 7 and outcomes["TEST2"].quarantined == 1
    assert bad_day not in env.prices("TEST2")  # excluded from fact table

    issues = env.issues(RULE_OHLC_INCOHERENT)
    assert len(issues) == 1
    assert issues[0].entity_key == f"TEST2/{bad_day}"
    assert issues[0].severity is IssueSeverity.ERROR

    sidecars = list((env.settings.rawdata_root / "prices" / "TEST2").glob("*.rejected.csv"))
    assert len(sidecars) == 1
    assert str(bad_day) in sidecars[0].read_text()


def test_warning_row_loads_and_is_flagged(env: PriceEnv) -> None:
    rows = steady_history(DAYS[:5])
    rows[2] = price_row(DAYS[2], 101.0, volume=0)
    env.provider.set_history("TEST2", rows)
    env.today = DAYS[4]

    _, _, inserted, _, _, outcomes = env.ingest(["TEST2"])

    assert inserted == 5  # warning row loaded
    assert outcomes["TEST2"].warnings >= 1
    issues = env.issues(RULE_ZERO_VOLUME)
    assert len(issues) == 1
    assert issues[0].severity is IssueSeverity.WARNING


# -- gate: return-jump rule vs corporate actions ----------------------------


def test_big_move_with_matching_split_passes(env: PriceEnv) -> None:
    split_day = DAYS[5]
    rows = steady_history(DAYS[:5], level=100.0)
    rows += [price_row(d, 51.0 + i * 0.2) for i, d in enumerate(DAYS[5:10])]  # 2:1 split
    env.provider.set_history("SPLITCO", rows)
    env.provider.set_actions(
        "SPLITCO",
        [
            {
                "action_type": "split",
                "ex_date": split_day,
                "split_ratio": 2.0,
                "cash_amount": float("nan"),
            }
        ],
    )
    env.today = DAYS[9]

    _, status, inserted, _, _, _ = env.ingest(["SPLITCO"])

    assert status is RunStatus.SUCCESS and inserted == 10
    assert env.issues(RULE_RETURN_JUMP) == []  # split explains the move
    assert split_day in env.prices("SPLITCO")


def test_big_move_without_action_flagged_then_accepted(env: PriceEnv) -> None:
    jump_day = DAYS[5]
    rows = steady_history(DAYS[:10])
    rows[5] = price_row(jump_day, 150.0)  # +47% spike, no action
    rows[6] = price_row(DAYS[6], 103.0)  # back to trend
    env.provider.set_history("JUMP", rows)
    env.today = DAYS[9]

    _, _, _, _, _, outcomes = env.ingest(["JUMP"])
    assert outcomes["JUMP"].quarantined == 1
    assert jump_day not in env.prices("JUMP")
    issues = env.issues(RULE_RETURN_JUMP)
    assert len(issues) == 1

    # human confirms the move is real -> accept -> re-ingest loads the row
    with session_scope(env.factory) as session:
        QualityRepository(session).set_status(issues[0].id, IssueStatus.ACCEPTED)
    _, _, inserted, _, _, _ = env.ingest(["JUMP"])

    assert inserted == 1  # exactly the previously quarantined row backfilled
    assert jump_day in env.prices("JUMP")
    still_open = [i for i in env.issues(RULE_RETURN_JUMP) if i.status is IssueStatus.OPEN]
    assert still_open == []  # not re-flagged


# -- gate: archive path + partial failure + retry ----------------------------


def test_archive_path_recorded_and_files_exist(env: PriceEnv) -> None:
    env.provider.set_history("TEST1", steady_history(DAYS[:5]))
    env.today = DAYS[4]

    run_id, _, _, _, _, _ = env.ingest(["TEST1"])

    with session_scope(env.factory) as session:
        from mip.domain.models import IngestionRun

        run = session.get(IngestionRun, run_id)
        assert run.archive_path == str(env.settings.rawdata_root / "prices")
    files = list((env.settings.rawdata_root / "prices" / "TEST1").glob("*.csv"))
    assert len(files) == 1 and f"run{run_id}" in files[0].name


def test_partial_failure_isolates_symbols(env: PriceEnv) -> None:
    env.provider.set_history("TEST1", steady_history(DAYS[:5]))
    env.provider.errors["BROKEN"] = PermanentError("no such listing")
    env.today = DAYS[4]

    _, status, inserted, _, error_detail, outcomes = env.ingest(["TEST1", "BROKEN"])

    assert status is RunStatus.PARTIAL
    assert inserted == 5  # healthy symbol fully loaded
    assert outcomes["BROKEN"].status == "failed"
    assert "no such listing" in error_detail["failed_symbols"]["BROKEN"]


def test_transient_errors_are_retried(env: PriceEnv) -> None:
    attempts = {"n": 0}
    real_fetch = env.provider.fetch_daily

    def flaky(symbol: str, start: date, end: date) -> PriceFetch:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise TransientError("rate limited")
        return real_fetch(symbol, start, end)

    env.provider.fetch_daily = flaky  # type: ignore[method-assign]
    env.provider.set_history("TEST1", steady_history(DAYS[:5]))
    env.today = DAYS[4]

    _, status, inserted, _, _, _ = env.ingest(["TEST1"])

    assert status is RunStatus.SUCCESS and inserted == 5
    assert attempts["n"] == 3  # two transient failures absorbed


# ======================================================================
# Regression: 2026-07-20 tripwire-storm bug fix (docs/PRICES.md).
# ======================================================================


def _seed(env: PriceEnv, symbol: str = "TEST1") -> dict[date, tuple]:
    """First full ingest of a clean steady history; returns stored rows."""
    env.provider.set_history(symbol, steady_history(DAYS))
    env.ingest([symbol])
    return env.prices(symbol)


def test_unchanged_overlap_is_incremental_not_full_refresh(env: PriceEnv) -> None:
    """1. A normal second run with identical provider data fetches only the
    overlap window, records nothing, and never full-refreshes."""
    _seed(env)
    _, status, inserted, updated, _, outcomes = env.ingest(["TEST1"])

    assert status is RunStatus.SUCCESS
    assert (inserted, updated) == (0, 0)
    assert outcomes["TEST1"].full_refresh is False
    assert outcomes["TEST1"].revisions == 0
    assert env.revisions() == []
    _, start, _ = env.provider.calls[-1]
    assert start != env.settings.history_start_date  # overlap window, not 2010->


def test_subtolerance_float_noise_creates_no_revisions(env: PriceEnv) -> None:
    """2. adj_close jitter below the materiality gate is ignored entirely —
    no revision, no update, no tripwire, stored value untouched."""
    stored = _seed(env)
    noisy_day = DAYS[-3]
    stored_adj = float(stored[noisy_day][4])
    env.provider.patch("TEST1", noisy_day, adj_close=stored_adj + 0.0003)  # << 1e-5 rel

    _, status, _, updated, _, outcomes = env.ingest(["TEST1"])

    assert status is RunStatus.SUCCESS
    assert updated == 0 and outcomes["TEST1"].revisions == 0
    assert outcomes["TEST1"].full_refresh is False
    assert env.revisions() == []
    assert env.prices("TEST1")[noisy_day][4] == stored[noisy_day][4]  # unchanged


def test_raw_vs_adjusted_mismatch_fails_as_semantic_error(env: PriceEnv) -> None:
    """3. A systematic raw-close shift across the overlap with no split is a
    config/semantics error — the symbol fails loudly, and the savepoint
    leaves ZERO false revisions rather than rewriting history."""
    stored = _seed(env)
    rows = steady_history(DAYS)
    for i, d in enumerate(DAYS):
        if d in DAYS[-5:]:  # the whole overlap window, uniformly re-scaled
            for col in ("open", "high", "low", "close", "adj_close"):
                rows[i][col] = round(rows[i][col] * 0.9, 4)
    env.provider.set_history("TEST1", rows)

    _, status, _, updated, error_detail, outcomes = env.ingest(["TEST1"])

    assert status is RunStatus.FAILED
    assert outcomes["TEST1"].status == "failed"
    assert "raw-vs-adjusted" in error_detail["failed_symbols"]["TEST1"]
    assert updated == 0 and env.revisions() == []  # nothing committed
    assert env.prices("TEST1")[DAYS[-3]] == stored[DAYS[-3]]  # rolled back intact


def test_new_split_triggers_exactly_one_full_refresh(env: PriceEnv) -> None:
    """4. A newly arrived split restates raw history -> exactly one full
    refresh; the immediately following run is idempotent."""
    env.provider.set_history("SPLITCO", steady_history(DAYS))
    env.ingest(["SPLITCO"])

    split_day = DAYS[-2]
    rows = steady_history(DAYS)
    for i, d in enumerate(DAYS):  # provider restates pre-split raw prices to new units
        if d < split_day:
            for col in ("open", "high", "low", "close", "adj_close"):
                rows[i][col] = round(rows[i][col] / 2, 4)
    env.provider.set_history("SPLITCO", rows)
    env.provider.set_actions(
        "SPLITCO",
        [
            {
                "action_type": "split",
                "ex_date": split_day,
                "split_ratio": 2.0,
                "cash_amount": float("nan"),
            }
        ],
    )

    _, status, _, _, _, outcomes = env.ingest(["SPLITCO"])
    assert status is RunStatus.SUCCESS
    assert outcomes["SPLITCO"].full_refresh is True
    assert outcomes["SPLITCO"].revisions > 0  # genuine split reconciliation recorded

    again = env.ingest(["SPLITCO"])
    assert again[-1]["SPLITCO"].full_refresh is False  # not re-triggered
    assert again[2] == 0 and again[3] == 0  # idempotent: no inserts/updates


def test_dividend_backadjustment_refreshes_and_records_adj_close(env: PriceEnv) -> None:
    """5. A dividend back-adjustment (adj_close moves, raw close does not) on
    a completed historical session escalates once and records adj_close
    revisions — raw close is never rewritten."""
    stored = _seed(env, "DIVCO")
    hist_day = DAYS[-3]
    env.provider.patch("DIVCO", hist_day, adj_close=float(stored[hist_day][4]) - 0.5)

    _, status, _, _, _, outcomes = env.ingest(["DIVCO"])

    assert status is RunStatus.SUCCESS
    assert outcomes["DIVCO"].full_refresh is True
    fields = {(r.entity_key, r.field) for r in env.revisions()}
    assert (f"DIVCO/{hist_day}", "adj_close") in fields
    assert (f"DIVCO/{hist_day}", "close") not in fields  # raw close preserved
    assert env.prices("DIVCO")[hist_day][3] == stored[hist_day][3]  # raw close unchanged


def test_genuine_single_row_correction_records_one_revision_no_storm(env: PriceEnv) -> None:
    """6. A real spot correction (close AND adj_close move on one day) is an
    ordinary revision — one row updated, no full-history refresh."""
    stored = _seed(env)
    fix_day = DAYS[-4]
    # a coherent correction: +0.5 stays inside the row's unchanged high/low
    corrected = float(stored[fix_day][3]) + 0.5
    env.provider.patch("TEST1", fix_day, close=corrected, adj_close=corrected)

    _, status, _, updated, _, outcomes = env.ingest(["TEST1"])

    assert status is RunStatus.SUCCESS
    assert outcomes["TEST1"].full_refresh is False  # close moved too -> not a re-adjustment
    assert updated == 1
    fields = {(r.entity_key, r.field) for r in env.revisions()}
    assert fields == {(f"TEST1/{fix_day}", "close"), (f"TEST1/{fix_day}", "adj_close")}


def test_full_refresh_totals_are_not_double_counted(env: PriceEnv) -> None:
    """8. The incremental+refresh passes report one coherent set of totals:
    each changed date counted once, DB revisions == reported revisions, and
    the refresh breakdown is consistent."""
    stored = _seed(env)
    inside, outside = DAYS[-3], DAYS[2]  # one in the overlap, one only reachable via refresh
    env.provider.patch("TEST1", inside, adj_close=float(stored[inside][4]) - 0.5)
    env.provider.patch("TEST1", outside, adj_close=float(stored[outside][4]) - 0.5)

    _, status, _, updated, _, outcomes = env.ingest(["TEST1"])
    o = outcomes["TEST1"]

    assert o.full_refresh is True
    assert updated == 2  # exactly the two distinct changed dates, not 4
    assert o.revisions == len(env.revisions()) == 2  # no double-count vs the DB
    assert (o.refresh_updated, o.refresh_revisions) == (1, 1)  # 'outside' found in refresh
    dates = {r.entity_key for r in env.revisions()}
    assert dates == {f"TEST1/{inside}", f"TEST1/{outside}"}


def test_snow_rejected_archive_collision_is_resolved(env: PriceEnv) -> None:
    """9 & 10. SNOW's exact failure: a recently rejected (OHLC-incoherent)
    row is re-rejected by the tripwire's full-refresh pass over the same
    date. Old code hit `archive is immutable`; now the two passes archive
    under distinct identities and the symbol succeeds."""
    rows = steady_history(DAYS)
    bad_day = DAYS[-2]
    rows[DAYS.index(bad_day)] = price_row(bad_day, 108.0, high=90.0, low=95.0, adj_close=108.0)
    env.provider.set_history("SNOWCO", rows)
    _, _, _, _, _, first = env.ingest(["SNOWCO"])
    assert first["SNOWCO"].quarantined == 1  # incoherent row rejected on first load

    # a dividend back-adjustment now trips the tripwire; bad_day stays
    # incoherent so BOTH passes reject the same single date
    stored = env.prices("SNOWCO")
    hist_day = DAYS[-4]
    env.provider.patch("SNOWCO", hist_day, adj_close=float(stored[hist_day][4]) - 0.6)

    run_id, status, _, _, error_detail, second = env.ingest(["SNOWCO"])

    assert status is RunStatus.SUCCESS, error_detail
    assert second["SNOWCO"].status == "ok"  # no immutable-archive failure
    assert second["SNOWCO"].full_refresh is True
    sidecars = sorted(
        p.name for p in (env.settings.rawdata_root / "prices" / "SNOWCO").glob("*.rejected.csv")
    )
    # this run's incremental (unlabeled) and full-refresh (-full) rejects coexist
    assert f"{bad_day}_{bad_day}_run{run_id}.rejected.csv" in sidecars
    assert f"{bad_day}_{bad_day}_run{run_id}-full.rejected.csv" in sidecars


def test_failed_symbol_leaves_no_partial_mutations(env: PriceEnv) -> None:
    """8 (transactional). A symbol that fails after writing some rows in its
    incremental pass has ALL of those mutations rolled back by its savepoint,
    while healthy symbols in the same run commit normally."""
    healthy = _seed(env, "TEST2")  # noqa: F841 - establishes a committed baseline
    stored = _seed(env, "TEST1")
    # TEST1 will fail the semantic guard; TEST2 stays clean this run
    rows = steady_history(DAYS)
    for i, d in enumerate(DAYS):
        if d in DAYS[-5:]:
            for col in ("open", "high", "low", "close", "adj_close"):
                rows[i][col] = round(rows[i][col] * 0.9, 4)
    env.provider.set_history("TEST1", rows)
    env.provider.set_history("TEST2", steady_history(DAYS))

    _, status, _, _, error_detail, outcomes = env.ingest(["TEST1", "TEST2"])

    assert status is RunStatus.PARTIAL
    assert outcomes["TEST1"].status == "failed" and outcomes["TEST2"].status == "ok"
    assert "TEST1" in error_detail["failed_symbols"]
    # TEST1 fully rolled back: no revisions, stored values intact
    assert [r for r in env.revisions() if r.entity_key.startswith("TEST1/")] == []
    assert env.prices("TEST1")[DAYS[-3]] == stored[DAYS[-3]]
