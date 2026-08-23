"""Provider-neutral historical-data interface (§11).

The application must never be hard-coded to one vendor. This declares the
logical datasets a calibration study needs, in vendor-agnostic terms, and a
protocol any provider can satisfy.

It follows the discipline already established in ``mip.securities.source``:
``blocked_source()`` RAISES rather than silently falling back to the survivor-only
feed the platform already has. Producing a plausible-looking calibration from
the wrong data is worse than producing none.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol, runtime_checkable


class HistoricalSourceUnavailableError(RuntimeError):
    """No licensed survivorship-clean provider is configured."""


@dataclass(frozen=True, slots=True)
class DatasetRequirement:
    """One logical dataset, and what calibration needs from it."""

    name: str
    purpose: str
    required_fields: tuple[str, ...]
    existing_table: str | None
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "existing_table": self.existing_table,
            "name": self.name,
            "purpose": self.purpose,
            "required_fields": list(self.required_fields),
            "status": self.status,
        }


# The ingestion contract. `existing_table` names the repo table that already
# represents the concept where one exists — the schema is reused, not redesigned.
REQUIRED_DATASETS: tuple[DatasetRequirement, ...] = (
    DatasetRequirement(
        name="security_master",
        purpose="Permanent non-ticker identity so a name change is not a new security.",
        required_fields=("security_id", "source", "source_security_id", "first_seen", "last_seen"),
        existing_table="security_master",
        status="TABLE EXISTS, EMPTY",
    ),
    DatasetRequirement(
        name="prices",
        purpose="Split/dividend-adjusted daily prices keyed on security_id, including "
        "securities that later delisted.",
        required_fields=("security_id", "price_date", "open", "high", "low", "close", "volume"),
        existing_table="security_price_daily",
        status="TABLE EXISTS, EMPTY (legacy daily_prices is survivor-only, ticker-keyed)",
    ),
    DatasetRequirement(
        name="fundamentals_pit",
        purpose="Fundamentals as reported AND as knowable on each historical date — "
        "vintages, not restatements.",
        required_fields=("security_id", "as_of_date", "period_end", "publication_date", "metrics"),
        existing_table="company_fundamentals",
        status="TABLE EXISTS, SNAPSHOT-ONLY (3 as-of dates; no vintages)",
    ),
    DatasetRequirement(
        name="sector_history",
        purpose="Sector/industry as classified AT the historical date, not today.",
        required_fields=("security_id", "valid_from", "valid_to", "scheme", "sector", "industry"),
        existing_table="historical_classification",
        status="TABLE EXISTS, EMPTY",
    ),
    DatasetRequirement(
        name="earnings_history",
        purpose="Earnings events with the date they became observable, so a historical "
        "as-of sees only what was knowable then.",
        required_fields=(
            "security_id",
            "earnings_date",
            "observed_at",
            "eps_estimate",
            "eps_actual",
        ),
        existing_table="earnings_observations",
        status="TABLE EXISTS, CONTAMINATED (25y of events, 3 observation dates)",
    ),
    DatasetRequirement(
        name="corporate_actions",
        purpose="Splits, dividends and structural events for correct adjustment.",
        required_fields=("security_id", "ex_date", "action_type", "ratio", "amount"),
        existing_table="corporate_actions",
        status="TABLE EXISTS, POPULATED but ticker-keyed and survivor-only",
    ),
    DatasetRequirement(
        name="delistings",
        purpose="Delisting date, reason and TERMINAL RETURN, so a delisted position has an "
        "outcome instead of vanishing from the sample.",
        required_fields=(
            "security_id",
            "delisting_date",
            "reason",
            "delisting_return",
            "terminal_price",
        ),
        existing_table="delisting_event",
        status="TABLE EXISTS, EMPTY — this is the single most important gap",
    ),
    DatasetRequirement(
        name="universe_membership",
        purpose="Point-in-time index/universe constituents, so the study population is what "
        "it was then rather than what survived.",
        required_fields=("universe_id", "security_id", "valid_from", "valid_to"),
        existing_table="universe_membership",
        status="TABLE EXISTS, EMPTY",
    ),
)


@runtime_checkable
class HistoricalDataSource(Protocol):
    """What any provider must supply. Vendor-agnostic by construction."""

    @property
    def name(self) -> str: ...

    @property
    def as_of_coverage(self) -> tuple[date, date]: ...

    def securities(self, as_of: date) -> list[dict[str, Any]]:
        """Universe members as of a historical date, INCLUDING those later delisted."""
        ...

    def prices(self, security_ids: list[int], start: date, end: date) -> list[dict[str, Any]]: ...

    def fundamentals_pit(self, security_ids: list[int], as_of: date) -> list[dict[str, Any]]:
        """Only vintages observable on ``as_of``."""
        ...

    def sector_history(self, security_ids: list[int], as_of: date) -> list[dict[str, Any]]: ...

    def earnings_history(self, security_ids: list[int], as_of: date) -> list[dict[str, Any]]:
        """Only events whose observation date is on or before ``as_of``."""
        ...

    def delistings(self, security_ids: list[int]) -> list[dict[str, Any]]: ...


def blocked_source() -> HistoricalDataSource:
    """The only source configured today, and it refuses to serve.

    Deliberate: falling back to the legacy survivor-only tables would produce a
    calibration that looks complete and measures selection.
    """
    raise HistoricalSourceUnavailableError(
        "No survivorship-clean historical provider is licensed or configured. "
        "Calibration is blocked rather than run against the survivor-only legacy "
        "tables. See docs/HISTORICAL_CALIBRATION_READINESS.md for the ingestion "
        "contract."
    )


def contract_summary() -> list[dict[str, Any]]:
    return [d.to_dict() for d in REQUIRED_DATASETS]
