"""Evidence Attribution Engine: the exact accounting of a TrimAssessment.

Every AttributionReport decomposes the final trim score into named line
items that sum EXACTLY back to it:

    trim_score = 50 (neutral baseline)
               + sum of per-model evidence contributions   (= E - 50)
               + concentration_adjustment
               + diversification_adjustment                (together = A)
               + clip_residual                             (usually 0)

Per-model contributions reuse the decision engine's own exact linear
decomposition: each participating model's signed_contribution sums to the
combined expected excess return, so its share of the evidence deviation is

    contribution_m = (E - 50) * signed_contribution_m / combined_excess

The portfolio overlay splits into its concentration part (weight term plus
any positive risk-share term) and diversification part (negative
risk-share term); when the overlay was capped, both parts are scaled by
the same factor so they still sum to the applied adjustment. Nothing is
invented and no statistic is recomputed — every number here is a ratio or
sum of fields already carried on TrimAssessment and DecisionEvidence.

Isolation: this layer consumes ONLY TrimAssessment and DecisionEvidence —
never intelligence models, features, research, providers, repositories,
or portfolio internals.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from mip.core.exceptions import ConfigurationError
from mip.engine.evidence import DecisionEvidence, DecisionEvidenceEngine
from mip.engine.trim import TrimAssessment, TrimConfig, assess_symbol

ENGINE_VERSION = 1
NEUTRAL_BASELINE = 50.0


@dataclass(frozen=True)
class EvidenceContribution:
    """One model's exact share of the trim score, in score points."""

    model_name: str
    contribution: float  # trim points; positive raises the trim score
    direction: str  # raises_trim | lowers_trim | neutral
    confidence: float  # the model's own confidence, verbatim
    evidence_strength: float  # |model score - 50| / 50, from the model's score
    expected_excess_return: float  # the model's effect, verbatim

    def to_dict(self) -> dict:
        return {
            "model_name": self.model_name,
            "contribution": self.contribution,
            "direction": self.direction,
            "confidence": self.confidence,
            "evidence_strength": self.evidence_strength,
            "expected_excess_return": self.expected_excess_return,
        }


@dataclass(frozen=True)
class PortfolioContributions:
    """The overlay split so that concentration + diversification equals the
    applied portfolio adjustment exactly (cap allocated proportionally)."""

    concentration_adjustment: float
    diversification_adjustment: float
    portfolio_overlay_contribution: float  # == TrimAssessment.portfolio_adjustment

    def to_dict(self) -> dict:
        return {
            "concentration_adjustment": self.concentration_adjustment,
            "diversification_adjustment": self.diversification_adjustment,
            "portfolio_overlay_contribution": self.portfolio_overlay_contribution,
        }


@dataclass(frozen=True)
class RankedContribution:
    """One line of the decomposition, ranked by magnitude, with the running
    total from the neutral baseline (the last cumulative is the trim score)."""

    name: str
    kind: str  # model | portfolio | clip
    contribution: float
    cumulative: float

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "contribution": self.contribution,
            "cumulative": self.cumulative,
        }


