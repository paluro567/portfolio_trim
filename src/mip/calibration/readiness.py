"""The data-quality gate.

This is a live check, not a claim in a document. It re-runs against the actual
database every time, so calibration cannot silently start producing numbers
because someone assumed the data had arrived.

Three independent conditions must ALL hold before a forward-return study is
defensible:

1. **Survivorship control.** A universe containing no delisted securities makes
   a forward-return study a measurement of selection, not of signal. Every name
   in it is present precisely because it survived.
2. **Point-in-time reconstruction.** Fundamentals and earnings must be
   observable *as of* the historical date, not restated today. A 25-year
   earnings history witnessed in one ingest last month is lookahead, however
   accurate the dates are.
3. **Signal reconstructability.** The deterministic security view is a vote
   across phenomenon groups. If a group's inputs cannot be reconstructed
   historically, the view at that horizon cannot be reconstructed either — so
   there is no state to condition on.

Failing any one of them means the honest output is UNAVAILABLE.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text

from mip.calibration.contracts import HORIZONS
from mip.product.slice import DELIVERY_HORIZONS, QUALITY_VOTING_HORIZONS, VALUATION_HORIZONS

# Minimum distinct observation dates before a source counts as a time series
# rather than a snapshot. Two is generous; a real PIT source has thousands.
MIN_PIT_OBSERVATION_DATES = 250

# Directional evidence groups whose inputs are price-derived, and therefore
# reconstructable at any historical date from `daily_prices` alone.
PRICE_DERIVED_GROUPS = frozenset(
    {
        "absolute_momentum",
        "trend_position",
        "market_relative",
        "sector_relative",
        "market_regime",
        "volatility",
        "own_history",
    }
)


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    passed: bool
    observed: str
    requirement: str
    blocker: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "blocker": self.blocker,
            "name": self.name,
            "observed": self.observed,
            "passed": self.passed,
            "requirement": self.requirement,
        }


@dataclass(slots=True)
class ReadinessReport:
    checks: list[Check] = field(default_factory=list)
    reconstructable_horizons: tuple[str, ...] = ()
    blocked_horizons: dict[str, list[str]] = field(default_factory=dict)

    @property
    def gate_passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def blockers(self) -> list[str]:
        return [c.blocker for c in self.checks if not c.passed and c.blocker]

    def reason(self) -> str:
        """One line suitable for a calibration `unavailable_reason`."""
        if self.gate_passed:
            return ""
        return "; ".join(self.blockers)

    def to_dict(self) -> dict[str, Any]:
        return {
            "blocked_horizons": self.blocked_horizons,
            "blockers": self.blockers,
            "checks": [c.to_dict() for c in self.checks],
            "gate_passed": self.gate_passed,
            "reconstructable_horizons": list(self.reconstructable_horizons),
        }


def _scalar(session, sql: str) -> Any:
    return session.execute(text(sql)).scalar()


def assess_readiness(session) -> ReadinessReport:
    """Run the gate against the live database."""
    report = ReadinessReport()

    # -- 1. survivorship -----------------------------------------------------
    delisted = _scalar(session, "select count(*) from instruments where delisted_date is not null")
    total = _scalar(session, "select count(*) from instruments")
    master = _scalar(session, "select count(*) from security_master")
    delisting_events = _scalar(session, "select count(*) from delisting_event")
    report.checks.append(
        Check(
            name="survivorship_control",
            passed=bool(delisted) and bool(master),
            observed=(
                f"{total} instruments, {delisted} delisted; security_master={master}, "
                f"delisting_event={delisting_events}"
            ),
            requirement=(
                "A universe containing delisted securities, keyed on a permanent "
                "security_id, with delisting returns available."
            ),
            blocker=(
                None
                if (delisted and master)
                else (
                    f"survivor-only universe: {delisted} of {total} instruments are delisted "
                    f"and the survivorship-clean tables are empty"
                )
            ),
        )
    )

    # -- 2. PIT fundamentals -------------------------------------------------
    fund_dates = _scalar(session, "select count(distinct as_of_date) from company_fundamentals")
    fund_span = _scalar(
        session,
        "select coalesce(max(as_of_date)::text,'n/a') || ' .. ' || "
        "coalesce(min(as_of_date)::text,'n/a') from company_fundamentals",
    )
    fund_ok = (fund_dates or 0) >= MIN_PIT_OBSERVATION_DATES
    report.checks.append(
        Check(
            name="pit_fundamentals",
            passed=fund_ok,
            observed=f"{fund_dates} distinct as_of dates ({fund_span})",
            requirement=(
                f"At least {MIN_PIT_OBSERVATION_DATES} distinct as-of dates, i.e. a vintage "
                f"time series rather than a snapshot."
            ),
            blocker=(
                None
                if fund_ok
                else f"fundamentals are a snapshot, not a vintage series ({fund_dates} as-of dates)"
            ),
        )
    )

    # -- 3. PIT earnings -----------------------------------------------------
    obs_dates = _scalar(
        session, "select count(distinct observed_at::date) from earnings_observations"
    )
    ev_rows = _scalar(session, "select count(*) from earnings_observations")
    ev_span = _scalar(
        session,
        "select coalesce(min(earnings_date)::text,'n/a') || ' .. ' || "
        "coalesce(max(earnings_date)::text,'n/a') from earnings_observations",
    )
    earn_ok = (obs_dates or 0) >= MIN_PIT_OBSERVATION_DATES
    report.checks.append(
        Check(
            name="pit_earnings",
            passed=earn_ok,
            observed=(
                f"{ev_rows} observations spanning {ev_span}, but only {obs_dates} distinct "
                f"observed_at dates"
            ),
            requirement=(
                "Earnings observed progressively, so a historical as-of sees only what was "
                "knowable then."
            ),
            blocker=(
                None
                if earn_ok
                else (
                    f"earnings history was witnessed in {obs_dates} ingest(s): using it at a "
                    f"historical as-of is lookahead"
                )
            ),
        )
    )

    # -- 4. PIT classification ----------------------------------------------
    hist_class = _scalar(session, "select count(*) from historical_classification")
    report.checks.append(
        Check(
            name="pit_classification",
            passed=bool(hist_class),
            observed=f"historical_classification={hist_class}",
            requirement="Sector/industry as classified AT the historical date.",
            blocker=(
                None
                if hist_class
                else "sector classification is current-only, applied retroactively"
            ),
        )
    )

    # -- 5. signal reconstructability ---------------------------------------
    # A horizon is reconstructable only if EVERY directional group voting at it
    # is price-derived. Derived from the product's own horizon constants so the
    # two cannot drift apart.
    non_reconstructable: dict[str, list[str]] = {}
    for hz in HORIZONS:
        blocked: list[str] = []
        if hz in VALUATION_HORIZONS:
            blocked.append("valuation_level (company_fundamentals)")
        if hz in DELIVERY_HORIZONS:
            blocked.append("earnings_delivery (earnings_observations)")
        if hz in QUALITY_VOTING_HORIZONS:
            blocked.append("company_quality (company_fundamentals)")
        if blocked:
            non_reconstructable[hz] = blocked

    report.blocked_horizons = non_reconstructable
    report.reconstructable_horizons = tuple(h for h in HORIZONS if h not in non_reconstructable)
    all_reconstructable = not non_reconstructable
    report.checks.append(
        Check(
            name="signal_reconstructability",
            passed=all_reconstructable and fund_ok and earn_ok,
            observed=(
                f"reconstructable at {list(report.reconstructable_horizons) or 'no horizon'}; "
                f"blocked at {sorted(non_reconstructable)}"
            ),
            requirement=(
                "Every directional evidence group voting at a horizon must be reconstructable "
                "point-in-time."
            ),
            blocker=(
                None
                if (all_reconstructable and fund_ok and earn_ok)
                else (
                    "the deterministic security view cannot be reconstructed at "
                    f"{sorted(non_reconstructable)} — it depends on fundamentals and earnings "
                    "that have no history"
                )
            ),
        )
    )

    # -- 6. price depth (informational, but a real floor) --------------------
    deep = _scalar(
        session,
        "select count(*) from (select instrument_id from daily_prices "
        "group by 1 having count(*) >= 1260) t",
    )
    span = _scalar(
        session,
        "select coalesce(min(price_date)::text,'n/a') || ' .. ' || "
        "coalesce(max(price_date)::text,'n/a') from daily_prices",
    )
    report.checks.append(
        Check(
            name="price_history_depth",
            passed=bool(deep and deep >= 100),
            observed=f"{deep} instruments with >=5y of sessions; span {span}",
            requirement="At least 100 securities with five years of daily prices.",
            blocker=None if (deep and deep >= 100) else "insufficient price history depth",
        )
    )

    return report
