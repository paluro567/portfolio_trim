"""V4 product vertical slice: one holding, five horizons, one report.

Reuses the existing price and feature stores. Adds no model. Emits no
probability and no predictive score. Every figure is either a fact read
from the repository, a deterministic calculation over those facts, or an
explicitly-labelled EXPERIMENTAL directional reading.
"""

from __future__ import annotations

import csv
import statistics
from dataclasses import replace
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
from mip.product.delivery import assess as assess_delivery
from mip.product.event import classify as classify_event
from mip.product.event import magnitude as event_magnitude
from mip.product.event import next_event
from mip.product.quality import assess as assess_quality
from mip.product.valuation import assess as assess_valuation

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

    # Market-value denominator: requires a price for EVERY holding. Cost-basis
    # weight is NOT a substitute - it answers a different question.
    total_mv = Decimal(0)
    unpriced: list[str] = []
    for row in rows:
        sym = row["symbol"].strip().upper()
        q = Decimal(row["quantity"])
        hit = session.execute(
            text(
                "select p.close from daily_prices p join instruments i on i.id=p.instrument_id "
                "where i.symbol=:s and p.price_date<=:d order by p.price_date desc limit 1"
            ),
            {"s": sym, "d": as_of},
        ).scalar()
        if hit is None:
            unpriced.append(sym)
            continue
        total_mv += q * Decimal(str(hit))
    if unpriced:
        market_weight = None
        portfolio_mv = None
        unavailable.append(
            f"market-value portfolio weight ({len(rows) - len(unpriced)} of {len(rows)} "
            f"positions priced at or before as_of; unpriced: {', '.join(sorted(unpriced))})"
        )
    else:
        portfolio_mv = total_mv.quantize(Decimal("0.01"))
        market_weight = (
            (mv / portfolio_mv).quantize(Decimal("0.000001"))
            if mv is not None and portfolio_mv
            else None
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
        market_weight=market_weight,
        portfolio_market_value=portfolio_mv,
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
        ("ret_21d", "21-session total return", ("1w", "1m"), "absolute_momentum"),
        ("ret_63d", "63-session total return", ("1m", "3m"), "absolute_momentum"),
        ("ret_126d", "126-session total return", ("3m", "6m"), "absolute_momentum"),
        ("ret_252d", "252-session total return", ("6m", "1y"), "absolute_momentum"),
        ("vol_21d", "21-session annualised volatility", ALL_H, "volatility"),
        ("dist_52w_high", "distance below the 52-week high", ALL_H, "trend_position"),
        (
            "price_to_ma50",
            "price relative to the 50-session average",
            ("1w", "1m"),
            "trend_position",
        ),
        (
            "price_to_ma200",
            "price relative to the 200-session average",
            ("3m", "6m", "1y"),
            "trend_position",
        ),
        ("rel_ret_spy_63d", "63-session return relative to SPY", ("1m", "3m"), "market_relative"),
    ]
    for name, desc, hz, grp in tech:
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
                    group=grp,
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
                "A measured price fact. The directional reading applies a MOMENTUM "
                "interpretation (recent strength read as positive). The opposite "
                "MEAN-REVERSION interpretation is equally defensible and would invert "
                "the sign. No predictive reliability has been established for either. "
                "EXPERIMENTAL.",
                direction=direction,
                group=grp,
                ambiguous=direction is not Direction.NEUTRAL,
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

    # -- sector relative behaviour
    for name, desc, hz in (
        ("rel_ret_sector_21d", "21-session return vs the sector ETF", ("1w", "1m")),
        ("rel_ret_sector_63d", "63-session return vs the sector ETF", ("1m", "3m")),
        ("rel_ret_sector_126d", "126-session return vs the sector ETF", ("3m", "6m")),
    ):
        row = _feat(session, symbol, name, as_of)
        if row is None:
            ev.append(
                Evidence(
                    name,
                    "sector",
                    Status.UNAVAILABLE,
                    "-",
                    "feature_store_daily",
                    None,
                    hz,
                    desc,
                    "sector-relative feature not computed",
                    missing_reason="no non-null value at or before as_of",
                )
            )
            continue
        val, fdate = float(row[0]), row[1]
        pc = _pctile(session, symbol, name, as_of, val)
        direction = Direction.NEUTRAL
        if pc is not None:
            direction = (
                Direction.POSITIVE
                if pc >= 0.70
                else Direction.NEGATIVE if pc <= 0.30 else Direction.NEUTRAL
            )
        pctxt = f"; {pc:.0%} of its own history" if pc is not None else ""
        ev.append(
            Evidence(
                name,
                "sector",
                Status.DESCRIPTIVE,
                f"{val:+.4f}",
                "feature_store_daily",
                fdate,
                hz,
                f"{desc}{pctxt}",
                "Measured relative-performance fact. Directional reading is " "EXPERIMENTAL.",
                direction=direction,
            )
        )

    # -- fundamentals and valuation (point-in-time snapshot)
    ev.extend(_fundamentals(session, symbol, as_of))

    # -- earnings and catalysts (dated events, PIT)
    ev.extend(_earnings(session, symbol, as_of))

    # -- valuation: ONE contextual voice, components exposed but not voting
    ev.append(_valuation_evidence(session, symbol, as_of))

    # -- historical forward-return distribution, own history, strictly PIT
    ev.extend(_historical(session, symbol, as_of))
    return _assign_groups(ev)


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
def evaluate_constraints(pos: PositionState, policy=None) -> list[Constraint]:
    """Deterministic constraints. Policy-dependent ones stay NOT_EVALUABLE
    until the portfolio owner supplies the value."""
    from mip.product.policy import PolicyArtifact

    cs: list[Constraint] = []
    has_policy = isinstance(policy, PolicyArtifact)
    mw = pos.market_weight
    mw_txt = f"{mw:.2%}" if mw is not None else "unavailable"

    # -- concentration vs hard cap (market value, never cost basis)
    if mw is None:
        cs.append(
            Constraint(
                "Concentration vs hard cap (market value)",
                ConstraintStatus.NOT_EVALUABLE,
                "unavailable",
                "unavailable",
                "Total portfolio market value is not computable: at least one holding has "
                "no price at or before as_of. Cost-basis weight is not a substitute.",
            )
        )
    elif not has_policy:
        miss = ", ".join(policy.missing) if policy is not None else "hard_cap_pct"
        cs.append(
            Constraint(
                "Concentration vs hard cap (market value)",
                ConstraintStatus.NOT_EVALUABLE,
                mw_txt,
                "unavailable",
                f"Market-value weight is known, but no hard cap has been supplied by the "
                f"portfolio owner. Required and unset: {miss}. The system does not invent "
                f"position limits.",
            )
        )
    else:
        cap = policy.hard_cap_pct / Decimal(100)
        breach = mw > cap
        headroom = (cap - mw) * Decimal(100)
        cs.append(
            Constraint(
                "Concentration vs hard cap (market value)",
                ConstraintStatus.BREACH if breach else ConstraintStatus.PASS,
                mw_txt,
                f"{policy.hard_cap_pct}%",
                (
                    f"Position is {abs(headroom):.2f} pp "
                    f"{'ABOVE the hard cap' if breach else 'below the hard cap'} "
                    f"(policy {policy.policy_version}, effective {policy.effective_date})."
                ),
            )
        )

    # -- deviation from target
    if mw is None or not has_policy:
        miss = ", ".join(policy.missing) if policy is not None and not has_policy else "-"
        cs.append(
            Constraint(
                "Deviation from core target (market value)",
                ConstraintStatus.NOT_EVALUABLE,
                mw_txt,
                "unavailable",
                (
                    "Market-value weight not computable."
                    if mw is None
                    else "No core target supplied by the portfolio owner. Required and unset: "
                    "{miss}."
                ),
            )
        )
    else:
        tgt = policy.core_target_pct / Decimal(100)
        dev = (mw - tgt) * Decimal(100)
        cs.append(
            Constraint(
                "Deviation from core target (market value)",
                ConstraintStatus.PASS,
                mw_txt,
                f"{policy.core_target_pct}%",
                f"{abs(dev):.2f} pp {'above' if dev > 0 else 'below'} target. "
                f"Deviation is reported, not enforced: no rebalance band has been supplied.",
            )
        )

    cs.append(
        Constraint(
            "Concentration (cost basis)",
            ConstraintStatus.NOT_EVALUABLE,
            f"{pos.cost_weight:.2%}" if pos.cost_weight is not None else "unavailable",
            "not applicable",
            "Cost-basis weight is reported as a fact only. It is NOT a concentration "
            "measure: concentration risk is a function of current market value.",
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


def _fundamentals(session, symbol: str, as_of: date) -> list[Evidence]:
    """Company fundamentals and valuation multiples from the PIT snapshot."""
    row = session.execute(
        text(
            "select f.as_of_date, f.trailing_pe, f.forward_pe, f.price_to_book, "
            "f.profit_margin, f.debt_to_equity, f.beta, f.market_cap, f.revenue_ttm "
            "from company_fundamentals f join instruments i on i.id=f.instrument_id "
            "where i.symbol=:s and f.as_of_date<=:d order by f.as_of_date desc limit 1"
        ),
        {"s": symbol, "d": as_of},
    ).first()
    if row is None:
        return [
            Evidence(
                n,
                dom,
                Status.UNAVAILABLE,
                "-",
                "company_fundamentals",
                None,
                ALL_H,
                d,
                "no snapshot at or before as_of",
                missing_reason="company_fundamentals holds no row at or before as_of",
            )
            for n, dom, d in (
                ("fundamental_snapshot", "fundamentals", "company fundamentals"),
                ("valuation_multiples", "valuation", "valuation multiples"),
            )
        ]
    fdate, tpe, fpe, pb, margin, de, beta, mcap, rev = row
    out: list[Evidence] = []

    def add(name, dom, val, expl, direction=Direction.NEUTRAL, grp="company_quality"):
        out.append(
            Evidence(
                name,
                dom,
                Status.DESCRIPTIVE,
                val,
                "company_fundamentals",
                fdate,
                ALL_H,
                expl,
                "Vendor snapshot. A single dated observation, not a time series, so "
                "no trend or historical percentile can be computed. Directional "
                "reading is EXPERIMENTAL.",
                direction=direction,
                group=grp,
            )
        )

    out.append(_quality_evidence(session, symbol, as_of))

    return out


def _earnings(session, symbol: str, as_of: date) -> list[Evidence]:
    """Dated earnings events. Strictly PIT: observed_at <= as_of."""
    ed, confirmed, any_hist = next_event(session, symbol, as_of)
    out: list[Evidence] = []

    # One item per horizon: an event 83 days out is OUTSIDE a 1-month window.
    for hz in ALL_H:
        st = classify_event(ed, as_of, hz, any_hist)
        if st.status == "UNAVAILABLE":
            out.append(
                Evidence(
                    f"event_state_{hz}",
                    "catalysts",
                    Status.UNAVAILABLE,
                    "-",
                    "earnings_observations",
                    None,
                    (hz,),
                    "scheduled-event state for this horizon",
                    st.reason,
                    missing_reason=st.reason,
                    group="event_risk",
                )
            )
            continue
        val = st.status
        if st.days_to_event is not None:
            val += f" ({st.days_to_event}d, {st.event_date.isoformat()})"
        out.append(
            Evidence(
                f"event_state_{hz}",
                "catalysts",
                Status.DESCRIPTIVE,
                val,
                "earnings_observations",
                st.event_date,
                (hz,),
                f"Scheduled-event state for the {hz} horizon: {st.reason}.",
                "A date is not a direction. This item states only whether an "
                "unresolved scheduled event falls inside the horizon and how close "
                "it is. It carries NO expectation of which way the result will go, "
                "and it never contributes to the directional view. It reaches the "
                "recommendation only as a position-management guardrail.",
                direction=Direction.NEUTRAL,
                group="event_risk",
            )
        )

    mag = event_magnitude(session, symbol, as_of)
    if mag.median_abs_move is None:
        out.append(
            Evidence(
                "event_move_magnitude",
                "catalysts",
                Status.UNAVAILABLE,
                "-",
                "earnings_observations + daily_prices",
                None,
                ALL_H,
                "historical size of moves around past reports",
                mag.reason,
                missing_reason=mag.reason,
                group="event_risk",
            )
        )
    else:
        out.append(
            Evidence(
                "event_move_magnitude",
                "catalysts",
                Status.DESCRIPTIVE,
                f"median |move| {mag.median_abs_move:.1%}, p90 {mag.p90_abs_move:.1%}, "
                f"worst {mag.worst_down:+.1%}, best {mag.best_up:+.1%}, n={mag.n_events}",
                "earnings_observations + daily_prices",
                as_of,
                ALL_H,
                f"Close-to-close move on the {mag.reason}.",
                "DISPERSION ONLY. This measures how large past reactions were, not "
                "which way the next one goes. The upside and downside extremes are "
                "shown together precisely so the figure cannot be read directionally. "
                "The schedule was observed in a single ingest, so these dates are "
                "usable for describing the present but would be lookahead-contaminated "
                "in a historical backtest. EXPERIMENTAL.",
                direction=Direction.NEUTRAL,
                group="event_risk",
            )
        )

    out.append(_delivery_evidence(session, symbol, as_of))
    return out


# Each domain maps to the PHENOMENON it measures, so that independence is never
# over-counted (several momentum windows are one phenomenon) and never
# under-counted (sector momentum, regime and earnings are not the same thing).
DOMAIN_GROUP = {
    "sector": "sector_relative",
    "market/regime": "market_regime",
    "catalysts": "event_risk",
    "earnings": "earnings_delivery",
    "historical": "own_history",
    "fundamentals": "company_quality",
    "valuation": "valuation_level",
}


def _assign_groups(ev: list[Evidence]) -> list[Evidence]:
    """Fill in any group left at the default from its domain."""
    out: list[Evidence] = []
    for e in ev:
        if e.group == "other" and e.domain in DOMAIN_GROUP:
            out.append(replace(e, group=DOMAIN_GROUP[e.domain]))
        else:
            out.append(e)
    return out


# Valuation is a level, not a timing signal. It is admitted only to the horizons
# over which a re-rating could plausibly play out. No weights are invented; the
# item simply does not appear at 1w/1m/3m.
VALUATION_HORIZONS = ("6m", "1y")


def _valuation_evidence(session, symbol: str, as_of: date) -> Evidence:
    a = assess_valuation(session, symbol, as_of)
    if a.status == "UNAVAILABLE":
        return Evidence(
            "valuation_position",
            "valuation",
            Status.UNAVAILABLE,
            "-",
            "company_fundamentals",
            a.as_of,
            VALUATION_HORIZONS,
            "contextual valuation position",
            a.reason,
            missing_reason=a.reason,
            group="valuation_level",
        )
    comps = "; ".join(
        f"{m} {float(v):.2f} -> {float(p):.0%} of {n} peers" for m, v, p, n in a.components
    )
    direction = (
        Direction.POSITIVE
        if a.status in ("CHEAP", "BELOW NORMAL")
        else Direction.NEGATIVE if a.status in ("EXPENSIVE", "ABOVE NORMAL") else Direction.NEUTRAL
    )
    return Evidence(
        "valuation_position",
        "valuation",
        Status.DESCRIPTIVE,
        f"{a.status} ({float(a.composite_percentile):.0%} of reference set)",
        "company_fundamentals",
        a.as_of,
        VALUATION_HORIZONS,
        f"Reference: {a.reference}; {a.peer_count} peers. Components: {comps}. "
        f"The composite is the mean of the component percentiles.",
        "The percentile is a rank within a peer set, NOT a probability. A demanding "
        "multiple is not a forecast of decline and a cheap one is not a forecast of "
        "gain: a high-quality or fast-growing business may rationally trade at a "
        "premium, and a deteriorating one may rationally trade cheaply. This item "
        "answers only 'how demanding is the price relative to comparable companies "
        "today'. The directional reading is EXPERIMENTAL. Single vendor snapshot: no "
        "valuation history exists, so the security cannot be compared with its own past.",
        direction=direction,
        group="valuation_level",
        ambiguous=True,
    )


# A quarterly delivery record summarises ~2 years of outcomes. Claiming it informs
# the next five sessions would require a link this repository cannot demonstrate,
# so 1w is deliberately excluded. No horizon weights are invented.
DELIVERY_HORIZONS = ("1m", "3m", "6m", "1y")

# Bands on the PEER PERCENTILE, matching the valuation module's treatment.
DELIVERY_TOP = 0.80
DELIVERY_BOTTOM = 0.20


def _delivery_evidence(session, symbol: str, as_of: date) -> Evidence:
    r = assess_delivery(session, symbol, as_of)
    if r.state == "UNAVAILABLE":
        return Evidence(
            "earnings_delivery_record",
            "earnings",
            Status.UNAVAILABLE,
            "-",
            "earnings_observations",
            r.last_report,
            DELIVERY_HORIZONS,
            "multi-report earnings delivery record",
            r.reason,
            missing_reason=r.reason,
            group="earnings_delivery",
        )
    # The vote uses the PEER PERCENTILE, not the raw state. Beating consensus is
    # the norm here - the median holding beats in 88% of quarters - so a
    # "consistent beater" is an ordinary company, not one exceeding expectations.
    if r.percentile is None:
        direction = Direction.NEUTRAL
        rank = "peer ranking unavailable (too few comparable records)"
    else:
        direction = (
            Direction.POSITIVE
            if r.percentile > DELIVERY_TOP
            else Direction.NEGATIVE if r.percentile < DELIVERY_BOTTOM else Direction.NEUTRAL
        )
        rank = (
            f"{r.percentile:.0%} of {r.peer_count} peers by beat rate "
            f"(this company beats {r.beat_rate:.0%} of the time)"
        )
    return Evidence(
        "earnings_delivery_record",
        "earnings",
        Status.DESCRIPTIVE,
        f"{r.state}, {rank}",
        "earnings_observations",
        r.last_report,
        DELIVERY_HORIZONS,
        f"Delivery against contemporaneous consensus: {r.reason}. Ranked against "
        f"every instrument carrying at least {6} completed reports. Magnitude is "
        f"reported in EPS dollars, not percent.",
        "Sign only. PERCENTAGE surprise is deliberately not used: it divides by the "
        "estimate, and these estimates are frequently near zero, so a $1.00 miss "
        "against a $0.02 estimate reads as -5000% - a denominator artifact. "
        "The directional vote measures the beat rate's position among peers, not "
        "the raw record, because beating is the norm and conformity to a norm is "
        "not evidence of anything. ECONOMIC HYPOTHESIS (stated, not demonstrated): "
        "firms whose delivery is unusual relative to peers may be systematically "
        "mis-anticipated by consensus. This describes EXECUTION, not expected "
        "return: whether unusual delivery precedes unusual returns has NOT been "
        "measured here, and the single-ingest earnings schedule makes a "
        "point-in-time test of that link impossible from this data. EXPERIMENTAL.",
        direction=direction,
        group="earnings_delivery",
        ambiguous=True,
    )


# Quality is the slowest-moving thing this engine measures: a single
# annual-frequency snapshot of profitability and leverage. The quality premium it
# leans on is a long-horizon phenomenon, so it votes at 1y only.
QUALITY_VOTING_HORIZONS = ("1y",)


def _quality_evidence(session, symbol: str, as_of: date) -> Evidence:
    a = assess_quality(session, symbol, as_of)
    ctx = "; ".join(f"{k} {v}" for k, v in a.context)
    if a.state == "UNAVAILABLE":
        return Evidence(
            "company_quality_position",
            "fundamentals",
            Status.UNAVAILABLE,
            "-",
            "company_fundamentals",
            a.as_of,
            QUALITY_VOTING_HORIZONS,
            (
                f"peer-relative business quality. Context: {ctx}"
                if ctx
                else "peer-relative business quality"
            ),
            a.reason,
            missing_reason=a.reason,
            group="company_quality",
        )
    comps = "; ".join(
        f"{m} {float(v):.2f} -> {float(p):.0%} of {n} peers" for m, v, p, n in a.components
    )
    direction = (
        Direction.POSITIVE
        if a.state in ("STRONG", "ABOVE_PEER")
        else Direction.NEGATIVE if a.state in ("WEAK", "BELOW_PEER") else Direction.NEUTRAL
    )
    return Evidence(
        "company_quality_position",
        "fundamentals",
        Status.DESCRIPTIVE,
        f"{a.state} ({float(a.composite_percentile):.0%} of {a.sector} peers)",
        "company_fundamentals",
        a.as_of,
        QUALITY_VOTING_HORIZONS,
        f"Business quality against {a.peer_count} {a.sector} peers. Components: "
        f"{comps}. Higher profitability and lower leverage rank better; the composite "
        f"is the mean of the component percentiles."
        + (f" Context (not part of the state): {ctx}." if ctx else ""),
        "A GOOD COMPANY IS NOT THE SAME THING AS A RISING STOCK. The state describes "
        "the business only. The directional reading rests on an economic hypothesis - "
        "that persistently profitable, lightly levered firms have historically earned "
        "better risk-adjusted returns over long holding periods - which has NOT been "
        "measured in this repository. Beta, market capitalisation and revenue are "
        "reported as context and deliberately excluded from the state: beta is market "
        "sensitivity, and size is not quality. Sector peers only, because margins are "
        "not comparable across sectors. Single vendor snapshot, so no trend can be "
        "computed. Votes at 1y only. EXPERIMENTAL.",
        direction=direction,
        group="company_quality",
        ambiguous=True,
    )
