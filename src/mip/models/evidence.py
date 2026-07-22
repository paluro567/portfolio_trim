"""Evidence Normalization Framework.

The seam between the intelligence models and the future Decision Engine:
every model already emits ModelScore objects with shared statistical
semantics; this layer converts them into ONE NormalizedEvidence contract so
the Decision Engine never needs to know how any individual model works.

Nothing is recomputed — every field is either carried through or derived by
pure algebra from statistics the models already produced:

- expected_volatility: per study, se·sqrt(n_eff) reconstructs the
  recency-weighted standard deviation of the conditional forward returns
  EXACTLY (the model stored se = (std/sqrt(kish))·sqrt(inflation) and
  n_eff = kish/inflation, so the overlap inflation cancels); studies are
  aggregated with the same 1/se² precision weights the models use.
- downside_risk / upside_potential: the one-sigma band around the expected
  conditional return (a documented normal approximation, not a new model).
- evidence_strength: |score - 50| / 50 in [0, 1] — the evidence-implied
  distance from "no edge", monotone in |z_clipped|.
- contradictory_evidence: 1 - agreement in [0, 1] — the precision-weighted
  share of studies dissenting from the combined direction. Values above 0.5
  are real: a high-magnitude minority study can pull the combined effect
  against the precision majority, and the Decision Engine should see that.
- supporting/opposing reasons: the RegimeEvidence studies carried on the
  score, serialized WITHOUT loss (including description and feature, which
  RegimeEvidence.to_dict omits for CLI brevity).

Neutral scores normalize to explicitly neutral evidence (strength 0,
confidence 0, all expectation fields None) — honest absence survives
normalization. ScoreDiagnostics pass through verbatim.
"""

import abc
import math
from dataclasses import asdict, dataclass
from datetime import date

from mip.core.exceptions import ConfigurationError
from mip.models.base import ModelScore, RegimeEvidence, ScoreDiagnostics

# Every registered intelligence model. A ModelScore from any other name is
# rejected: new models must be added here deliberately (the adapter seam).
KNOWN_MODELS = (
    "interest_rate_sensitivity",
    "sector_rotation",
    "momentum_exhaustion",
    "valuation",
    "earnings_behavior",
    "macro_regime",
    "relative_strength",
    "historical_analogues",
)

HORIZONS = ("1w", "2w", "1m", "3m", "6m", "1y")


def _reason_to_dict(evidence: RegimeEvidence) -> dict:
    """Lossless RegimeEvidence serialization. RegimeEvidence.to_dict rounds
    values and drops description/feature/se for CLI brevity — the evidence
    contract keeps full precision and every field."""
    return {
        "label": evidence.label,
        "description": evidence.description,
        "feature": evidence.feature,
        "n": evidence.n,
        "n_eff": evidence.n_eff,
        "mean": evidence.mean,
        "hit_rate": evidence.hit_rate,
        "baseline_mean": evidence.baseline_mean,
        "excess": evidence.excess,
        "se": evidence.se,
        "first_event": evidence.first_event.isoformat(),
        "last_event": evidence.last_event.isoformat(),
    }


def _reason_from_dict(payload: dict) -> RegimeEvidence:
    return RegimeEvidence(
        label=payload["label"],
        description=payload["description"],
        feature=payload["feature"],
        n=payload["n"],
        n_eff=payload["n_eff"],
        mean=payload["mean"],
        hit_rate=payload["hit_rate"],
        baseline_mean=payload["baseline_mean"],
        excess=payload["excess"],
        se=payload["se"],
        first_event=date.fromisoformat(payload["first_event"]),
        last_event=date.fromisoformat(payload["last_event"]),
    )


