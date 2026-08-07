"""V4 product vertical slice: one holding, five horizons, one report.

Reuses the existing price and feature stores. Adds no model. Emits no
probability and no predictive score. Every figure is either a fact read
from the repository, a deterministic calculation over those facts, or an
explicitly-labelled EXPERIMENTAL directional reading.
"""

from __future__ import annotations

import csv
import statistics
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import text

from mip.product.contracts import (
    HORIZONS,
    Constraint,
    ConstraintStatus,
    Direction,
    Evidence,
    PositionState,
    Status,
)

ALL_H = tuple(h for h, _ in HORIZONS)


# ---------------------------------------------------------------- position
def load_position(session, symbol: str, as_of: date, balances_csv: Path) -> PositionState:
    """PositionState from the user's own broker balances plus the price store."""
    rows = list(csv.DictReader(balances_csv.open()))
    if not rows:
        raise ValueError(f"no rows in {balances_csv}")
    mine = [r for r in rows if r["symbol"].strip().upper() == symbol.upper()]
    if not mine:
        raise ValueError(f"{symbol} not present in {balances_csv.name}")
    r = mine[0]
    qty = Decimal(r["quantity"])
    avg = Decimal(r["average_cost"])
    cost = (qty * avg).quantize(Decimal("0.01"))

    total_cost = sum(Decimal(x["quantity"]) * Decimal(x["average_cost"]) for x in rows)
    cost_weight = (cost / total_cost).quantize(Decimal("0.000001")) if total_cost else None

    px = session.execute(
        text(
            "select p.close, p.price_date from daily_prices p join instruments i "
            "on i.id=p.instrument_id where i.symbol=:s and p.price_date<=:d "
            "order by p.price_date desc limit 1"
        ),
        {"s": symbol, "d": as_of},
    ).first()

    unavailable: list[str] = []
    if px is None:
        unavailable.append("market price (no daily_prices row at or before as_of)")
        mp = pd_ = mv = pnl = pct = None
    else:
        mp = Decimal(str(px[0])).quantize(Decimal("0.01"))
        pd_ = px[1]
        mv = (qty * mp).quantize(Decimal("0.01"))
        pnl = (mv - cost).quantize(Decimal("0.01"))
        pct = (pnl / cost).quantize(Decimal("0.0001")) if cost else None

    priced = session.execute(
        text(
            "select count(distinct i.symbol) from daily_prices p join instruments i "
            "on i.id=p.instrument_id where i.symbol = any(:syms)"
        ),
        {"syms": [x["symbol"].strip().upper() for x in rows]},
    ).scalar_one()
    if priced < len(rows):
        unavailable.append(
            f"market-value portfolio weight ({priced} of {len(rows)} positions have prices "
            "in the repository; total portfolio market value is not computable)"
        )
    unavailable.append("tax lots and acquisition dates (broker export records average cost only)")

    return PositionState(
        symbol=symbol,
        as_of=as_of,
        quantity=qty,
        average_cost=avg,
        market_price=mp,
        price_date=pd_,
        market_value=mv,
        cost_basis=cost,
        unrealized_pnl=pnl,
        unrealized_pct=pct,
        cost_weight=cost_weight,
        portfolio_positions=len(rows),
        unavailable=tuple(unavailable),
    )


# ---------------------------------------------------------------- helpers
def _feat(session, symbol: str, name: str, as_of: date):
    return session.execute(
        text(
            "select f.value, f.feature_date from feature_store_daily f "
            "join feature_definitions d on d.id=f.feature_id "
            "join instruments i on i.id=f.instrument_id "
            "where i.symbol=:s and d.name=:n and f.feature_date<=:d and f.value is not null "
            "order by f.feature_date desc limit 1"
        ),
        {"s": symbol, "n": name, "d": as_of},
    ).first()


def _market_feat(session, name: str, as_of: date):
    return session.execute(
        text(
            "select f.value, f.feature_date from feature_store_market_daily f "
            "join feature_definitions d on d.id=f.feature_id "
            "where d.name=:n and f.feature_date<=:d "
            "and f.value is not null order by f.feature_date desc limit 1"
        ),
        {"n": name, "d": as_of},
    ).first()


