"""Market-date resolution for the daily update.

The update always targets the LATEST COMPLETED NYSE session:

- before market close (+ a configurable data-availability buffer), today's
  session is not complete -> resolve to the previous session;
- after close + buffer, today resolves to itself (if a session);
- weekends and holidays resolve to the last session before them;
- an explicit --as-of D resolves to the last session <= D (never partial
  intraday data — D itself only counts once it is a completed session in
  the calendar and prices exist for it).

Pure given (now_eastern, session dates); the orchestrator supplies both.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from mip.core.exceptions import ConfigurationError

EASTERN = ZoneInfo("America/New_York")
MARKET_CLOSE = time(16, 0)


def now_eastern() -> datetime:
    return datetime.now(tz=EASTERN)


def resolve_market_date(
    sessions: list[date],
    now: datetime,
    close_buffer_minutes: int,
    as_of: date | None = None,
) -> date:
    """The latest completed session, per the rules above."""
    if not sessions:
        raise ConfigurationError("trading calendar is empty — run `mip calendar build`")
    if as_of is not None:
        eligible = [s for s in sessions if s <= as_of]
        if not eligible:
            raise ConfigurationError(f"no trading session on or before {as_of.isoformat()}")
        return eligible[-1]

    today = now.astimezone(EASTERN).date()
    cutoff = datetime.combine(today, MARKET_CLOSE, tzinfo=EASTERN) + timedelta(
        minutes=close_buffer_minutes
    )
    effective = today
    if today in set(sessions) and now.astimezone(EASTERN) < cutoff:
        effective = today - timedelta(days=1)  # today's session is not complete yet
    eligible = [s for s in sessions if s <= effective]
    if not eligible:
        raise ConfigurationError(f"no completed trading session on or before {effective}")
    return eligible[-1]