@dataclass(frozen=True)
class NormalizedEvidence:
    """The model-agnostic evidence contract consumed by the Decision Engine."""

    model_name: str
    model_version: int
    symbol: str
    as_of: date
    horizon: str
    horizon_sessions: int
    score: float  # 0-100, 50 = no edge (unchanged convention)
    neutral: bool  # True = honest absence of evidence
    expected_return: float | None  # conditional forward return
    baseline_return: float | None  # unconditional forward return
    expected_excess_return: float | None
    confidence: float  # 0-1
    effective_sample_size: float  # overlap-adjusted (max per-study n_eff)
    sample_size: int  # raw distinct event dates
    historical_hit_rate: float | None
    expected_volatility: float | None  # precision-weighted conditional stdev
    downside_risk: float | None  # expected_return - expected_volatility
    upside_potential: float | None  # expected_return + expected_volatility
    evidence_strength: float  # |score-50|/50 in [0, 1]
    contradictory_evidence: float  # 1 - agreement in [0, 1]; > 0.5 = majority dissents
    supporting_reasons: tuple[RegimeEvidence, ...]
    opposing_reasons: tuple[RegimeEvidence, ...]
    active_regimes: tuple[str, ...]
    explanation: str
    diagnostics: ScoreDiagnostics | None
    context: dict | None = None  # preserved verbatim; None on neutral

    def to_dict(self) -> dict:
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "symbol": self.symbol,
            "as_of": self.as_of.isoformat(),
            "horizon": self.horizon,
            "horizon_sessions": self.horizon_sessions,
            "score": self.score,
            "neutral": self.neutral,
            "expected_return": self.expected_return,
            "baseline_return": self.baseline_return,
            "expected_excess_return": self.expected_excess_return,
            "confidence": self.confidence,
            "effective_sample_size": self.effective_sample_size,
            "sample_size": self.sample_size,
            "historical_hit_rate": self.historical_hit_rate,
            "expected_volatility": self.expected_volatility,
            "downside_risk": self.downside_risk,
            "upside_potential": self.upside_potential,
            "evidence_strength": self.evidence_strength,
            "contradictory_evidence": self.contradictory_evidence,
            "supporting_reasons": [_reason_to_dict(r) for r in self.supporting_reasons],
            "opposing_reasons": [_reason_to_dict(r) for r in self.opposing_reasons],
            "active_regimes": list(self.active_regimes),
            "explanation": self.explanation,
            # asdict, not ScoreDiagnostics.to_dict: that one rounds for CLI
            # display and the evidence contract must keep full precision
            "diagnostics": asdict(self.diagnostics) if self.diagnostics else None,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "NormalizedEvidence":
        diagnostics = None
        if payload["diagnostics"] is not None:
            diagnostics = ScoreDiagnostics(**payload["diagnostics"])
        return cls(
            model_name=payload["model_name"],
            model_version=payload["model_version"],
            symbol=payload["symbol"],
            as_of=date.fromisoformat(payload["as_of"]),
            horizon=payload["horizon"],
            horizon_sessions=payload["horizon_sessions"],
            score=payload["score"],
            neutral=payload["neutral"],
            expected_return=payload["expected_return"],
            baseline_return=payload["baseline_return"],
            expected_excess_return=payload["expected_excess_return"],
            confidence=payload["confidence"],
            effective_sample_size=payload["effective_sample_size"],
            sample_size=payload["sample_size"],
            historical_hit_rate=payload["historical_hit_rate"],
            expected_volatility=payload["expected_volatility"],
            downside_risk=payload["downside_risk"],
            upside_potential=payload["upside_potential"],
            evidence_strength=payload["evidence_strength"],
            contradictory_evidence=payload["contradictory_evidence"],
            supporting_reasons=tuple(_reason_from_dict(r) for r in payload["supporting_reasons"]),
            opposing_reasons=tuple(_reason_from_dict(r) for r in payload["opposing_reasons"]),
            active_regimes=tuple(payload["active_regimes"]),
            explanation=payload["explanation"],
            diagnostics=diagnostics,
            context=payload.get("context"),
        )


class EvidenceNormalizer(abc.ABC):
    """Converts one model's ModelScore into the shared evidence contract."""

    @abc.abstractmethod
    def normalize(self, score: ModelScore) -> NormalizedEvidence: ...