def _pctile(session, symbol: str, name: str, as_of: date, value: float) -> float | None:
    hist = (
        session.execute(
            text(
                "select f.value from feature_store_daily f "
                "join feature_definitions d on d.id=f.feature_id "
                "join instruments i on i.id=f.instrument_id "
                "where i.symbol=:s and d.name=:n and f.feature_date<=:d and f.value is not null"
            ),
            {"s": symbol, "n": name, "d": as_of},
        )
        .scalars()
        .all()
    )
    if len(hist) < 252:
        return None
    return sum(1 for h in hist if float(h) <= value) / len(hist)


# ---------------------------------------------------------------- evidence
def gather_evidence(session, symbol: str, as_of: date) -> list[Evidence]:
    ev: list[Evidence] = []

    # -- price / technical (DESCRIPTIVE facts; direction is EXPERIMENTAL reading)
    tech = [
        ("ret_21d", "21-session total return", ("1w", "1m")),
        ("ret_63d", "63-session total return", ("1m", "3m")),
        ("ret_126d", "126-session total return", ("3m", "6m")),
        ("ret_252d", "252-session total return", ("6m", "1y")),
        ("vol_21d", "21-session annualised volatility", ALL_H),
        ("dist_52w_high", "distance below the 52-week high", ALL_H),
        ("price_to_ma50", "price relative to the 50-session average", ("1w", "1m")),
        ("price_to_ma200", "price relative to the 200-session average", ("3m", "6m", "1y")),
        ("rel_ret_spy_63d", "63-session return relative to SPY", ("1m", "3m")),
    ]
    for name, desc, hz in tech:
        row = _feat(session, symbol, name, as_of)
        if row is None:
            ev.append(
                Evidence(
                    name,
                    "price/technical",
                    Status.UNAVAILABLE,
                    "—",
                    "feature_store_daily",
                    None,
                    hz,
                    desc,
                    "not computed for this symbol at this date",
                    missing_reason="no non-null feature value at or before as_of",
                )
            )
            continue
        val, fdate = float(row[0]), row[1]
        pc = _pctile(session, symbol, name, as_of, val)
        direction = Direction.NEUTRAL
        if name.startswith(("ret_", "rel_ret_", "price_to_")) and pc is not None:
            direction = (
                Direction.POSITIVE
                if pc >= 0.70
                else Direction.NEGATIVE if pc <= 0.30 else Direction.NEUTRAL
            )
        pctxt = f"; {pc:.0%} of its own history" if pc is not None else "; percentile unavailable"
        ev.append(
            Evidence(
                name,
                "price/technical",
                Status.DESCRIPTIVE,
                f"{val:+.4f}",
                "feature_store_daily",
                fdate,
                hz,
                f"{desc}{pctxt}",
                "A measured price fact. Its directional reading is EXPERIMENTAL: no "
                "predictive reliability has been established for this feature.",
                direction=direction,
            )
        )

    # -- market / regime
    for name, desc in (
        ("regime_bull", "market in a bull regime (SPY above its 200-session average)"),
        ("vix_pctile_252d", "VIX percentile over the trailing year"),
        ("sector_breadth_ma50", "share of sector ETFs above their 50-session average"),
    ):
        row = _market_feat(session, name, as_of)
        if row is None:
            ev.append(
                Evidence(
                    name,
                    "market/regime",
                    Status.UNAVAILABLE,
                    "—",
                    "feature_store_daily",
                    None,
                    ALL_H,
                    desc,
                    "market-scope feature not populated",
                    missing_reason="no market-scope value at or before as_of",
                )
            )
        else:
            ev.append(
                Evidence(
                    name,
                    "market/regime",
                    Status.DESCRIPTIVE,
                    f"{float(row[0]):+.4f}",
                    "feature_store_daily",
                    row[1],
                    ALL_H,
                    desc,
                    "Market state fact. Applies to every holding, not specific to this one.",
                )
            )

    # -- fundamentals / earnings / valuation / catalysts
    for dom, nm, why in (
        (
            "fundamentals",
            "fundamental_snapshot",
            "no point-in-time fundamentals are stored; the fundamentals-driven models emit "
            "constant output",
        ),
        ("earnings", "next_earnings_date", "earnings_events table is not present in this database"),
        ("valuation", "valuation_multiples", "requires point-in-time fundamentals (unavailable)"),
        (
            "catalysts",
            "dated_catalysts",
            "no PIT-verified catalyst source is wired into this slice",
        ),
    ):
        ev.append(
            Evidence(
                nm,
                dom,
                Status.UNAVAILABLE,
                "—",
                "—",
                None,
                ALL_H,
                f"{dom} evidence for {symbol}",
                "Section renders as UNAVAILABLE.",
                missing_reason=why,
            )
        )

    # -- historical forward-return distribution, own history, strictly PIT
    ev.extend(_historical(session, symbol, as_of))
    return ev


