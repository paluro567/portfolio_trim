"""PolicyArtifact: the only home for investor preferences.

The system never invents a policy value. Every field below must be supplied
explicitly by the portfolio owner. An unset required value yields
``PolicyUnavailable`` carrying the exact list of what the owner must state,
and every dependent constraint stays NOT_EVALUABLE.

Scope note: this is the minimum artifact the current vertical slice consumes.
The frozen DOMAIN_MODEL.md specifies further fields (band_pp, sector_cap_pct,
liquidity_limit_days, participation_rate, gains_budget, objective_order,
tolerance_bands, tier_caps, rubric). They are deliberately absent because no
implemented constraint reads them yet.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml

DEFAULT_POLICY_PATH = Path("config/policy/personal.yaml")
REQUIRED = ("hard_cap_pct", "core_target_pct")


class PolicyError(ValueError):
    """The policy file exists but is invalid. Never silently ignored."""


@dataclass(frozen=True, slots=True)
class PolicyUnavailable:
    """A policy could not be loaded. Carries what the owner must supply."""

    reason: str
    missing: tuple[str, ...]
    path: str

    def to_dict(self) -> dict:
        return {
            "missing": list(self.missing),
            "path": self.path,
            "reason": self.reason,
            "status": "UNAVAILABLE",
        }


@dataclass(frozen=True, slots=True)
class PolicyArtifact:
    policy_version: str
    effective_date: date
    hard_cap_pct: Decimal
    core_target_pct: Decimal
    authored_by: str
    source: str
    content_hash: str

    def to_dict(self) -> dict:
        return {
            "authored_by": self.authored_by,
            "content_hash": self.content_hash,
            "core_target_pct": str(self.core_target_pct),
            "effective_date": self.effective_date.isoformat(),
            "hard_cap_pct": str(self.hard_cap_pct),
            "policy_version": self.policy_version,
            "source": self.source,
            "status": "SUPPLIED",
        }


def _pct(raw, field: str) -> Decimal:
    try:
        v = Decimal(str(raw))
    except (InvalidOperation, TypeError) as exc:
        raise PolicyError(f"{field}: not a valid number ({raw!r})") from exc
    if v <= 0:
        raise PolicyError(f"{field}: must be greater than 0 (got {v})")
    if v > 100:
        raise PolicyError(f"{field}: must not exceed 100 (got {v})")
    return v


def load_policy(path: Path = DEFAULT_POLICY_PATH) -> PolicyArtifact | PolicyUnavailable:
    """Load and validate. Returns PolicyUnavailable when values are unset."""
    if not path.exists():
        return PolicyUnavailable(
            reason=f"no policy file at {path}",
            missing=list(REQUIRED),
            path=str(path),
        )
    raw = yaml.safe_load(path.read_text()) or {}
    if not isinstance(raw, dict):
        raise PolicyError(f"{path}: top level must be a mapping")

    portfolio = raw.get("portfolio") or {}
    if not isinstance(portfolio, dict):
        raise PolicyError(f"{path}: 'portfolio' must be a mapping")

    missing = [f for f in REQUIRED if portfolio.get(f) in (None, "", [])]
    if not raw.get("policy_version"):
        missing.append("policy_version")
    if not raw.get("effective_date"):
        missing.append("effective_date")
    if missing:
        return PolicyUnavailable(
            reason=(
                "policy values have not been supplied by the portfolio owner; "
                "the system does not invent them"
            ),
            missing=tuple(missing),
            path=str(path),
        )

    eff = raw["effective_date"]
    if isinstance(eff, str):
        try:
            eff = date.fromisoformat(eff)
        except ValueError as exc:
            raise PolicyError(f"effective_date: not an ISO date ({eff!r})") from exc
    if not isinstance(eff, date):
        raise PolicyError(f"effective_date: not a date ({eff!r})")

    cap = _pct(portfolio["hard_cap_pct"], "hard_cap_pct")
    target = _pct(portfolio["core_target_pct"], "core_target_pct")
    if target > cap:
        raise PolicyError(f"core_target_pct ({target}) must not exceed hard_cap_pct ({cap})")

    return PolicyArtifact(
        policy_version=str(raw["policy_version"]),
        effective_date=eff,
        hard_cap_pct=cap,
        core_target_pct=target,
        authored_by=str(raw.get("authored_by") or "unspecified"),
        source=str(path),
        content_hash=hashlib.sha256(path.read_bytes()).hexdigest(),
    )
