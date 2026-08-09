"""Event risk: proximity and historical dispersion. Never direction.

A scheduled earnings report is not bullish or bearish. It is a date on which
uncertainty resolves. This module answers two questions and refuses the third:

  - does the event fall inside this horizon, and how close is it?
  - how large have this company's moves around past reports been?
  - which way will it go?  -- NOT ANSWERED, and not inferable from the above.

Consequently every item produced here carries Direction.NEUTRAL. Event risk
reaches the recommendation through the ACTION stage as a guardrail, never
through the directional view.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date

from sqlalchemy import text

# Calendar days spanned by each horizon. Deterministic and declared: an event
# outside the window cannot be "within" that horizon.
HORIZON_DAYS = {"1w": 7, "1m": 31, "3m": 92, "6m": 183, "1y": 365}

# Proximity cutoffs, in calendar days. Heuristic, declared, not fitted to
# recommendations: one week is the trading week containing the event; three
# weeks is roughly the period over which positioning into a print is decided.
IMMINENT_DAYS = 7
APPROACHING_DAYS = 21

MIN_EVENTS_FOR_MAGNITUDE = 6


@dataclass(frozen=True, slots=True)
class EventState:
    status: str  # UNAVAILABLE | NO_KNOWN_EVENT | OUTSIDE_HORIZON | WITHIN_HORIZON
    #                          | APPROACHING | IMMINENT
    event_date: date | None
    days_to_event: int | None
    confirmed: bool
    horizon: str
    reason: str


@dataclass(frozen=True, slots=True)
class EventMagnitude:
    """Historical absolute move around past reports. Dispersion, not direction."""

    n_events: int
    median_abs_move: float | None
    p90_abs_move: float | None
    worst_down: float | None
    best_up: float | None
    reason: str


def next_event(session, symbol: str, as_of: date) -> tuple[date | None, bool, bool]:
    """(date, confirmed, any_history). Only events already OBSERVED at as_of."""
    row = session.execute(
        text(
            "select e.earnings_date, e.is_confirmed from earnings_observations e "
            "join instruments i on i.id=e.instrument_id where i.symbol=:s "
            "and e.observed_at::date <= :d and e.earnings_date >= :d "
            "order by e.earnings_date asc limit 1"
        ),
        {"s": symbol, "d": as_of},
    ).first()
    any_hist = (
        session.execute(
            text(
                "select 1 from earnings_observations e join instruments i on i.id=e.instrument_id "
                "where i.symbol=:s limit 1"
            ),
            {"s": symbol},
        ).first()
        is not None
    )
    if row is None:
        return None, False, any_hist
    return row[0], bool(row[1]), any_hist


def classify(event_date: date | None, as_of: date, horizon: str, any_history: bool) -> EventState:
    """Per-horizon. An event 83 days out is NOT inside a one-month horizon."""
    window = HORIZON_DAYS[horizon]
    if event_date is None:
        if not any_history:
            return EventState(
                "UNAVAILABLE",
                None,
                None,
                False,
                horizon,
                "no earnings observations exist for this security; absence of a known "
                "event is NOT evidence that no event will occur",
            )
        return EventState(
            "NO_KNOWN_EVENT",
            None,
            None,
            False,
            horizon,
            "earnings history exists but no future date has been observed at or before "
            "as_of; the next report is simply not yet scheduled or not yet ingested",
        )
    days = (event_date - as_of).days
    if days > window:
        return EventState(
            "OUTSIDE_HORIZON",
            event_date,
            days,
            False,
            horizon,
            f"the next report is {days} days away, beyond the {window}-day {horizon} window",
        )
    if days <= IMMINENT_DAYS:
        status = "IMMINENT"
    elif days <= APPROACHING_DAYS:
        status = "APPROACHING"
    else:
        status = "WITHIN_HORIZON"
    return EventState(
        status,
        event_date,
        days,
        False,
        horizon,
        f"the next report is {days} days away, inside the {window}-day {horizon} window",
    )


def magnitude(session, symbol: str, as_of: date) -> EventMagnitude:
    """Absolute close-to-close move on the session after each past report.

    Uses only reports dated before as_of. Characterises dispersion. It is not a
    forecast and carries no sign expectation.
    """
    events = (
        session.execute(
            text(
                "select e.earnings_date from earnings_observations e "
                "join instruments i on i.id=e.instrument_id where i.symbol=:s "
                "and e.earnings_date < :d and e.eps_actual is not null "
                "order by e.earnings_date desc limit 20"
            ),
            {"s": symbol, "d": as_of},
        )
        .scalars()
        .all()
    )
    if len(events) < MIN_EVENTS_FOR_MAGNITUDE:
        return EventMagnitude(
            len(events),
            None,
            None,
            None,
            None,
            f"only {len(events)} completed reports; {MIN_EVENTS_FOR_MAGNITUDE} required",
        )
    px = session.execute(
        text(
            "select p.price_date, p.adj_close from daily_prices p "
            "join instruments i on i.id=p.instrument_id where i.symbol=:s "
            "and p.price_date <= :d order by p.price_date"
        ),
        {"s": symbol, "d": as_of},
    ).all()
    if len(px) < 30:
        return EventMagnitude(len(events), None, None, None, None, "insufficient price history")
    dates = [r[0] for r in px]
    closes = [float(r[1]) for r in px]
    moves: list[float] = []
    for ev in events:
        after = [i for i, dt in enumerate(dates) if dt > ev]
        if not after or after[0] == 0:
            continue
        i = after[0]
        if closes[i - 1] > 0:
            moves.append((closes[i] / closes[i - 1]) - 1.0)
    if len(moves) < MIN_EVENTS_FOR_MAGNITUDE:
        return EventMagnitude(
            len(moves),
            None,
            None,
            None,
            None,
            f"only {len(moves)} reports had a usable adjacent session pair",
        )
    absm = sorted(abs(m) for m in moves)
    return EventMagnitude(
        len(moves),
        statistics.median(absm),
        absm[int(0.9 * len(absm)) - 1],
        min(moves),
        max(moves),
        f"first session after each of the last {len(moves)} completed reports",
    )