def _historical(session, symbol: str, as_of: date) -> list[Evidence]:
    """Forward-return distribution from this symbol's own completed history."""
    closes = session.execute(
        text(
            "select p.price_date, p.adj_close from daily_prices p join instruments i "
            "on i.id=p.instrument_id where i.symbol=:s and p.price_date<=:d "
            "order by p.price_date"
        ),
        {"s": symbol, "d": as_of},
    ).all()
    out: list[Evidence] = []
    if len(closes) < 600:
        for h, _ in HORIZONS:
            out.append(
                Evidence(
                    f"forward_return_{h}",
                    "historical",
                    Status.UNAVAILABLE,
                    "—",
                    "daily_prices",
                    None,
                    (h,),
                    "forward-return distribution",
                    "insufficient history",
                    missing_reason="fewer than 600 sessions",
                )
            )
        return out

    px = [float(c[1]) for c in closes]
    for h, n in HORIZONS:
        fwd = [(px[i + n] / px[i]) - 1.0 for i in range(len(px) - n)]
        if len(fwd) < 100:
            out.append(
                Evidence(
                    f"forward_return_{h}",
                    "historical",
                    Status.UNAVAILABLE,
                    "—",
                    "daily_prices",
                    None,
                    (h,),
                    "forward-return distribution",
                    "too few completed windows",
                    missing_reason=f"only {len(fwd)} completed {h} windows",
                )
            )
            continue
        fwd.sort()
        med = statistics.median(fwd)
        p10 = fwd[int(0.10 * len(fwd))]
        p90 = fwd[int(0.90 * len(fwd))]
        hit = sum(1 for f in fwd if f > 0) / len(fwd)
        out.append(
            Evidence(
                f"forward_return_{h}",
                "historical",
                Status.DESCRIPTIVE,
                f"median {med:+.2%}, p10 {p10:+.2%}, p90 {p90:+.2%}, positive {hit:.0%}, "
                "n={len(fwd)}",
                "daily_prices",
                closes[-1][0],
                (h,),
                f"Unconditional distribution of {symbol}'s own completed {h} forward returns, "
                f"using only sessions at or before {as_of.isoformat()}.",
                "Point-in-time: yes (no window extends past as_of). Survivorship: this symbol "
                "survived the whole sample, so the distribution is conditioned on survival. "
                "Universe selection: this symbol is in the sample because it is a current "
                "holding. Overlapping windows: yes, so n overstates independent observations. "
                "DESCRIPTIVE ONLY - this is history, not a forecast.",
            )
        )
    return out


# ---------------------------------------------------------------- constraints
def evaluate_constraints(pos: PositionState) -> list[Constraint]:
    cs: list[Constraint] = []
    cw = f"{pos.cost_weight:.2%}" if pos.cost_weight is not None else "unavailable"
    cs.append(
        Constraint(
            "Concentration (cost-basis weight)",
            ConstraintStatus.NOT_EVALUABLE,
            cw,
            "unavailable",
            "No PolicyArtifact exists. Position limits live only in the policy layer "
            "(module M7, phase P3) which is not yet implemented, so no threshold can be "
            "applied. The observed weight is reported as a fact.",
        )
    )
    cs.append(
        Constraint(
            "Concentration (market-value weight)",
            ConstraintStatus.NOT_EVALUABLE,
            "unavailable",
            "unavailable",
            "Total portfolio market value is not computable: most positions have no price "
            "in the repository.",
        )
    )
    cs.append(
        Constraint(
            "Liquidity (days to liquidate)",
            ConstraintStatus.NOT_EVALUABLE,
            "unavailable",
            "unavailable",
            "Average daily volume is not wired into this slice.",
        )
    )
    cs.append(
        Constraint(
            "Tax impact of a sale",
            ConstraintStatus.NOT_EVALUABLE,
            "unavailable",
            "unavailable",
            "Tax lots and acquisition dates are unavailable; the broker export records "
            "average cost only. Realised gain or loss on a partial sale cannot be computed.",
        )
    )
    return cs
