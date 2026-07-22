"""Intelligence models: independent packages consuming ONLY the feature
store and the Historical Research Engine (architecture Phase 9 shape).
Models: Interest Rate Sensitivity, Sector Rotation, Momentum Exhaustion,
Valuation, Earnings Behavior, Macro Regime, Relative Strength."""

from mip.models.analogues import HistoricalAnalogueModel
from mip.models.base import (
    Z_CLIP,
    IntelligenceModel,
    ModelScore,
    RegimeEvidence,
    combine_evidence,
    confidence_from_evidence,
    score_from_z,
)
from mip.models.earnings import EarningsBehaviorModel
from mip.models.evidence import (
    EvidenceNormalizer,
    NormalizedEvidence,
    normalize_score,
    normalize_scores,
)
from mip.models.macro import MacroRegimeModel
from mip.models.momentum import MomentumExhaustionModel
from mip.models.rates import InterestRateModel
from mip.models.relative import RelativeStrengthModel
from mip.models.sector import SectorRotationModel
from mip.models.valuation import ValuationModel

# The registry consumers iterate to gather evidence without naming models.
ALL_MODELS = (
    InterestRateModel,
    SectorRotationModel,
    MomentumExhaustionModel,
    ValuationModel,
    EarningsBehaviorModel,
    MacroRegimeModel,
    RelativeStrengthModel,
    HistoricalAnalogueModel,
)

__all__ = [
    "HistoricalAnalogueModel",
    "ALL_MODELS",
    "Z_CLIP",
    "combine_evidence",
    "confidence_from_evidence",
    "score_from_z",
    "EarningsBehaviorModel",
    "EvidenceNormalizer",
    "IntelligenceModel",
    "InterestRateModel",
    "MacroRegimeModel",
    "ModelScore",
    "MomentumExhaustionModel",
    "NormalizedEvidence",
    "RegimeEvidence",
    "RelativeStrengthModel",
    "SectorRotationModel",
    "ValuationModel",
    "normalize_score",
    "normalize_scores",
]