@dataclass(frozen=True)
class AttributionReport:
    """The complete, exact accounting of one trim assessment — sufficient
    for a future report generator to explain it without touching anything
    below this layer."""

    # identity
    symbol: str
    horizon: str
    as_of: date
    # overall
    trim_score: float
    confidence: float
    # decomposition
    neutral_baseline: float
    evidence_contributions: tuple[EvidenceContribution, ...]
    portfolio_contributions: PortfolioContributions
    clip_residual: float
    # summary
    strongest_positive_contributor: str | None  # pushes the score up most
    strongest_negative_contributor: str | None  # pushes the score down most
    largest_uncertainty: dict | None  # least precise participant, by se
    dominant_historical_regime: dict | None  # verbatim regime reason
    dominant_portfolio_driver: str | None
    # diagnostics
    contribution_ranking: tuple[RankedContribution, ...]
    omitted_models: tuple[str, ...]
    neutral_models: tuple[str, ...]
    contradictory_evidence: float
    traceability: dict

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "horizon": self.horizon,
            "as_of": self.as_of.isoformat(),
            "trim_score": self.trim_score,
            "confidence": self.confidence,
            "neutral_baseline": self.neutral_baseline,
            "evidence_contributions": [c.to_dict() for c in self.evidence_contributions],
            "portfolio_contributions": self.portfolio_contributions.to_dict(),
            "clip_residual": self.clip_residual,
            "strongest_positive_contributor": self.strongest_positive_contributor,
            "strongest_negative_contributor": self.strongest_negative_contributor,
            "largest_uncertainty": self.largest_uncertainty,
            "dominant_historical_regime": self.dominant_historical_regime,
            "dominant_portfolio_driver": self.dominant_portfolio_driver,
            "contribution_ranking": [r.to_dict() for r in self.contribution_ranking],
            "omitted_models": list(self.omitted_models),
            "neutral_models": list(self.neutral_models),
            "contradictory_evidence": self.contradictory_evidence,
            "traceability": self.traceability,
        }


def _direction(contribution: float) -> str:
    if contribution > 0:
        return "raises_trim"
    if contribution < 0:
        return "lowers_trim"
    return "neutral"


def _split_overlay(assessment: TrimAssessment) -> PortfolioContributions:
    weight_term = assessment.diagnostics.weight_term
    risk_term = assessment.diagnostics.risk_term
    applied = assessment.portfolio_adjustment
    raw = weight_term + risk_term
    scale = applied / raw if raw else 1.0
    concentration = (weight_term + max(risk_term, 0.0)) * scale
    diversification = min(risk_term, 0.0) * scale
    return PortfolioContributions(
        concentration_adjustment=concentration,
        diversification_adjustment=diversification,
        portfolio_overlay_contribution=applied,
    )


def _portfolio_driver(assessment: TrimAssessment) -> str | None:
    if assessment.portfolio_weight is None:
        return None
    weight_term = assessment.diagnostics.weight_term
    risk_term = assessment.diagnostics.risk_term
    if weight_term == 0.0 and risk_term == 0.0:
        return "none"
    if weight_term >= abs(risk_term):
        return "weight_concentration"
    return "risk_concentration" if risk_term > 0 else "diversification_benefit"


