"""Trading calendar builder.

Sessions come from the exchange-calendars package (holiday and early-close
rules maintained upstream) and are persisted into trading_calendar, the
canonical set of trading days every cursor, gap check, and feature
alignment joins against (ARCHITECTURE.md D13/§4.1).

trading_sessions() is a pure computation so the rules are unit-testable;
build_trading_calendar() adds the idempotent persistence.
"""

from dataclasses import dataclass
from datetime import date, time

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from mip.core.exceptions import ConfigurationError
from mip.core.logging import get_logger
from mip.domain.models import TradingDay

logger = get_logger(__name__)

# Platform exchange code -> exchange-calendars code and regular close time.
_EXCHANGES = {"NYSE": ("XNYS", time(16, 0))}


@dataclass(frozen=True)
class SessionDay:
    calendar_date: date
    is_half_day: bool


def trading_sessions(start: date, end: date, exchange: str = "NYSE") -> list[SessionDay]:
    """All trading sessions in [start, end], flagging early closes."""
    import exchange_calendars as xcals  # heavy import kept out of CLI startup

    if exchange not in _EXCHANGES:
        raise ConfigurationError(f"unknown exchange {exchange!r} (supported: {sorted(_EXCHANGES)})")
    if end < start:
        raise ConfigurationError(f"calendar range is inverted: {start} > {end}")

    xcals_code, regular_close = _EXCHANGES[exchange]
    calendar = xcals.get_calendar(xcals_code, start=str(start), end=str(end))

    closes = calendar.schedule["close"].dt.tz_convert(calendar.tz)
    return [
        SessionDay(calendar_date=session.date(), is_half_day=close.time() < regular_close)
        for session, close in closes.items()
    ]


def build_trading_calendar(session: Session, start: date, end: date, exchange: str = "NYSE") -> int:
    """Idempotently upsert sessions for [start, end]; returns session count."""
    days = trading_sessions(start=start, end=end, exchange=exchange)
    if not days:
        return 0

    stmt = pg_insert(TradingDay).values(
        [
            {"exchange": exchange, "calendar_date": d.calendar_date, "is_half_day": d.is_half_day}
            for d in days
        ]
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["exchange", "calendar_date"],
        set_={"is_half_day": stmt.excluded.is_half_day},
    )
    session.execute(stmt)

    half_days = sum(1 for d in days if d.is_half_day)
    logger.info(
        "calendar.built",
        exchange=exchange,
        start=str(start),
        end=str(end),
        sessions=len(days),
        half_days=half_days,
    )
    return len(days)
