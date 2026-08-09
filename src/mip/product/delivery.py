"""Earnings delivery: how consistently a company has met contemporaneous estimates.

This is a DESCRIPTION OF EXECUTION, not a return forecast. Whether a company
that beats often subsequently outperforms has NOT been measured in this
repository and is not claimed here.

Representation: the beat/miss RECORD over the most recent completed reports.
Sign only. Percentage surprise is deliberately not used as a magnitude, because
it divides by the estimate and the estimates here are frequently near zero -
BBAI's -0.02 estimate against a -1.02 actual reads as -5000%, which is a
denominator artifact, not a 50x disappointment. The dollar miss is reported
alongside for scale, but it does not vote.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date

from sqlalchemy import text

WINDOW = 8  # most recent completed reports considered
MIN_REPORTS = 6  # below this, no state is claimed
MIN_PEERS = 20  # below this, no peer ranking is claimed

# Bands on the PEER PERCENTILE, matching the valuation module's treatment.
TOP_BAND = 0.80
BOTTOM_BAND = 0.20

# Declared, not fitted: a three-quarters record either way is treated as a
# consistent pattern; anything between is mixed.
STRONG_BEATS = 6  # of WINDOW
WEAK_BEATS = 2


@dataclass(frozen=True, slots=True)
class DeliveryRecord:
    """`state` describes the record. `percentile` places it among peers.

    The directional vote uses the PERCENTILE, not the state. Beating consensus is
    the norm - the median holding here beats in 88% of quarters - so "beats often"
    describes a company that is ordinary, not one that is outperforming
    expectations. The economic hypothesis behind the vote (analysts under-react to
    firms that surprise) concerns deviation from what is expected, so the vote must
    measure deviation from the peer norm rather than conformity to it.
    """

    state: str  # CONSISTENT_BEATS | MIXED | CONSISTENT_MISSES | UNAVAILABLE
    n_reports: int
    beats: int
    misses: int
    inline: int
    median_abs_dollar_surprise: float | None
    last_report: date | None
    reason: str
    beat_rate: float | None = None
    percentile: float | None = None
    peer_count: int = 0


def _beat_rate(rows) -> float | None:
    if len(rows) < MIN_REPORTS:
        return None
    beats = sum(1 for _dt, est, act in rows if float(act) > float(est))
    return beats / len(rows)


def population_beat_rates(session, as_of: date) -> dict[str, float]:
    """Beat rate for every instrument carrying enough completed reports."""
    rows = session.execute(
        text(
            "select i.symbol, e.earnings_date, e.eps_estimate, e.eps_actual "
            "from earnings_observations e join instruments i on i.id=e.instrument_id "
            "where e.observed_at::date <= :d and e.earnings_date < :d "
            "and e.eps_actual is not null and e.eps_estimate is not null "
            "order by i.symbol, e.earnings_date desc"
        ),
        {"d": as_of},
    ).all()
    by: dict[str, list] = {}
    for sym, dt, est, act in rows:
        by.setdefault(sym, []).append((dt, est, act))
    out = {}
    for sym, rs in by.items():
        r = _beat_rate(rs[:WINDOW])
        if r is not None:
            out[sym] = r
    return out


def assess(session, symbol: str, as_of: date) -> DeliveryRecord:
    rows = session.execute(
        text(
            "select e.earnings_date, e.eps_estimate, e.eps_actual "
            "from earnings_observations e join instruments i on i.id=e.instrument_id "
            "where i.symbol=:s and e.observed_at::date <= :d and e.earnings_date < :d "
            "and e.eps_actual is not null and e.eps_estimate is not null "
            "order by e.earnings_date desc limit :w"
        ),
        {"s": symbol, "d": as_of, "w": WINDOW},
    ).all()
    if len(rows) < MIN_REPORTS:
        return DeliveryRecord(
            "UNAVAILABLE",
            len(rows),
            0,
            0,
            0,
            None,
            rows[0][0] if rows else None,
            f"only {len(rows)} completed reports carry both an estimate and an actual; "
            f"{MIN_REPORTS} required. Absence of a record is NOT a neutral record.",
        )

    beats = misses = inline = 0
    dollar: list[float] = []
    for _dt, est, act in rows:
        diff = float(act) - float(est)
        dollar.append(abs(diff))
        if diff > 0:
            beats += 1
        elif diff < 0:
            misses += 1
        else:
            inline += 1

    if beats >= STRONG_BEATS:
        state = "CONSISTENT_BEATS"
    elif beats <= WEAK_BEATS:
        state = "CONSISTENT_MISSES"
    else:
        state = "MIXED"

    rate = beats / len(rows)
    pop = population_beat_rates(session, as_of)
    peers = [v for k, v in pop.items() if k != symbol]
    pct = None
    if len(peers) >= MIN_PEERS:
        # Midrank percentile: ties share a rank, so a block of perfect records is
        # not pushed out of the top band merely by how many share it.
        below = sum(1 for v in peers if v < rate)
        equal = sum(1 for v in peers if v == rate)
        pct = (below + equal / 2) / len(peers)
    return DeliveryRecord(
        state,
        len(rows),
        beats,
        misses,
        inline,
        statistics.median(dollar),
        rows[0][0],
        f"{beats} beats / {misses} misses / {inline} in line over the last "
        f"{len(rows)} completed reports",
        beat_rate=rate,
        percentile=pct,
        peer_count=len(peers),
    )
