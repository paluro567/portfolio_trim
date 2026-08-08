"""Frozen value objects for the V4 product vertical slice.

Evidence-status contract (docs/v6/PRODUCT_EVIDENCE_BOUNDARY.md):
no calibrated probabilities, no directional recommendations presented as
predictive, no synthetic confidence scalar. Every item declares its status.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum

HORIZONS: tuple[tuple[str, int], ...] = (
    ("1w", 5),
    ("1m", 21),
    ("3m", 63),
    ("6m", 126),
    ("1y", 252),
)


class Status(StrEnum):
    VALIDATED = "VALIDATED"
    DESCRIPTIVE = "DESCRIPTIVE"
    EXPERIMENTAL = "EXPERIMENTAL"
    UNAVAILABLE = "UNAVAILABLE"


class Direction(StrEnum):
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"
    CONFLICTED = "CONFLICTED"
    UNAVAILABLE = "UNAVAILABLE"


class Action(StrEnum):
    ADD = "ADD"
    HOLD = "HOLD"
    TRIM = "TRIM"
    EXIT = "EXIT"
    ABSTAIN = "ABSTAIN"


class Confidence(StrEnum):
    VERY_LOW = "VERY LOW"
    LOW = "LOW"
    MODERATE = "MODERATE"
    # HIGH is deliberately absent: prohibited in the first vertical slice.


class ConstraintStatus(StrEnum):
    PASS = "PASS"
    BREACH = "BREACH"
    NOT_EVALUABLE = "NOT_EVALUABLE"


@dataclass(frozen=True, slots=True)
class Evidence:
    """One observation.

    `domain` is where it came from. `group` is the underlying PHENOMENON it
    measures. Several items may share a group (four momentum windows are one
    phenomenon, not four). Independence is counted by group, never by item.
    """

    name: str
    domain: str
    status: Status
    value: str
    source: str
    as_of: date | None
    horizons: tuple[str, ...]
    explanation: str
    limitations: str
    missing_reason: str | None = None
    direction: Direction = Direction.NEUTRAL
    group: str = "other"
    ambiguous: bool = False

    def to_dict(self) -> dict:
        return {
            "as_of": self.as_of.isoformat() if self.as_of else None,
            "direction": self.direction.value,
            "ambiguous": self.ambiguous,
            "domain": self.domain,
            "group": self.group,
            "explanation": self.explanation,
            "horizons": list(self.horizons),
            "limitations": self.limitations,
            "missing_reason": self.missing_reason,
            "name": self.name,
            "source": self.source,
            "status": self.status.value,
            "value": self.value,
        }


@dataclass(frozen=True, slots=True)
class Constraint:
    name: str
    status: ConstraintStatus
    observed: str
    threshold: str
    reason: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "observed": self.observed,
            "reason": self.reason,
            "status": self.status.value,
            "threshold": self.threshold,
        }


@dataclass(frozen=True, slots=True)
class HorizonVerdict:
    horizon: str
    direction: Direction
    action: Action
    confidence: Confidence
    contributing: tuple[str, ...]
    conflicts: tuple[str, ...]
    rationale: str
    eliminations: tuple[tuple[str, str], ...]  # (rejected action, reason)
    confidence_basis: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "action": self.action.value,
            "confidence": self.confidence.value,
            "confidence_basis": list(self.confidence_basis),
            "conflicts": list(self.conflicts),
            "contributing": list(self.contributing),
            "direction": self.direction.value,
            "eliminations": [list(e) for e in self.eliminations],
            "horizon": self.horizon,
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class PositionState:
    symbol: str
    as_of: date
    quantity: Decimal | None
    average_cost: Decimal | None
    market_price: Decimal | None
    price_date: date | None
    market_value: Decimal | None
    cost_basis: Decimal | None
    unrealized_pnl: Decimal | None
    unrealized_pct: Decimal | None
    cost_weight: Decimal | None
    market_weight: Decimal | None
    portfolio_market_value: Decimal | None
    portfolio_positions: int
    unavailable: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        def s(v):
            return None if v is None else str(v)

        return {
            "as_of": self.as_of.isoformat(),
            "average_cost": s(self.average_cost),
            "cost_basis": s(self.cost_basis),
            "cost_weight": s(self.cost_weight),
            "market_price": s(self.market_price),
            "market_weight": s(self.market_weight),
            "portfolio_market_value": s(self.portfolio_market_value),
            "market_value": s(self.market_value),
            "portfolio_positions": self.portfolio_positions,
            "price_date": self.price_date.isoformat() if self.price_date else None,
            "quantity": s(self.quantity),
            "symbol": self.symbol,
            "unavailable": list(self.unavailable),
            "unrealized_pct": s(self.unrealized_pct),
            "unrealized_pnl": s(self.unrealized_pnl),
        }
