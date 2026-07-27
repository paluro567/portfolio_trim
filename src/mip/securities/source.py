"""Vendor-independent source-adapter contract for the security master.

The canonical model never depends on one vendor's column names: every adapter
yields these frozen DTOs. A future survivorship-clean provider (Norgate /
Sharadar / CRSP) is a new adapter implementing ``SecuritySource``; downstream
ingestion is untouched.

Phase 1 status: the real paid source is NOT licensed. ``FixtureSource`` (for
tests + a documented sample) is the only concrete adapter; ``blocked_source``
raises loudly so nothing silently falls back to a survivor-only feed.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from mip.core.exceptions import ConfigurationError
from mip.domain.enums import IdentifierType, LifecycleEventType, SecurityType


@dataclass(frozen=True)
class SourceIdentifier:
    identifier_type: IdentifierType
    identifier_value: str
    valid_from: date
    valid_to: date | None = None
    exchange: str | None = None
    is_primary: bool = True


@dataclass(frozen=True)
class SourceLifecycleEvent:
    event_type: LifecycleEventType
    effective_date: date
    announcement_date: date | None = None
    successor_source_id: str | None = None  # vendor id; ingestor maps to security_id
    predecessor_source_id: str | None = None
    details: dict | None = None


@dataclass(frozen=True)
class SourceDelisting:
    delisting_date: date
    delisting_code: str | None = None
    delisting_reason: str | None = None
    successor_source_id: str | None = None
    # delisting_return / terminal_price are Phase-2 (price data); never fabricated here.


@dataclass(frozen=True)
class SourceClassification:
    scheme: str
    valid_from: date
    valid_to: date | None = None
    sector: str | None = None
    industry_group: str | None = None
    industry: str | None = None
    sub_industry: str | None = None


@dataclass(frozen=True)
class SourceSecurity:
    """One security as the vendor knows it. ``source_security_id`` is the
    vendor's PERMANENT id — the resolution + idempotency anchor. A record with
    an empty permanent id cannot be identity-resolved and is quarantined."""

    source_security_id: str
    security_type: SecurityType
    name: str | None = None
    share_class: str | None = None
    country: str | None = "US"
    currency: str = "USD"
    primary_exchange: str | None = None
    first_trade_date: date | None = None
    last_trade_date: date | None = None
    active: bool = True
    delisted: bool = False
    delisting_date: date | None = None
    delisting_reason: str | None = None
    identifiers: tuple[SourceIdentifier, ...] = ()
    lifecycle_events: tuple[SourceLifecycleEvent, ...] = ()
    delisting: SourceDelisting | None = None
    classifications: tuple[SourceClassification, ...] = ()


@dataclass(frozen=True)
class SourceConstituent:
    """Optional point-in-time universe membership provided directly by a vendor
    (e.g. historical index constituents). ``source_security_id`` links to a
    SourceSecurity."""

    source_security_id: str
    membership_date: date
    included: bool = True


class SecuritySource(Protocol):
    """The adapter contract. Every record carries source lineage; the ingestor
    stamps ingestion_run_id + data_version. ``data_version`` identifies the
    immutable vendor snapshot for reproducibility."""

    name: str
    data_version: str

    def securities(self) -> Iterable[SourceSecurity]: ...

    def constituents(self) -> Iterable[SourceConstituent]: ...


@dataclass
class FixtureSource:
    """In-memory adapter for tests and documented samples. NOT a production
    survivorship-clean source."""

    name: str
    data_version: str
    _securities: tuple[SourceSecurity, ...] = ()
    _constituents: tuple[SourceConstituent, ...] = ()

    def securities(self) -> Iterable[SourceSecurity]:
        return self._securities

    def constituents(self) -> Iterable[SourceConstituent]:
        return self._constituents


@dataclass
class _BlockedSource:
    """Placeholder for a real survivorship-clean vendor not yet licensed.
    Raises loudly so nothing silently falls back to a survivor-only feed."""

    name: str = "unlicensed"
    data_version: str = "blocked"

    def securities(self) -> Iterable[SourceSecurity]:
        raise ConfigurationError(
            "No survivorship-clean security source is licensed. A survivor-only "
            "feed (yfinance) does NOT solve survivorship — see docs/SECURITY_MASTER.md. "
            "Select a source (Norgate / Sharadar / CRSP) and implement its adapter."
        )

    def constituents(self) -> Iterable[SourceConstituent]:
        return self.securities()  # raises


def blocked_source() -> _BlockedSource:
    return _BlockedSource()
