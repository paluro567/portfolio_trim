"""Prediction archiving: the exact published TrimAssessment, immutably.

Every archived row is permanent historical evidence. Immutability is
enforced at the repository seam (INSERT-only, ON CONFLICT DO NOTHING on
the natural key) — re-archiving the same (instrument, portfolio context,
as_of, horizon, engine version) can never change what was stored first.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from mip.engine.trim import TrimAssessment
from mip.repositories.predictions import PredictionRepository


def prediction_row(assessment: TrimAssessment, instrument_id: int) -> dict[str, Any]:
    """Map one TrimAssessment to its archive row — values verbatim."""
    expected = assessment.expected_return
    excess = assessment.expected_excess_return
    return {
        "instrument_id": instrument_id,
        "portfolio_key": assessment.portfolio_name or "",
        "as_of": assessment.as_of,
        "horizon": assessment.horizon,
        "horizon_sessions": assessment.horizon_sessions,
        "trim_score": assessment.trim_score,
        "evidence_trim_score": assessment.evidence_trim_score,
        "portfolio_adjustment": assessment.portfolio_adjustment,
        "confidence": assessment.confidence,
        "recommendation_label": assessment.recommendation_label,
        "expected_return": expected,
        "expected_excess_return": excess,
        "baseline_return": (expected - excess if None not in (expected, excess) else None),
        "data_quality_label": assessment.data_quality_label,
        "contradictory_evidence": assessment.contradictory_evidence,
        "effective_sample_size": assessment.effective_sample_size,
        "participating_models": list(assessment.participating_models),
        "primary_trim_drivers": list(assessment.primary_trim_drivers),
        "primary_hold_strengths": list(assessment.primary_hold_strengths),
        "model_contributions": [c.to_dict() for c in assessment.model_contributions],
        "evidence": {
            "neutral_models": list(assessment.neutral_models),
            "omitted_models": list(assessment.omitted_models),
            "evidence_strength": assessment.evidence_strength,
            "strongest_supporting_reason": assessment.strongest_supporting_reason,
            "strongest_opposing_reason": assessment.strongest_opposing_reason,
            "concentration_flags": list(assessment.concentration_flags),
            "limitations": list(assessment.limitations),
            "context": assessment.context,
        },
        "trim_engine_version": assessment.engine_version,
    }


@dataclass(frozen=True)
class ArchiveResult:
    inserted: int
    skipped: int  # already archived (immutable — left exactly as first written)


class PredictionArchiver:
    """Archives assessments; consumes only TrimAssessment objects."""

    def __init__(self, session: Session) -> None:
        self._repo = PredictionRepository(session)

    def archive(self, assessments: Iterable[TrimAssessment]) -> ArchiveResult:
        instrument_ids: dict[str, int] = {}
        rows = []
        for assessment in assessments:
            symbol = assessment.symbol
            if symbol not in instrument_ids:
                instrument_ids[symbol] = self._repo.instrument_id(symbol)
            rows.append(prediction_row(assessment, instrument_ids[symbol]))
        inserted = self._repo.insert_predictions(rows)
        return ArchiveResult(inserted=inserted, skipped=len(rows) - inserted)