def attribute(assessment: TrimAssessment, evidence: DecisionEvidence) -> AttributionReport:
    """Pure: one (TrimAssessment, DecisionEvidence) pair in, its exact
    accounting out. The pair must describe the same symbol, horizon, and
    combination — enforced, so no report can mix lineages."""
    if (
        assessment.symbol != evidence.symbol
        or assessment.horizon != evidence.horizon
        or assessment.as_of != evidence.as_of
        or assessment.diagnostics.source_combined_score != evidence.combined_score
        or assessment.diagnostics.source_combined_confidence != evidence.combined_confidence
    ):
        raise ConfigurationError(
            "TrimAssessment does not derive from this DecisionEvidence "
            f"({assessment.symbol}/{assessment.horizon} vs {evidence.symbol}/{evidence.horizon})"
        )

    deviation = assessment.evidence_trim_score - NEUTRAL_BASELINE
    combined_excess = evidence.expected_excess_return
    contributions = tuple(
        EvidenceContribution(
            model_name=c.model,
            contribution=(
                deviation * c.signed_contribution / combined_excess if combined_excess else 0.0
            ),
            direction=_direction(
                deviation * c.signed_contribution / combined_excess if combined_excess else 0.0
            ),
            confidence=c.confidence,
            evidence_strength=abs(c.score - 50.0) / 50.0,
            expected_excess_return=c.effect,
        )
        for c in assessment.model_contributions
    )
    portfolio = _split_overlay(assessment)
    clip_residual = assessment.trim_score - (
        assessment.evidence_trim_score + assessment.portfolio_adjustment
    )

    items: list[tuple[str, str, float]] = [
        (c.model_name, "model", c.contribution) for c in contributions
    ]
    if assessment.portfolio_weight is not None:
        items.append(("portfolio concentration", "portfolio", portfolio.concentration_adjustment))
        items.append(
            ("portfolio diversification", "portfolio", portfolio.diversification_adjustment)
        )
    if clip_residual:
        items.append(("clip at score bounds", "clip", clip_residual))
    items.sort(key=lambda item: (-abs(item[2]), item[0]))
    ranking: list[RankedContribution] = []
    running = NEUTRAL_BASELINE
    for name, kind, value in items:
        running += value
        ranking.append(
            RankedContribution(name=name, kind=kind, contribution=value, cumulative=running)
        )

    positive = max((i for i in items if i[2] > 0), key=lambda i: i[2], default=None)
    negative = min((i for i in items if i[2] < 0), key=lambda i: i[2], default=None)
    least_precise = max(assessment.model_contributions, key=lambda c: (c.se, c.model), default=None)
    dominant_regime = (
        assessment.strongest_supporting_reason
        if deviation >= 0 and assessment.strongest_supporting_reason is not None
        else assessment.strongest_opposing_reason or assessment.strongest_supporting_reason
    )

    return AttributionReport(
        symbol=assessment.symbol,
        horizon=assessment.horizon,
        as_of=assessment.as_of,
        trim_score=assessment.trim_score,
        confidence=assessment.confidence,
        neutral_baseline=NEUTRAL_BASELINE,
        evidence_contributions=contributions,
        portfolio_contributions=portfolio,
        clip_residual=clip_residual,
        strongest_positive_contributor=positive[0] if positive else None,
        strongest_negative_contributor=negative[0] if negative else None,
        largest_uncertainty=(
            {"model": least_precise.model, "standard_error": least_precise.se}
            if least_precise is not None
            else None
        ),
        dominant_historical_regime=dominant_regime,
        dominant_portfolio_driver=_portfolio_driver(assessment),
        contribution_ranking=tuple(ranking),
        omitted_models=assessment.omitted_models,
        neutral_models=assessment.neutral_models,
        contradictory_evidence=assessment.contradictory_evidence,
        traceability={
            "decision_combined_score": assessment.diagnostics.source_combined_score,
            "decision_combined_confidence": assessment.diagnostics.source_combined_confidence,
            "evidence_trim_score": assessment.evidence_trim_score,
            "portfolio_adjustment": assessment.portfolio_adjustment,
            "combined_expected_excess_return": evidence.expected_excess_return,
            "recommendation_label": assessment.recommendation_label,
            "data_quality_label": assessment.data_quality_label,
            "trim_engine_version": assessment.engine_version,
            "attribution_engine_version": ENGINE_VERSION,
        },
    )


class AttributionEngine:
    """Drives the existing engines once and attributes every assessment.
    Consumes nothing below DecisionEvidence and TrimAssessment."""

    def __init__(self, session: Session, config: TrimConfig | None = None) -> None:
        self._engine = DecisionEvidenceEngine(session)
        self._config = config or TrimConfig()

    def assessed(
        self,
        symbols: list[str] | None = None,
        portfolio: str | None = None,
        as_of: date | None = None,
    ) -> dict[str, list[tuple[TrimAssessment, AttributionReport]]]:
        """Every assessment with its exact accounting, from ONE evidence run
        — the input surface for the report layer, which may not touch
        DecisionEvidence itself."""
        evidence = self._engine.assess(symbols=symbols, portfolio=portfolio, as_of=as_of)
        results: dict[str, list[tuple[TrimAssessment, AttributionReport]]] = {}
        for symbol, evidences in evidence.items():
            assessments = assess_symbol(evidences, self._config)
            by_horizon = {e.horizon: e for e in evidences}
            results[symbol] = [(a, attribute(a, by_horizon[a.horizon])) for a in assessments]
        return results

    def report(
        self,
        symbols: list[str] | None = None,
        portfolio: str | None = None,
        as_of: date | None = None,
    ) -> dict[str, list[AttributionReport]]:
        return {
            symbol: [report for _, report in pairs]
            for symbol, pairs in self.assessed(
                symbols=symbols, portfolio=portfolio, as_of=as_of
            ).items()
        }
