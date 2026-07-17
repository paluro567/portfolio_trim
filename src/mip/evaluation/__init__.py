"""Prediction Archive & Outcome Evaluation — measurement only.

This layer sits AFTER the reporting layer: it archives the exact
predictions the platform publishes (immutably), matches them against
realized market outcomes once each horizon expires, and measures
accuracy, calibration, model usefulness, horizon reliability, and regime
dependence. It never tunes, recalibrates, or feeds anything back into
the models.
"""

from mip.evaluation.analytics import (
    calibration_table,
    evaluated_row,
    horizon_analytics,
    model_analytics,
    trim_analytics,
)
from mip.evaluation.archive import ArchiveResult, PredictionArchiver, prediction_row
from mip.evaluation.outcomes import MaturitySummary, OutcomeEvaluator, compute_outcome
from mip.evaluation.regimes import RegimeClassifier, regime_analytics

__all__ = [
    "ArchiveResult",
    "MaturitySummary",
    "OutcomeEvaluator",
    "PredictionArchiver",
    "RegimeClassifier",
    "calibration_table",
    "compute_outcome",
    "evaluated_row",
    "horizon_analytics",
    "model_analytics",
    "prediction_row",
    "regime_analytics",
    "trim_analytics",
]
