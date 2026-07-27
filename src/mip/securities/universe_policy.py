"""Versioned, machine-readable universe eligibility policy.

Eligibility is decided using ONLY information available on the membership date:
the security must have a point-in-time listing (a ticker valid that day), enough
trading history, an eligible type and exchange, and must not yet be delisted.
Securities are retained through their actual delisting date and are NEVER removed
retroactively because they later failed.

Market-cap / price / dollar-volume filters are declared but marked PENDING until
Phase 2 supplies the historical data — the policy does not pretend the universe
is fully investable before those filters exist.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from mip.domain.enums import SecurityType


@dataclass(frozen=True)
class UniversePolicy:
    name: str
    version: int
    description: str
    eligible_exchanges: tuple[str, ...]
    eligible_security_types: tuple[SecurityType, ...]
    include_adr: bool
    min_trading_age_days: int
    reconstitution: str  # 'monthly'
    # configurable, PENDING Phase 2 (data not yet present):
    min_price: float | None = None
    min_market_cap: float | None = None
    min_dollar_volume: float | None = None
    pending_filters: tuple[str, ...] = field(
        default_factory=lambda: ("min_price", "min_market_cap", "min_dollar_volume")
    )

    def to_rules_json(self) -> dict:
        return {
            "eligible_exchanges": list(self.eligible_exchanges),
            "eligible_security_types": [t.value for t in self.eligible_security_types],
            "include_adr": self.include_adr,
            "min_trading_age_days": self.min_trading_age_days,
            "reconstitution": self.reconstitution,
            "min_price": self.min_price,
            "min_market_cap": self.min_market_cap,
            "min_dollar_volume": self.min_dollar_volume,
            "pending_filters": list(self.pending_filters),
            "note": (
                "PENDING filters require Phase-2 price/market-cap history and are "
                "NOT applied yet; this universe is not certified fully investable."
            ),
        }

    def _type_ok(self, security_type: SecurityType) -> bool:
        if security_type in self.eligible_security_types:
            return True
        return self.include_adr and security_type is SecurityType.ADR

    def eligibility(
        self,
        *,
        security_type: SecurityType,
        first_trade_date: date | None,
        delisting_date: date | None,
        exchange: str | None,
        has_listing_as_of: bool,
        as_of: date,
    ) -> tuple[bool, str | None]:
        """(included, exclusion_reason). Uses only <= as_of information."""
        if not has_listing_as_of:
            return False, "not_listed_as_of"
        if delisting_date is not None and delisting_date <= as_of:
            return False, "delisted"  # never extend membership past delisting
        if not self._type_ok(security_type):
            return False, f"ineligible_type:{security_type.value}"
        if exchange is not None and exchange not in self.eligible_exchanges:
            return False, f"ineligible_exchange:{exchange}"
        if first_trade_date is None:
            return False, "no_first_trade_date"
        if (as_of - first_trade_date).days < self.min_trading_age_days:
            return False, "insufficient_history"
        return True, None


# The provisional validation-tier policy (docs/EVALUATION_FOUNDATION_DESIGN.md).
US_COMMON_EQUITY_V1 = UniversePolicy(
    name="us_common_equity",
    version=1,
    description=(
        "U.S.-listed ordinary common equity on NYSE/Nasdaq/NYSE American; ETFs, "
        "preferreds, warrants, rights, units, and closed-end funds excluded; ADRs "
        "labelled and excluded by default. Monthly reconstitution; securities "
        "retained through their actual delisting date. Liquidity/size/price "
        "filters PENDING Phase 2."
    ),
    eligible_exchanges=("NYSE", "NASDAQ", "NYSE American", "NYSEAMERICAN", "AMEX"),
    eligible_security_types=(SecurityType.COMMON,),
    include_adr=False,
    min_trading_age_days=252,  # ~1 trading year
    reconstitution="monthly",
)
