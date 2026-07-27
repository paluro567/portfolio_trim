"""Vendor-independent adapter contract for native survivorship-clean outcomes.

The canonical native tables never depend on one vendor's columns: every adapter
yields these frozen DTOs keyed by the vendor's PERMANENT id (``source_security_id``,
the Phase-1 resolution anchor) — NEVER by ticker. A future provider (Norgate /
Sharadar / CRSP) is a new adapter implementing ``OutcomeSource``.

Phase 2A status: no paid survivorship-clean price source is licensed.
``FixtureOutcomeSource`` (tests + documented samples) is the only concrete
adapter; ``blocked_outcome_source`` raises loudly so nothing silently falls back
to a survivor-only feed (e.g. yfinance) and calls the result survivorship-clean.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Protocol

from mip.core.exceptions import ConfigurationError
from mip.domain.enums import SecurityType, TerminalRule

# Provider posture (approved & frozen): Norgate primary, Sharadar supplemental
# PIT + cross-check, CRSP optional audit. See docs/PHASE2_DESIGN.md.
APPROVED_PROVIDERS = ("norgate", "sharadar", "crsp")


@dataclass(frozen=True)
class SourcePriceBar:
    """One daily bar as the vendor knows it, tagged with the vendor's permanent
    id. Adjusted values are the vendor's; raw close is always retained so any
    adjustment policy is reproducible. Never fabricated."""

    source_security_id: str
    trade_date: date
    close: Decimal | None
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    adjusted_close: Decimal | None = None
    volume: int | None = None
    total_return_factor: Decimal | None = None
    split_factor: Decimal | None = None
    dividend_amount: Decimal | None = None
    currency: str = "USD"
    exchange: str | None = None
    source_record_id: str | None = None


@dataclass(frozen=True)
class SourceMarketSnapshot:
    """Point-in-time exposure/eligibility inputs. Absent values stay None — a
    market cap is never reconstructed from today's shares projected backward."""

    source_security_id: str
    snapshot_date: date
    price: Decimal | None = None
    shares_outstanding: int | None = None
    market_cap: Decimal | None = None
    volume: int | None = None
    average_dollar_volume: Decimal | None = None
    exchange: str | None = None
    security_type: SecurityType | None = None
    sector: str | None = None


@dataclass(frozen=True)
class SourceBenchmarkBar:
    benchmark_key: str  # 'MARKET' or 'SECTOR:<gics sector>'
    kind: str  # 'market' | 'sector'
    trade_date: date
    total_return: Decimal | None


@dataclass(frozen=True)
class SourceTerminal:
    """Vendor-provided terminal (delisting/M&A/bankruptcy) outcome. The ingestor
    maps this to a deterministic ``TerminalRule`` and records the resulting
    investor value — never assumed to be -100% when the vendor does not say so."""

    source_security_id: str
    event_date: date
    rule: TerminalRule
    terminal_return: Decimal | None = None
    terminal_value: Decimal | None = None
    cash_consideration: Decimal | None = None
    successor_source_id: str | None = None
    resolved: bool = True
    confidence: float | None = None


class OutcomeSource(Protocol):
    """The native-outcome adapter contract. Every record carries source lineage;
    the ingestor stamps ingestion_run_id + data_version. ``data_version``
    identifies the immutable vendor snapshot for reproducibility."""

    name: str
    data_version: str

    def prices(self) -> Iterable[SourcePriceBar]: ...

    def market_snapshots(self) -> Iterable[SourceMarketSnapshot]: ...

    def benchmarks(self) -> Iterable[SourceBenchmarkBar]: ...

    def terminals(self) -> Iterable[SourceTerminal]: ...


@dataclass
class FixtureOutcomeSource:
    """In-memory adapter for tests and documented samples. NOT a production
    survivorship-clean source (though it is deliberately built to REPRESENT
    delisted names, so survivorship logic can be exercised)."""

    name: str
    data_version: str
    _prices: tuple[SourcePriceBar, ...] = ()
    _market: tuple[SourceMarketSnapshot, ...] = ()
    _benchmarks: tuple[SourceBenchmarkBar, ...] = ()
    _terminals: tuple[SourceTerminal, ...] = field(default_factory=tuple)

    def prices(self) -> Iterable[SourcePriceBar]:
        return self._prices

    def market_snapshots(self) -> Iterable[SourceMarketSnapshot]:
        return self._market

    def benchmarks(self) -> Iterable[SourceBenchmarkBar]:
        return self._benchmarks

    def terminals(self) -> Iterable[SourceTerminal]:
        return self._terminals


@dataclass
class _BlockedOutcomeSource:
    """Placeholder for a real survivorship-clean vendor not yet licensed. Raises
    loudly so nothing silently falls back to a survivor-only feed."""

    name: str = "unlicensed"
    data_version: str = "blocked"

    def prices(self) -> Iterable[SourcePriceBar]:
        raise ConfigurationError(
            "No survivorship-clean outcome source is licensed. A survivor-only "
            "feed (yfinance/stooq) does NOT solve survivorship or carry delisting "
            "returns — see docs/PHASE2_DESIGN.md. License Norgate (primary) + "
            "Sharadar (PIT/cross-check) and implement their adapters."
        )

    def market_snapshots(self) -> Iterable[SourceMarketSnapshot]:
        return self.prices()  # raises

    def benchmarks(self) -> Iterable[SourceBenchmarkBar]:
        return self.prices()  # raises

    def terminals(self) -> Iterable[SourceTerminal]:
        return self.prices()  # raises


def blocked_outcome_source() -> _BlockedOutcomeSource:
    return _BlockedOutcomeSource()
