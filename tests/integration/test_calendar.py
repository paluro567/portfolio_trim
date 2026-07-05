"""Phase 1 gate tests: trading calendar persistence."""

from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from mip.core.db import session_scope
from mip.domain.models import TradingDay
from mip.reference.calendar import build_trading_calendar

pytestmark = pytest.mark.integration


def _dates(session: Session) -> dict[date, bool]:
    return {
        row.calendar_date: row.is_half_day
        for row in session.scalars(select(TradingDay).order_by(TradingDay.calendar_date))
    }


def test_build_persists_sessions_and_flags(
    migrated_schema: None, session_factory: sessionmaker[Session]
) -> None:
    with session_scope(session_factory) as session:
        count = build_trading_calendar(session, start=date(2025, 11, 1), end=date(2025, 12, 31))

    with session_scope(session_factory) as session:
        days = _dates(session)

    assert len(days) == count
    assert all(d.weekday() < 5 for d in days)  # no weekends
    assert date(2025, 11, 27) not in days  # Thanksgiving
    assert date(2025, 12, 25) not in days  # Christmas
    assert days[date(2025, 11, 28)] is True  # half day flagged
    assert days[date(2025, 12, 24)] is True
    assert days[date(2025, 12, 26)] is False


def test_build_is_idempotent(migrated_schema: None, session_factory: sessionmaker[Session]) -> None:
    start, end = date(2026, 1, 1), date(2026, 3, 31)

    with session_scope(session_factory) as session:
        first = build_trading_calendar(session, start=start, end=end)
    with session_scope(session_factory) as session:
        second = build_trading_calendar(session, start=start, end=end)

    with session_scope(session_factory) as session:
        rows = session.execute(select(func.count()).select_from(TradingDay)).scalar_one()

    assert first == second == rows  # re-run adds nothing


def test_contiguous_coverage_in_db(
    migrated_schema: None, session_factory: sessionmaker[Session]
) -> None:
    with session_scope(session_factory) as session:
        build_trading_calendar(session, start=date(2026, 1, 1), end=date(2026, 12, 31))

    with session_scope(session_factory) as session:
        dates = sorted(_dates(session))

    assert dates[0] == date(2026, 1, 2)  # Jan 1 is a holiday
    assert 250 <= len(dates) <= 253
    gaps = [(b - a).days for a, b in zip(dates, dates[1:], strict=False)]
    assert max(gaps) <= 4  # no gap longer than a long weekend
    assert date(2026, 7, 3) not in dates  # observed Independence Day
