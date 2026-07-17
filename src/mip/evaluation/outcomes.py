"""Outcome evaluation: match archived predictions to realized closes.

Matching rule (declared in the phase contract): entry session = last
trading session <= as_of, entry price = that session's close (what the
models knew); exit session = the horizon_sessions-th session strictly
after entry. A prediction matures when both closes exist; until then it
stays visibly pending. All measures compare against the ARCHIVED
baseline, so prediction_error = actual_excess - expected_excess is
identical to actual_return - expected_return.

Outcomes are derived data: the guarded upsert makes re-evaluation
idempotent, and prediction rows themselves are never touched.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from mip.repositories.predictions import PredictionRepository


def compute_outcome(
    entry_price: Decimal | float,
    exit_price: Decimal | float,
    baseline_return: float | None,
    expected_excess: float | None,
) -> dict[str, Any]:
    """Pure outcome arithmetic for one matured prediction."""
    actual_return = float(exit_price) / float(entry_price) - 1.0
    actual_excess = actual_return - baseline_return if baseline_return is not None else None
    error = None
    direction = None
    outperformed = None
    underperformed = None
    if actual_excess is not None and expected_excess is not None:
        error = actual_excess - expected_excess
        outperformed = actual_excess > expected_excess
        underperformed = actual_excess < expected_excess
        if expected_excess != 0.0:
            direction = (expected_excess > 0.0) == (actual_excess > 0.0)
    return {
        "actual_return": actual_return,
        "actual_excess_return": actual_excess,
        "prediction_error": error,
        "absolute_error": abs(error) if error is not None else None,
        "direction_correct": direction,
        "outperformed": outperformed,
        "underperformed": underperformed,
    }


@dataclass(frozen=True)
class MaturitySummary:
    evaluated: int  # newly evaluated (or corrected after a price restatement)
    unchanged: int  # matured, re-checked, byte-identical
    pending: int  # horizon not yet expired (or prices not yet available)

    def to_dict(self) -> dict:
        return {
            "evaluated": self.evaluated,
            "unchanged": self.unchanged,
            "pending": self.pending,
        }


class OutcomeEvaluator:
    def __init__(self, session: Session) -> None:
        self._repo = PredictionRepository(session)

    def evaluate_matured(self) -> MaturitySummary:
        """Sweeps EVERY archived prediction: immature ones stay pending,
        matured ones get their outcome written (or re-verified — a price
        restatement corrects the derived outcome on the next run)."""
        evaluated = unchanged = pending = 0
        for prediction, _symbol in self._repo.all_predictions():
            entry_date = self._repo.entry_session(prediction.as_of)
            if entry_date is None:
                pending += 1
                continue
            entry_price = self._repo.close_on(prediction.instrument_id, entry_date)
            exit_date = self._repo.session_after(entry_date, prediction.horizon_sessions)
            exit_price = (
                self._repo.close_on(prediction.instrument_id, exit_date) if exit_date else None
            )
            if entry_price is None or exit_price is None:
                pending += 1  # not matured (or instrument not priced on session)
                continue
            values = compute_outcome(
                entry_price,
                exit_price,
                prediction.baseline_return,
                prediction.expected_excess_return,
            )
            values.update(
                entry_date=entry_date,
                exit_date=exit_date,
                entry_price=entry_price,
                exit_price=exit_price,
            )
            if self._repo.upsert_outcome(prediction.id, values):
                evaluated += 1
            else:
                unchanged += 1
        return MaturitySummary(evaluated=evaluated, unchanged=unchanged, pending=pending)
