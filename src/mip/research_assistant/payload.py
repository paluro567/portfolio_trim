"""The deterministic per-holding context payload.

Everything here is assembled by Python from objects the product layer already
produced. The model receives these values as GIVEN FACTS. It is told, in the
prompt and by the shape of the schema, that it may interpret them but may never
recompute, restate differently, or contradict them.

The payload is also the cache key: ``content_hash`` covers every deterministic
input, so research is re-run exactly when the quantitative picture changes.

This module imports from ``mip.product`` and never the other way round.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from mip.product.contracts import (
    Constraint,
    Evidence,
    HorizonVerdict,
    PositionState,
    Status,
)
from mip.product.decide import ADD_DISCOURAGE_MULTIPLE, portfolio_adjustment

# Mirrors the format string in `mip.product.slice.gather_evidence`, which appends
# "; 23% of its own history" to a technical item's explanation. Parsed back out
# here so the model receives a clean number instead of prose it might misread.
_PCTILE_RE = re.compile(r";\s*(\d+)%\s+of its own history")

# Instrument-scope technical features the payload surfaces individually.
_PRICE_FEATURES = (
    "ret_21d",
    "ret_63d",
    "ret_126d",
    "ret_252d",
    "vol_21d",
    "dist_52w_high",
    "price_to_ma50",
    "price_to_ma200",
    "rel_ret_spy_63d",
    "rel_ret_sector_21d",
    "rel_ret_sector_63d",
    "rel_ret_sector_126d",
)

_MARKET_FEATURES = ("regime_bull", "vix_pctile_252d", "sector_breadth_ma50")

# Market-scope features that exist in the store but never reached the
# deterministic report. Surfaced here because macro context genuinely helps a
# qualitative reading, and because they are already PIT publication-lagged.
_MACRO_FEATURES = (
    "vix_level",
    "dgs10_chg_21d",
    "dgs2_chg_21d",
    "curve_slope_10y2y",
    "cpi_yoy",
    "cpi_yoy_accel",
    "fedfunds_level",
    "regime_high_vol",
)

_BENCHMARKS = ("SPY", "QQQ", "IWM")
_BENCHMARK_FEATURES = ("ret_21d", "ret_63d", "ret_252d")


def _num(value: Decimal | float | None) -> str | None:
    """Numbers travel as strings so no float rounding can alter them in transit."""
    return None if value is None else str(value)


def _pctile_of(item: Evidence | None) -> int | None:
    if item is None:
        return None
    hit = _PCTILE_RE.search(item.explanation or "")
    return int(hit.group(1)) if hit else None


def _by_name(evidence: list[Evidence]) -> dict[str, Evidence]:
    return {e.name: e for e in evidence}


def _item(e: Evidence | None) -> dict[str, Any] | None:
    if e is None:
        return None
    return {
        "as_of": e.as_of.isoformat() if e.as_of else None,
        "available": e.status is not Status.UNAVAILABLE,
        "direction": e.direction.value,
        "group": e.group,
        "limitations": e.limitations,
        "missing_reason": e.missing_reason,
        "own_history_percentile": _pctile_of(e),
        "reading": e.explanation,
        "status": e.status.value,
        "value": e.value,
    }


# ------------------------------------------------------------------ the payload
@dataclass(frozen=True, slots=True)
class HoldingPayload:
    """Deterministic facts for one holding at one as-of date."""

    symbol: str
    as_of: date
    body: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return self.body

    def content_hash(self) -> str:
        """Stable hash over every deterministic input. Drives cache invalidation."""
        canonical = json.dumps(self.body, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def as_prompt_json(self) -> str:
        return json.dumps(self.body, indent=2, sort_keys=True)


def build_payload(
    pos: PositionState,
    evidence: list[Evidence],
    constraints: list[Constraint],
    verdicts: list[HorizonVerdict],
    *,
    policy: Any = None,
    company_name: str | None = None,
    sector: str | None = None,
    industry: str | None = None,
    market_context: dict[str, Any] | None = None,
    unsupported_positions_note: str | None = None,
) -> HoldingPayload:
    """Assemble the payload. Pure: no I/O, no database, fully unit-testable."""
    named = _by_name(evidence)

    equal_weight_multiple: str | None = None
    if pos.market_weight is not None and pos.portfolio_positions:
        equal = Decimal(1) / Decimal(pos.portfolio_positions)
        equal_weight_multiple = str((pos.market_weight / equal).quantize(Decimal("0.01")))

    sizing_effect, sizing_text = portfolio_adjustment(pos, constraints)

    price_state = {name: _item(named.get(name)) for name in _PRICE_FEATURES}
    market_state = {name: _item(named.get(name)) for name in _MARKET_FEATURES}

    historical = {
        h: _item(named.get(f"forward_return_{h}")) for h in ("1w", "1m", "3m", "6m", "1y")
    }

    earnings = {
        "event_state_by_horizon": {
            h: _item(named.get(f"event_state_{h}")) for h in ("1w", "1m", "3m", "6m", "1y")
        },
        "historical_move_dispersion": _item(named.get("event_move_magnitude")),
        "delivery_record": _item(named.get("earnings_delivery_record")),
    }

    fundamentals = {
        "valuation": _item(named.get("valuation_position")),
        "quality": _item(named.get("company_quality_position")),
        "snapshot_limitation": (
            "company_fundamentals holds one dated snapshot per instrument per day and "
            "began accumulating only recently. There is NO fundamentals history and no "
            "vintages, so no own-valuation percentile or trend exists. Peer percentiles "
            "are same-date cross-sectional ranks only."
        ),
    }

    verdict_rows = [
        {
            "action": v.action.value,
            "confidence": v.confidence.value,
            "confidence_basis": list(v.confidence_basis),
            "conflicts": list(v.conflicts),
            "contributing_groups": list(v.contributing),
            "elimination_trace": [list(e) for e in v.eliminations],
            "horizon": v.horizon,
            "rationale": v.rationale,
            "security_view": v.direction.value,
        }
        for v in verdicts
    ]

    policy_block: dict[str, Any]
    if policy is None:
        policy_block = {"status": "UNKNOWN", "detail": "policy not supplied to the payload"}
    else:
        policy_block = policy.to_dict()

    caveats = {
        "data_freshness": {
            "as_of": pos.as_of.isoformat(),
            "latest_price_date": pos.price_date.isoformat() if pos.price_date else None,
            "price_age_calendar_days": (
                (pos.as_of - pos.price_date).days if pos.price_date else None
            ),
        },
        "evidence_limitations": sorted(
            {
                e.limitations
                for e in evidence
                if e.limitations and e.status is not Status.UNAVAILABLE
            }
        ),
        "non_pit_limitations": [
            "Sector/industry classification is the CURRENT classification applied "
            "retroactively; it is not point-in-time.",
            "The earnings schedule was captured in a single ingest, so it describes "
            "the present correctly but is lookahead-contaminated historically.",
            "Fundamentals are current-value snapshots, not point-in-time vintages.",
        ],
        "survivorship_limitation": (
            "Own-history distributions are conditioned on this security having survived "
            "the whole sample, and it is in the sample because it is a current holding. "
            "No delisted security exists anywhere in this platform's data."
        ),
        "position_unavailable_inputs": list(pos.unavailable),
        "unsupported_positions": unsupported_positions_note,
        "validation_status": (
            "NO directional signal in this platform has established predictive "
            "reliability. Deterministic actions are declared heuristics over percentile "
            "thresholds, not validated forecasts."
        ),
    }

    body: dict[str, Any] = {
        "identity": {
            "as_of": pos.as_of.isoformat(),
            "company_name": company_name,
            "industry": industry,
            "sector": sector,
            "sector_classification_caveat": (
                "current classification, applied retroactively; not point-in-time"
            ),
            "symbol": pos.symbol,
        },
        "position": {
            "average_cost": _num(pos.average_cost),
            "cost_basis": _num(pos.cost_basis),
            "cost_weight": _num(pos.cost_weight),
            "current_price": _num(pos.market_price),
            "equal_weight_multiple": equal_weight_multiple,
            "equal_weight_reference_note": (
                f"Equal weight across the holdings present. A multiple at or above "
                f"{ADD_DISCOURAGE_MULTIPLE}x suppresses ADD. This is a DESCRIPTIVE "
                f"reference, not a policy limit."
            ),
            "market_value": _num(pos.market_value),
            "market_weight": _num(pos.market_weight),
            "portfolio_market_value": _num(pos.portfolio_market_value),
            "portfolio_positions": pos.portfolio_positions,
            "price_date": pos.price_date.isoformat() if pos.price_date else None,
            "quantity": _num(pos.quantity),
            "sizing_effect": sizing_effect,
            "sizing_explanation": sizing_text,
            "unrealized_pct": _num(pos.unrealized_pct),
            "unrealized_pnl": _num(pos.unrealized_pnl),
        },
        "price_state": price_state,
        "market_environment": {
            "product_evidence": market_state,
            **(market_context or {"benchmarks": None, "macro": None}),
        },
        "fundamentals": fundamentals,
        "earnings": earnings,
        "historical_evidence": {
            "distributions": historical,
            "interpretation_note": (
                "These are UNCONDITIONAL own-history forward-return distributions on "
                "overlapping windows. They are EMPIRICAL_HISTORICAL statistics, not "
                "forecasts, and n overstates independent observations."
            ),
        },
        "deterministic_verdicts": verdict_rows,
        "portfolio_constraints": [c.to_dict() for c in constraints],
        "policy": policy_block,
        "caveats": caveats,
        "evidence_index": [e.to_dict() for e in evidence],
    }

    return HoldingPayload(symbol=pos.symbol, as_of=pos.as_of, body=body)


# ------------------------------------------------------- optional DB enrichment
def load_market_context(session, as_of: date) -> dict[str, Any]:
    """Benchmark and macro context from the existing feature store.

    Read-only, reuses the exact query shape the product slice already uses, and
    is optional: if anything is missing the field is simply ``None``. Kept out
    of ``build_payload`` so the payload stays a pure function.
    """
    from sqlalchemy import text

    benchmarks: dict[str, Any] = {}
    for sym in _BENCHMARKS:
        row_values: dict[str, str | None] = {}
        for feat in _BENCHMARK_FEATURES:
            hit = session.execute(
                text(
                    "select f.value from feature_store_daily f "
                    "join feature_definitions d on d.id=f.feature_id "
                    "join instruments i on i.id=f.instrument_id "
                    "where i.symbol=:s and d.name=:n and f.feature_date<=:d "
                    "and f.value is not null order by f.feature_date desc limit 1"
                ),
                {"s": sym, "n": feat, "d": as_of},
            ).scalar()
            row_values[feat] = None if hit is None else str(hit)
        benchmarks[sym] = row_values

    macro: dict[str, str | None] = {}
    for feat in _MACRO_FEATURES:
        hit = session.execute(
            text(
                "select f.value from feature_store_market_daily f "
                "join feature_definitions d on d.id=f.feature_id "
                "where d.name=:n and f.feature_date<=:d and f.value is not null "
                "order by f.feature_date desc limit 1"
            ),
            {"n": feat, "d": as_of},
        ).scalar()
        macro[feat] = None if hit is None else str(hit)

    return {
        "benchmarks": benchmarks,
        "benchmarks_note": (
            "Trailing total returns for the broad-market ETFs, from the feature store."
        ),
        "macro": macro,
        "macro_note": (
            "Market-scope features from the PIT publication-lagged macro store. "
            "Yield changes are in percentage points."
        ),
    }


def load_identity(session, symbol: str) -> dict[str, str | None]:
    """Company name / sector / industry from the reference tables, if present."""
    from sqlalchemy import text

    # An instrument carries EITHER industry_id OR sector_id (the `single_classification`
    # check constraint), so the sector must be coalesced across both paths — the same
    # resolution `mip.product.quality` uses.
    row = session.execute(
        text(
            "select i.name, coalesce(s1.name, s2.name) as sector, ind.name as industry "
            "from instruments i "
            "left join industries ind on ind.id = i.industry_id "
            "left join sectors s1 on s1.id = ind.sector_id "
            "left join sectors s2 on s2.id = i.sector_id "
            "where i.symbol = :s"
        ),
        {"s": symbol},
    ).first()
    if row is None:
        return {"company_name": None, "sector": None, "industry": None}
    return {"company_name": row[0], "sector": row[1], "industry": row[2]}
