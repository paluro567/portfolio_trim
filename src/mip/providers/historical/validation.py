"""Data-quality checks for ingested historical data.

These are the checks that must pass BEFORE the calibration readiness gate can
mean anything: the gate asks "is the data present and PIT?", these ask "is what
arrived internally consistent?".

Each check declares which readiness-gate check it feeds, so a failure here
explains a failure there rather than being a separate mystery.

The predicate functions are small and pure so they can be unit-tested against
fixtures without a database or a vendor.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any

from mip.providers.historical.contract import (
    AS_REPORTED_DIMENSIONS,
    SourceEarningsEvent,
    SourceFundamentalFact,
)


@dataclass(frozen=True, slots=True)
class QualityCheck:
    name: str
    description: str
    feeds_gate_check: str | None
    severity: str  # BLOCKING | WARNING

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "feeds_gate_check": self.feeds_gate_check,
            "name": self.name,
            "severity": self.severity,
        }


CHECKS: tuple[QualityCheck, ...] = (
    QualityCheck(
        "duplicate_identity",
        "Two security_master rows resolving to the same vendor permanent id.",
        "survivorship_control",
        "BLOCKING",
    ),
    QualityCheck(
        "ticker_reuse",
        "One ticker mapping to more than one permanent id over time without disjoint "
        "validity windows — the classic silent merge of two different companies.",
        "survivorship_control",
        "BLOCKING",
    ),
    QualityCheck(
        "missing_permanent_identifier",
        "A vendor record with no permanent id; cannot be identity-resolved.",
        "survivorship_control",
        "BLOCKING",
    ),
    QualityCheck(
        "impossible_date_ordering",
        "first_trade_date > last_trade_date, or delisting_date before first_trade_date.",
        None,
        "BLOCKING",
    ),
    QualityCheck(
        "future_leakage",
        "Any record whose availability date is after the as-of it was served for.",
        "pit_fundamentals",
        "BLOCKING",
    ),
    QualityCheck(
        "fundamentals_available_before_filing",
        "A fundamental fact visible at an as-of earlier than its filing date.",
        "pit_fundamentals",
        "BLOCKING",
    ),
    QualityCheck(
        "restated_dimension_used",
        "An MRQ/MRY/MRT fact reaching PIT_CLEAN. Restated values are not point-in-time.",
        "pit_fundamentals",
        "BLOCKING",
    ),
    QualityCheck(
        "delisted_missing_terminal_outcome",
        "A delisted security with no terminal outcome — the row that, if dropped, "
        "biases every forward-return statistic upward.",
        "survivorship_control",
        "BLOCKING",
    ),
    QualityCheck(
        "price_gaps",
        "Missing sessions against the exchange calendar for a security that was listed.",
        "price_history_depth",
        "WARNING",
    ),
    QualityCheck(
        "corporate_action_inconsistency",
        "A split factor in ACTIONS that the price series does not reflect, or vice versa.",
        None,
        "BLOCKING",
    ),
    QualityCheck(
        "sector_classification_leakage",
        "A classification with no valid_from, i.e. today's sector applied to all history.",
        "pit_classification",
        "BLOCKING",
    ),
    QualityCheck(
        "earnings_observed_before_availability",
        "An earnings event whose observed_at precedes its event_date.",
        "pit_earnings",
        "BLOCKING",
    ),
    QualityCheck(
        "earnings_consensus_not_contemporaneous",
        "A beat/miss computed against an estimate that was not current at the event.",
        "pit_earnings",
        "BLOCKING",
    ),
    QualityCheck(
        "universe_membership_gaps",
        "A date in the study period with no membership rows, or a security that leaves "
        "and re-enters without an exclusion reason.",
        "survivorship_control",
        "BLOCKING",
    ),
)


# ------------------------------------------------------------------ predicates
def fundamentals_pit_violations(facts: Iterable[SourceFundamentalFact], as_of: date) -> list[str]:
    """Facts that must not be visible at ``as_of``. Empty list means clean."""
    bad: list[str] = []
    for fact in facts:
        if fact.dimension not in AS_REPORTED_DIMENSIONS:
            bad.append(f"{fact.source_security_id}: restated dimension {fact.dimension}")
            continue
        if fact.filing_date is None:
            bad.append(f"{fact.source_security_id}: no filing date")
            continue
        if fact.filing_date > as_of:
            bad.append(f"{fact.source_security_id}: filed {fact.filing_date} but served at {as_of}")
        if fact.report_period > fact.filing_date:
            bad.append(
                f"{fact.source_security_id}: report period {fact.report_period} after "
                f"filing {fact.filing_date}"
            )
    return bad


def earnings_pit_violations(events: Iterable[SourceEarningsEvent], as_of: date) -> list[str]:
    bad: list[str] = []
    for ev in events:
        if ev.observed_at > as_of:
            bad.append(f"{ev.source_security_id}: observed {ev.observed_at}, served at {as_of}")
        if ev.observed_at < ev.event_date:
            bad.append(
                f"{ev.source_security_id}: observed {ev.observed_at} before event "
                f"{ev.event_date}"
            )
        if ev.consensus_eps is not None and not ev.has_contemporaneous_consensus:
            bad.append(
                f"{ev.source_security_id}: consensus supplied without a contemporaneous "
                f"observation date"
            )
    return bad


def select_pit_fundamental(
    facts: Iterable[SourceFundamentalFact], as_of: date, report_period: date | None = None
) -> SourceFundamentalFact | None:
    """The PIT selection rule, stated once.

    Among as-reported facts filed on or before ``as_of``, take the one with the
    LATEST filing date. That is what a reader knew on ``as_of``, including any
    amended filing that had arrived by then — and excluding every amendment that
    had not. Selecting by fiscal period instead would silently pick a later
    restatement.
    """
    admissible = [
        f
        for f in facts
        if f.knowable_on(as_of) and (report_period is None or f.report_period == report_period)
    ]
    if not admissible:
        return None
    return max(admissible, key=lambda f: (f.filing_date, f.report_period))


def checks_for_gate(gate_check: str) -> tuple[QualityCheck, ...]:
    return tuple(c for c in CHECKS if c.feeds_gate_check == gate_check)


def blocking_checks() -> tuple[QualityCheck, ...]:
    return tuple(c for c in CHECKS if c.severity == "BLOCKING")


def contract_summary() -> list[dict[str, Any]]:
    return [c.to_dict() for c in CHECKS]


__all__: list[str] = [
    "CHECKS",
    "QualityCheck",
    "blocking_checks",
    "checks_for_gate",
    "contract_summary",
    "earnings_pit_violations",
    "fundamentals_pit_violations",
    "select_pit_fundamental",
]
