"""Centralized label-observability rule: the per-horizon embargo.

THE rule, used by every validation path (never duplicated): a historical
observation dated t may contribute a forward outcome at horizon H to a
scoring date T only if its complete outcome window was observable by T.

Platform timing semantics (documented, deliberate): scores are computed
AFTER the close of the scoring session (the daily update runs post-close
and T's own close is a model input), so an outcome window ending exactly
ON T's session is observable. Eligibility on the trading calendar:

    position(t) + H <= position(T)          [end-on-T allowed]

Everything is expressed in trading sessions of the actual instrument
price series — weekends, holidays, sparse histories, and delistings are
handled by construction because positions come from real traded dates.

`min_gap_sessions` in AnalogueConfig serves a SEPARATE documented
purpose (near-duplicate suppression between selected analogues) and is
not a substitute for this embargo.
"""

from bisect import bisect_right
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select

OBSERVATION_AFTER_CUTOFF = "observation_after_scoring_cutoff"
CROSSES_SCORING_DATE = "outcome_crosses_scoring_date"
OUTCOME_UNAVAILABLE = "outcome_unavailable"
MISSING_CALENDAR = "missing_calendar_mapping"
ELIGIBLE = "eligible"


def _position(sessions: Sequence[date], day: date) -> int | None:
    """Index of the last session <= day; None when day precedes history."""
    index = bisect_right(sessions, day)
    return index - 1 if index else None


def label_observable(
    observation_date: date,
    scoring_date: date,
    horizon_sessions: int,
    sessions: Sequence[date],
) -> tuple[bool, str]:
    """(eligible, reason). `sessions` must be the ascending traded dates
    of the instrument whose outcome is being measured."""
    if observation_date > scoring_date:
        return False, OBSERVATION_AFTER_CUTOFF
    pos_t = _position(sessions, observation_date)
    if pos_t is None or sessions[pos_t] != observation_date:
        return False, MISSING_CALENDAR
    pos_scoring = _position(sessions, scoring_date)
    if pos_scoring is None:
        return False, MISSING_CALENDAR
    end = pos_t + horizon_sessions
    if end >= len(sessions):
        return False, OUTCOME_UNAVAILABLE
    if end > pos_scoring:
        return False, CROSSES_SCORING_DATE
    return True, ELIGIBLE


def eligible_mask(
    observation_dates: Sequence[date],
    scoring_date: date,
    horizon_sessions: int,
    sessions: Sequence[date],
) -> tuple[list[bool], Counter]:
    """Vectorized form: per-observation eligibility plus a reason count."""
    flags: list[bool] = []
    reasons: Counter = Counter()
    for observation in observation_dates:
        ok, reason = label_observable(observation, scoring_date, horizon_sessions, sessions)
        flags.append(ok)
        reasons[reason] += 1
    return flags, reasons


@dataclass
class ObservabilityDiagnostics:
    """Leakage diagnostics for one analogue result — the aggregate across
    a validation run must show violations == 0."""

    symbol: str
    as_of: date
    analogues: int
    horizons: dict[str, dict[str, int]] = field(default_factory=dict)
    violations: int = 0

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "as_of": self.as_of.isoformat(),
            "analogues": self.analogues,
            "horizons": self.horizons,
            "violations": self.violations,
        }


def instrument_sessions(session, symbol: str) -> list[date]:
    """The instrument's traded dates with usable adjusted closes —
    deterministic ascending order."""
    from mip.domain.models import DailyPrice, Instrument

    return list(
        session.execute(
            select(DailyPrice.price_date)
            .join(Instrument, Instrument.id == DailyPrice.instrument_id)
            .where(Instrument.symbol == symbol.strip().upper())
            .where(DailyPrice.adj_close.is_not(None))
            .order_by(DailyPrice.price_date)
        ).scalars()
    )


def verify_analogue_observability(session, result, strict: bool = False):
    """Reconcile an AnalogueResult against the embargo: for every horizon,
    the outcomes actually USED must not exceed the OBSERVABLE analogues.
    strict=True raises on any violation (the walk-forward invariant)."""
    from mip.research.analogues import HORIZONS

    sessions = instrument_sessions(session, result.symbol)
    diagnostics = ObservabilityDiagnostics(
        symbol=result.symbol, as_of=result.as_of, analogues=len(result.analogues)
    )
    analogue_dates = [a.date for a in result.analogues]
    for label, horizon_sessions in HORIZONS.items():
        flags, reasons = eligible_mask(analogue_dates, result.as_of, horizon_sessions, sessions)
        outcome = result.outcomes.get(label)
        used = outcome.n if outcome is not None else 0
        observable = sum(flags)
        diagnostics.horizons[label] = {
            "used": used,
            "observable": observable,
            "embargoed": reasons[CROSSES_SCORING_DATE],
            "unavailable": reasons[OUTCOME_UNAVAILABLE] + reasons[MISSING_CALENDAR],
        }
        if used > observable:
            diagnostics.violations += used - observable
    if strict:
        assert diagnostics.violations == 0, (
            f"leakage: {result.symbol}@{result.as_of} used unobservable outcomes "
            f"{diagnostics.to_dict()}"
        )
    return diagnostics
