"""Session-rule tests (pure computation, no database).

Known-date assertions per NYSE rules:
- 2026-07-03 (Fri): Independence Day observed -> closed
- 2026-06-19 (Fri): Juneteenth -> closed
- 2025-11-28 (Fri after Thanksgiving) and 2025-12-24: early closes
"""

from datetime import date

import pytest

from mip.core.exceptions import ConfigurationError
from mip.reference.calendar import trading_sessions


def test_holidays_and_weekends_excluded() -> None:
    sessions = trading_sessions(date(2026, 6, 29), date(2026, 7, 7))
    dates = [s.calendar_date for s in sessions]

    assert date(2026, 7, 3) not in dates  # observed Independence Day
    assert date(2026, 7, 4) not in dates  # Saturday
    assert date(2026, 7, 5) not in dates  # Sunday
    assert dates == [
        date(2026, 6, 29),
        date(2026, 6, 30),
        date(2026, 7, 1),
        date(2026, 7, 2),
        date(2026, 7, 6),
        date(2026, 7, 7),
    ]


def test_juneteenth_2026_excluded() -> None:
    sessions = trading_sessions(date(2026, 6, 15), date(2026, 6, 22))
    dates = [s.calendar_date for s in sessions]
    assert date(2026, 6, 19) not in dates
    assert date(2026, 6, 18) in dates
    assert date(2026, 6, 22) in dates


def test_half_days_flagged() -> None:
    sessions = trading_sessions(date(2025, 11, 24), date(2025, 12, 31))
    by_date = {s.calendar_date: s.is_half_day for s in sessions}

    assert by_date[date(2025, 11, 28)] is True  # day after Thanksgiving
    assert by_date[date(2025, 12, 24)] is True  # Christmas Eve
    assert date(2025, 11, 27) not in by_date  # Thanksgiving closed
    assert date(2025, 12, 25) not in by_date  # Christmas closed
    assert by_date[date(2025, 12, 26)] is False  # regular session


def test_contiguous_coverage() -> None:
    sessions = trading_sessions(date(2024, 1, 1), date(2024, 12, 31))
    dates = [s.calendar_date for s in sessions]

    assert 250 <= len(dates) <= 253  # a full NYSE year
    assert all(d.weekday() < 5 for d in dates)  # never weekends
    gaps = [(b - a).days for a, b in zip(dates, dates[1:], strict=False)]
    assert max(gaps) <= 4  # nothing longer than a long weekend


def test_unknown_exchange_rejected() -> None:
    with pytest.raises(ConfigurationError, match="unknown exchange"):
        trading_sessions(date(2026, 1, 1), date(2026, 2, 1), exchange="LSE")


def test_inverted_range_rejected() -> None:
    with pytest.raises(ConfigurationError, match="inverted"):
        trading_sessions(date(2026, 2, 1), date(2026, 1, 1))
