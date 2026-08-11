"""Company quality: how the business compares with economically similar peers.

This describes the BUSINESS, not the security. A good company is not the same
thing as a stock that will rise, and the two are kept apart here: the quality
state is built first, without reference to price or expected return, and only
then is a directional reading attached under an explicitly stated hypothesis.

Reference population is SECTOR PEERS ONLY. Margins are not comparable across
sectors - in this population the median Consumer Staples margin is -1.0% while
Materials is +19.0% - so there is no cross-sectional fallback. Where a sector
carries too few peers the state is UNAVAILABLE rather than approximated.

Only profitability and leverage inform the state. Beta, market cap and revenue
are reported as context but do not enter it: beta measures sensitivity to the
market, and size and scale are not quality.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import text

MIN_PEERS = 5  # excluding the company itself; matches the valuation module

# Bands on the composite peer percentile, matching the valuation module.
BANDS = (
    (Decimal("0.20"), "WEAK"),
    (Decimal("0.40"), "BELOW_PEER"),
    (Decimal("0.60"), "TYPICAL"),
    (Decimal("0.80"), "ABOVE_PEER"),
    (Decimal("1.01"), "STRONG"),
)

# (field, label, higher_is_better)
METRICS = (
    ("profit_margin", "profit margin", True),
    ("debt_to_equity", "debt/equity", False),
)

_SQL = """
select i.symbol,
       coalesce(s1.name, s2.name) as sector,
       f.profit_margin, f.debt_to_equity, f.beta, f.market_cap, f.revenue_ttm, f.as_of_date
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
class QualityAssessment:
    state: str  # STRONG | ABOVE_PEER | TYPICAL | BELOW_PEER | WEAK | UNAVAILABLE
    sector: str | None
    peer_count: int
    composite_percentile: Decimal | None
    components: tuple[tuple[str, Decimal, Decimal, int], ...]  # metric, raw, pctile, n
    context: tuple[tuple[str, str], ...]  # non-voting descriptors
    as_of: date | None
    reason: str


def _usable(row: dict) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    m = row.get("profit_margin")
    if m is not None:
        out["profit_margin"] = Decimal(str(m))
    de = row.get("debt_to_equity")
    # Negative debt/equity means negative book equity; the ratio is then not a
    # leverage measure at all and is dropped rather than ranked.
    if de is not None and Decimal(str(de)) >= 0:
        out["debt_to_equity"] = Decimal(str(de))
    return out


def assess(session, symbol: str, as_of: date) -> QualityAssessment:
    rows = session.execute(text(_SQL), {"d": as_of}).mappings().all()
    by = {r["symbol"]: dict(r) for r in rows}
    me = by.get(symbol)
    if me is None:
        return QualityAssessment(
            "UNAVAILABLE",
            None,
            0,
            None,
            (),
            (),
            None,
            f"no fundamentals row for {symbol} at or before as_of",
        )
    ctx: list[tuple[str, str]] = []
    if me.get("beta") is not None:
        ctx.append(("beta", f"{float(me['beta']):.2f}"))
    if me.get("market_cap") is not None:
        ctx.append(("market cap", f"${float(me['market_cap']) / 1e9:,.1f}B"))
    if me.get("revenue_ttm") is not None:
        ctx.append(("revenue TTM", f"${float(me['revenue_ttm']) / 1e9:,.1f}B"))

    sector = me.get("sector")
    if sector is None:
        return QualityAssessment(
            "UNAVAILABLE",
            None,
            0,
            None,
            (),
            tuple(ctx),
            me["as_of_date"],
            "the instrument carries no sector classification, and quality metrics "
            "are not comparable across sectors",
        )
    peers = [r for sym, r in by.items() if sym != symbol and r.get("sector") == sector]
    if len(peers) < MIN_PEERS:
        return QualityAssessment(
            "UNAVAILABLE",
            sector,
            len(peers),
            None,
            (),
            tuple(ctx),
            me["as_of_date"],
            f"sector '{sector}' carries only {len(peers)} peers with fundamentals; "
            f"{MIN_PEERS} required. Margins and leverage are not comparable across "
            f"sectors, so no cross-sectional fallback is applied.",
        )

    mine = _usable(me)
    components: list[tuple[str, Decimal, Decimal, int]] = []
    for field, _label, higher_better in METRICS:
        if field not in mine:
            continue
        vals = [v[field] for v in (_usable(p) for p in peers) if field in v]
        if len(vals) < MIN_PEERS:
            continue
        below = sum(1 for v in vals if v < mine[field])
        equal = sum(1 for v in vals if v == mine[field])
        pct = (Decimal(below) + Decimal(equal) / 2) / Decimal(len(vals))
        if not higher_better:
            pct = Decimal(1) - pct
        components.append((field, mine[field], pct, len(vals)))

    if not components:
        return QualityAssessment(
            "UNAVAILABLE",
            sector,
            len(peers),
            None,
            (),
            tuple(ctx),
            me["as_of_date"],
            "no quality metric had enough peers carrying the same metric to rank against",
        )
    composite = sum(c[2] for c in components) / Decimal(len(components))
    state = next(label for edge, label in BANDS if composite < edge)
    return QualityAssessment(
        state,
        sector,
        len(peers),
        composite,
        tuple(components),
        tuple(ctx),
        me["as_of_date"],
        f"composite of {len(components)} metric percentile(s) within {len(peers)} "
        f"{sector} peers",
    )
