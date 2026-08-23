"""The provider-neutral ingestion contract.

Deliberately composes the DTOs the repository ALREADY has rather than inventing
a parallel set:

    security_master      mip.securities.source.SourceSecurity
    universe_membership  mip.securities.source.SourceConstituent
    sector_history       mip.securities.source.SourceClassification
    delistings           mip.securities.source.SourceDelisting  (+ SourceTerminal)
    prices               mip.research_data.source.SourcePriceBar

Only three DTOs are genuinely new, because nothing in the repository yet
expresses their point-in-time semantics:

    fundamentals_pit     SourceFundamentalFact   — needs a FILING date, not just a period
    earnings_history     SourceEarningsEvent     — needs an OBSERVATION date
    corporate_actions    SourceCorporateAction   — needs an ex-date keyed on security_id

The distinction those three encode is the whole point of this work. A fiscal
period tells you what a number describes; only the filing/observation date tells
you when you were allowed to know it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol, runtime_checkable

from mip.core.exceptions import ConfigurationError
from mip.research_data.source import SourcePriceBar
from mip.securities.source import (
    SourceClassification,
    SourceConstituent,
    SourceDelisting,
    SourceSecurity,
)

# Which SF1-style dimension a fundamental fact came from. Only AS-REPORTED
# dimensions are admissible for calibration: MOST-RECENT-REPORTED dimensions are
# updated when a company restates, so using them at a historical as-of would
# read a later restatement into the past.
AS_REPORTED_DIMENSIONS = frozenset({"ARQ", "ARY", "ART"})
RESTATED_DIMENSIONS = frozenset({"MRQ", "MRY", "MRT"})


@dataclass(frozen=True, slots=True)
class SourceFundamentalFact:
    """One fundamental observation, with the date it became knowable.

    ``filing_date`` is load-bearing. ``report_period`` says which quarter the
    figure describes; ``filing_date`` says when it reached the public. A PIT
    query filters on the latter and never on the former.
    """

    source_security_id: str
    dimension: str  # ARQ / ARY / ART (admissible) or MRQ / MRY / MRT (not)
    report_period: date  # fiscal period the figure describes
    filing_date: date  # when it was filed and therefore knowable
    calendar_date: date | None = None  # vendor's calendar-aligned label
    last_updated: date | None = None  # vendor revision marker, for incremental loads
    metrics: dict[str, Any] | None = None  # pe, ps, pb, margins, debt/equity, ...

    @property
    def is_point_in_time(self) -> bool:
        """True only for as-reported dimensions carrying a filing date."""
        return self.dimension in AS_REPORTED_DIMENSIONS and self.filing_date is not None

    def knowable_on(self, as_of: date) -> bool:
        return self.is_point_in_time and self.filing_date <= as_of


@dataclass(frozen=True, slots=True)
class SourceEarningsEvent:
    """One earnings event, with the date the platform could have known it.

    Four dates are kept apart on purpose, because collapsing them is exactly how
    the current `earnings_observations` table became unusable:

      event_date        when the quarter's result relates to / was reported
      announced_at      timestamp of the announcement, where the vendor has it
      scheduled_date    the date as SCHEDULED beforehand (may differ from actual)
      observed_at       when this record became available to us

    ``consensus_eps`` is nullable and must stay null unless a genuinely
    contemporaneous estimate is available. A consensus figure pulled today is
    not what the market expected then.
    """

    source_security_id: str
    event_date: date
    observed_at: date
    announced_at: datetime | None = None
    scheduled_date: date | None = None
    actual_eps: float | None = None
    consensus_eps: float | None = None
    consensus_observed_at: date | None = None  # when the estimate itself was current

    @property
    def has_contemporaneous_consensus(self) -> bool:
        """Whether a beat/miss can be computed without hindsight."""
        return (
            self.consensus_eps is not None
            and self.consensus_observed_at is not None
            and self.consensus_observed_at <= self.event_date
        )

    def knowable_on(self, as_of: date) -> bool:
        return self.observed_at <= as_of


@dataclass(frozen=True, slots=True)
class SourceCorporateAction:
    """A split, dividend or structural action, keyed on the vendor's permanent id."""

    source_security_id: str
    ex_date: date
    action_type: str  # split | dividend | spinoff | merger | ticker_change | delisting
    ratio: float | None = None
    amount: float | None = None
    contra_source_security_id: str | None = None  # counterparty in a merger/spinoff
    details: dict[str, Any] | None = None


@runtime_checkable
class HistoricalDataProvider(Protocol):
    """What any survivorship-clean historical provider must supply.

    Every method is as-of aware where point-in-time semantics apply. A provider
    that cannot honour an as-of filter must raise rather than return restated
    values, because silently-restated data is indistinguishable from clean data
    downstream.
    """

    @property
    def name(self) -> str: ...

    @property
    def coverage(self) -> tuple[date, date]:
        """(earliest, latest) dates the provider can serve."""
        ...

    def load_security_master(self) -> Iterable[SourceSecurity]:
        """Every security ever covered, INCLUDING delisted ones."""
        ...

    def load_universe_membership(self, as_of: date) -> Iterable[SourceConstituent]:
        """Universe members as of a historical date, by the declared policy."""
        ...

    def load_prices(
        self, source_security_ids: list[str], start: date, end: date
    ) -> Iterable[SourcePriceBar]: ...

    def load_fundamentals_pit(
        self, source_security_ids: list[str], as_of: date
    ) -> Iterable[SourceFundamentalFact]:
        """Only as-reported facts whose filing_date <= as_of."""
        ...

    def load_sector_history(
        self, source_security_ids: list[str], as_of: date
    ) -> Iterable[SourceClassification]:
        """Classification effective at ``as_of``, not today's classification."""
        ...

    def load_earnings_history(
        self, source_security_ids: list[str], as_of: date
    ) -> Iterable[SourceEarningsEvent]:
        """Only events whose observed_at <= as_of."""
        ...

    def load_corporate_actions(
        self, source_security_ids: list[str], start: date, end: date
    ) -> Iterable[SourceCorporateAction]: ...

    def load_delistings(
        self, source_security_ids: list[str]
    ) -> Iterable[tuple[str, SourceDelisting]]:
        """(source_security_id, delisting). Terminal return may be null."""
        ...


@dataclass
class _BlockedHistoricalProvider:
    """The only provider configured today, and it refuses to serve.

    Deliberate: a fallback to the legacy survivor-only tables would produce a
    calibration that looks complete and measures survival.
    """

    name: str = "blocked"

    def __getattr__(self, item: str) -> Any:
        raise ConfigurationError(
            "No survivorship-clean historical provider is configured. Ingestion is "
            "blocked rather than falling back to the survivor-only legacy tables. "
            "See docs/data/SHARADAR_INGESTION_PLAN.md."
        )


def blocked_historical_provider() -> HistoricalDataProvider:
    return _BlockedHistoricalProvider()  # type: ignore[return-value]