class DefaultNormalizer(EvidenceNormalizer):
    """The standard mapping. Every current model emits ModelScore objects
    with identical statistical semantics (shared models.base framework), so
    one normalizer serves all seven; the adapter registry below is the seam
    where a future model with different semantics would plug in its own."""

    def normalize(self, score: ModelScore) -> NormalizedEvidence:
        neutral = score.expected_return is None
        reasons = tuple(score.strongest_supporting_regimes) + tuple(
            score.strongest_negative_regimes
        )
        volatility = self._expected_volatility(reasons) if not neutral else None
        diagnostics = score.diagnostics
        return NormalizedEvidence(
            model_name=score.model,
            model_version=score.model_version,
            symbol=score.symbol,
            as_of=score.as_of,
            horizon=score.horizon,
            horizon_sessions=score.horizon_sessions,
            score=score.score,
            neutral=neutral,
            expected_return=score.expected_return,
            baseline_return=score.baseline_return,
            expected_excess_return=score.excess_return,
            confidence=score.confidence,
            effective_sample_size=(diagnostics.max_n_eff if diagnostics else 0.0),
            sample_size=score.sample_size,
            historical_hit_rate=score.historical_hit_rate,
            expected_volatility=volatility,
            downside_risk=(
                score.expected_return - volatility
                if not neutral and volatility is not None
                else None
            ),
            upside_potential=(
                score.expected_return + volatility
                if not neutral and volatility is not None
                else None
            ),
            evidence_strength=abs(score.score - 50.0) / 50.0,
            contradictory_evidence=(1.0 - diagnostics.agreement if diagnostics else 0.0),
            supporting_reasons=tuple(score.strongest_supporting_regimes),
            opposing_reasons=tuple(score.strongest_negative_regimes),
            active_regimes=tuple(score.active_regimes),
            explanation=score.explanation,
            diagnostics=diagnostics,
            context=score.context,
        )

    @staticmethod
    def _expected_volatility(reasons: tuple[RegimeEvidence, ...]) -> float | None:
        """Precision-weighted conditional stdev, reconstructed per study as
        se·sqrt(n_eff) (exact: the overlap inflation cancels — see module
        docstring). Uses the studies carried on the score."""
        usable = [r for r in reasons if r.se > 0 and r.n_eff > 0]
        if not usable:
            return None
        weights = [1.0 / r.se**2 for r in usable]
        stds = [r.se * math.sqrt(r.n_eff) for r in usable]
        return sum(w * s for w, s in zip(weights, stds, strict=True)) / sum(weights)


# -- adapters: model name -> normalizer (the extension seam) ---------------------

MODEL_NORMALIZERS: dict[str, EvidenceNormalizer] = {
    name: DefaultNormalizer() for name in KNOWN_MODELS
}


def validate_evidence(evidence: NormalizedEvidence) -> None:
    """Contract checks. Violations are ConfigurationErrors: they mean a
    model or normalizer broke the shared semantics, never bad market data."""
    checks: list[tuple[bool, str]] = [
        (evidence.model_name in KNOWN_MODELS, f"unknown model {evidence.model_name!r}"),
        (evidence.horizon in HORIZONS, f"unknown horizon {evidence.horizon!r}"),
        (0.0 <= evidence.score <= 100.0, f"score out of range: {evidence.score}"),
        (0.0 <= evidence.confidence <= 1.0, f"confidence out of range: {evidence.confidence}"),
        (
            0.0 <= evidence.evidence_strength <= 1.0,
            f"evidence_strength out of range: {evidence.evidence_strength}",
        ),
        (
            0.0 <= evidence.contradictory_evidence <= 1.0,
            f"contradictory_evidence out of range: {evidence.contradictory_evidence}",
        ),
        (evidence.effective_sample_size >= 0.0, "negative effective sample size"),
        (evidence.sample_size >= 0, "negative sample size"),
    ]
    if evidence.neutral:
        checks += [
            (evidence.expected_return is None, "neutral evidence carries expected_return"),
            (evidence.confidence == 0.0, "neutral evidence carries confidence"),
            (evidence.evidence_strength == 0.0, "neutral evidence carries strength"),
        ]
    else:
        checks += [
            (evidence.expected_return is not None, "evidence lacks expected_return"),
            (evidence.expected_excess_return is not None, "evidence lacks excess return"),
            (evidence.diagnostics is not None, "evidence lacks diagnostics"),
            (
                evidence.historical_hit_rate is None or 0.0 <= evidence.historical_hit_rate <= 1.0,
                f"hit rate out of range: {evidence.historical_hit_rate}",
            ),
            (
                evidence.expected_volatility is None or evidence.expected_volatility >= 0.0,
                "negative expected volatility",
            ),
            (
                evidence.downside_risk is None
                or evidence.upside_potential is None
                or evidence.downside_risk
                <= (evidence.expected_return or 0.0)
                <= evidence.upside_potential,
                "expected return outside its own risk band",
            ),
        ]
    for ok, message in checks:
        if not ok:
            raise ConfigurationError(f"invalid normalized evidence: {message}")


def normalize_score(score: ModelScore) -> NormalizedEvidence:
    """Dispatch one ModelScore through its model's adapter and validate."""
    normalizer = MODEL_NORMALIZERS.get(score.model)
    if normalizer is None:
        raise ConfigurationError(
            f"no evidence normalizer registered for model {score.model!r}; "
            f"known models: {sorted(MODEL_NORMALIZERS)}"
        )
    evidence = normalizer.normalize(score)
    validate_evidence(evidence)
    return evidence


def normalize_scores(scores: list[ModelScore]) -> list[NormalizedEvidence]:
    """Normalize a batch (e.g. one model's six horizons, or many models'
    outputs for one symbol) preserving order."""
    return [normalize_score(score) for score in scores]
