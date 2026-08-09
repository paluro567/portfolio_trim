"""Contextual valuation: one phenomenon, one voice.

A P/E of 30 is neither cheap nor expensive on its own. This module places a
holding's multiples inside a reference population measured at the same date and
returns ONE composite position. The component metrics are exposed for tracing
but never vote independently.

Reference hierarchy (first that qualifies wins):
  1. own point-in-time valuation history  - NOT AVAILABLE: company_fundamentals
     holds a single snapshot date, so no historical distribution exists;
  2. sector peers at the same as-of date  - used when >= MIN_SECTOR_PEERS;
  3. whole cross-section at the same date - fallback, disclosed as weaker;
  4. otherwise UNAVAILABLE.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import text

MIN_SECTOR_PEERS = 5  # peers excluding the target
MIN_ANY_PEERS = 5

# Metric, human label, and whether a LOW value means a cheaper valuation.
# All four are "price paid per unit of something", so low = cheaper for each.
METRICS = (
    ("trailing_pe", "trailing P/E"),
    ("forward_pe", "forward P/E"),
    ("price_to_book", "price/book"),
    ("price_to_sales", "price/sales"),
)

BANDS = (
    (Decimal("0.20"), "CHEAP"),
    (Decimal("0.40"), "BELOW NORMAL"),
    (Decimal("0.60"), "NORMAL"),
    (Decimal("0.80"), "ABOVE NORMAL"),
    (Decimal("1.01"), "EXPENSIVE"),
)

_SQL = """
select i.symbol,
       coalesce(s1.name, s2.name) as sector,
       f.trailing_pe, f.forward_pe, f.price_to_book,
       f.market_cap, f.revenue_ttm, f.trailing_eps, f.forward_eps, f.as_of_date
from company_fundamentals f
join instruments i on i.id = f.instrument_id
left join industries ind on ind.id = i.industry_id
left join sectors s1 on s1.id = ind.sector_id
left join sectors s2 on s2.id = i.sector_id
where f.as_of_date <= :d
  and f.as_of_date = (
      select max(f2.as_of_date) from company_fundamentals f2
      where f2.instrument_id = f.instrument_id and f2.as_of_date <= :d
  )
"""


@dataclass(frozen=True, slots=True)
class ValuationAssessment:
    status: str  # CHEAP | BELOW NORMAL | NORMAL | ABOVE NORMAL | EXPENSIVE | UNAVAILABLE
    reference: str
    peer_count: int
    composite_percentile: Decimal | None
    components: tuple[tuple[str, Decimal, Decimal, int], ...]  # metric, raw, pctile, n
    raw_values: tuple[tuple[str, Decimal], ...]
    as_of: date | None
    reason: str


def _valid_metrics(row: dict) -> dict[str, Decimal]:
    """Only multiples that are economically meaningful for this company."""
    out: dict[str, Decimal] = {}
    teps, feps = row.get("trailing_eps"), row.get("forward_eps")
    tpe, fpe = row.get("trailing_pe"), row.get("forward_pe")
    pb = row.get("price_to_book")
    mcap, rev = row.get("market_cap"), row.get("revenue_ttm")

    # A P/E built on non-positive earnings is not a valuation level; it is noise.
    if tpe is not None and teps is not None and Decimal(str(teps)) > 0 and Decimal(str(tpe)) > 0:
        out["trailing_pe"] = Decimal(str(tpe))
    if fpe is not None and feps is not None and Decimal(str(feps)) > 0 and Decimal(str(fpe)) > 0:
        out["forward_pe"] = Decimal(str(fpe))
    # Negative book value makes price/book meaningless.
    if pb is not None and Decimal(str(pb)) > 0:
        out["price_to_book"] = Decimal(str(pb))
    if mcap is not None and rev is not None and Decimal(str(rev)) > 0:
        out["price_to_sales"] = Decimal(str(mcap)) / Decimal(str(rev))
    return out


def assess(session, symbol: str, as_of: date) -> ValuationAssessment:
    rows = session.execute(text(_SQL), {"d": as_of}).mappings().all()
    if not rows:
        return ValuationAssessment(
            "UNAVAILABLE",
            "none",
            0,
            None,
            (),
            (),
            None,
            "company_fundamentals holds no snapshot at or before as_of",
        )
    by_symbol = {r["symbol"]: dict(r) for r in rows}
    me = by_symbol.get(symbol)
    if me is None:
        return ValuationAssessment(
            "UNAVAILABLE",
            "none",
            0,
            None,
            (),
            (),
            None,
            f"no fundamentals row for {symbol} at or before as_of",
        )

    mine = _valid_metrics(me)
    if not mine:
        return ValuationAssessment(
            "UNAVAILABLE",
            "none",
            0,
            None,
            (),
            (),
            me["as_of_date"],
            "no economically valid multiple: earnings and book value are "
            "non-positive, and revenue is unavailable",
        )

    sector = me.get("sector")
    sector_peers = [
        r
        for sym, r in by_symbol.items()
        if sym != symbol and sector is not None and r.get("sector") == sector
    ]
    if len(sector_peers) >= MIN_SECTOR_PEERS:
        peers, reference = sector_peers, f"sector peers ({sector})"
    else:
        peers = [r for sym, r in by_symbol.items() if sym != symbol]
        reference = (
            f"whole cross-section (sector '{sector or 'unmapped'}' had only "
            f"{len(sector_peers)} peers, below the {MIN_SECTOR_PEERS} required)"
        )
    if len(peers) < MIN_ANY_PEERS:
        return ValuationAssessment(
            "UNAVAILABLE",
            reference,
            len(peers),
            None,
            (),
            tuple(mine.items()),
            me["as_of_date"],
            f"only {len(peers)} comparable peers; below the {MIN_ANY_PEERS} required",
        )

    components: list[tuple[str, Decimal, Decimal, int]] = []
    for metric, _label in METRICS:
        if metric not in mine:
            continue
        vals = [v[metric] for v in (_valid_metrics(p) for p in peers) if metric in v]
        if len(vals) < MIN_ANY_PEERS:
            continue
        below = sum(1 for v in vals if v < mine[metric])
        pct = Decimal(below) / Decimal(len(vals))
        components.append((metric, mine[metric], pct, len(vals)))

    if not components:
        return ValuationAssessment(
            "UNAVAILABLE",
            reference,
            len(peers),
            None,
            (),
            tuple(mine.items()),
            me["as_of_date"],
            "no metric had enough peers carrying the same metric to rank against",
        )

    composite = sum(c[2] for c in components) / Decimal(len(components))
    status = next(label for edge, label in BANDS if composite < edge)
    return ValuationAssessment(
        status,
        reference,
        len(peers),
        composite,
        tuple(components),
        tuple(mine.items()),
        me["as_of_date"],
        f"composite of {len(components)} metric percentile(s) within {reference}",
    )
