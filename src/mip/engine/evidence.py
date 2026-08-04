"""Decision Evidence Engine: one statistically consistent assessment per
holding and horizon, combined from ALL intelligence models' normalized
evidence — answering "what does the total historical evidence suggest?",
never "what should I do?". No Hold/Buy/Trim/Sell exists here.

Isolation: this layer consumes ONLY the NormalizedEvidence contract and
PortfolioPositionAssessment, gathered through the public mip.models and
mip.portfolio.analytics surfaces. It never touches model internals, the
research engine, feature calculators, providers, or raw tables.

Statistical combination (documented before implementation, per the phase
contract):

- Each participating model contributes ONE study: its combined excess
  effect with an EQUAL per-model standard error (see model_standard_error).
  Scores are never averaged.

  HISTORICAL DEFECT (removed 2026-08-02, amendment A-2026-006): this layer
  previously recovered se = abs(effect / z_raw), making the precision weight
  w = (z_raw / effect)^2. That inverted the weighting — a model reporting a
  LARGER effect received a SMALLER weight (measured spearman(|effect|, w) =
  -0.72) — and made w unbounded as effect -> 0. It is a correctness defect
  and must never return. Repairing it does NOT improve forecasting accuracy;
  see docs/v6/V6_RECOVERED_SE_REPAIR_RESULTS.md. No predictive claim attaches
  to this change.
- Cross-model combination reuses the shared correlated fixed-effect
  meta-analysis (mip.models.combine_evidence) with a DECLARED conservative
  correlation prior, not an estimate: every distinct model pair gets
  BASELINE_CORRELATION (all models study the same stock's forward returns
  over overlapping history, so their sampling errors are positively
  correlated a priori), and the named information-sharing pairs —
  rates↔macro, sector↔relative, momentum↔relative — get
  OVERLAP_CORRELATION. These constants only INFLATE uncertainty (higher
  correlation → larger combined SE → less confidence than independence
  would fake); directional weights remain pure precision 1/se².
- Evidence volume never sums across overlapping models: combined effective
  sample size is the MAX of the participating models' — the same doctrine
  every model applies internally.
- Contradiction cannot produce confidence: disagreeing effects cancel in
  the precision-weighted mean, and combined_confidence = volume × agreement
  where agreement is the precision share matching the combined sign.
  contradictory_evidence = 1 − agreement is surfaced explicitly.
- Missing evidence is never neutral evidence. Models are partitioned into
  participating (non-neutral: enter the statistics), neutral (evaluated,
  honestly found nothing — EXCLUDED: a fabricated zero-effect observation
  would manufacture precision), and omitted (could not evaluate in this
  data environment). Zero participants yields an explicit no-evidence
  result, not a fake neutral with confidence.
- Explainability: every output carries a per-model breakdown (effect, se,
  z, precision share, signed contribution) plus the strongest supporting
  and opposing regime-level reasons with model attribution — fully
  traceable to the originating models.
"""

import math
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from mip.core.exceptions import ConfigurationError
from mip.models import (
    ALL_MODELS,
    Z_CLIP,
    NormalizedEvidence,
    combine_evidence,
    confidence_from_evidence,
    normalize_scores,
    score_from_z,
)
from mip.portfolio.analytics import PortfolioAnalyzer, PortfolioPositionAssessment

HORIZONS = ("1w", "2w", "1m", "3m", "6m", "1y")

# Evidence computed and reported but EXCLUDED from the official combined
# score, per the analogue v1 out-of-sample validation and the hardened
# (leakage-free) revalidation: shadow evidence is informational only and
# must never influence recommendations. Promotion requires passing
# docs/VALIDATION_GATES.md.
SHADOW_MODELS = frozenset({"historical_analogues", "conditional_probability"})
PRIOR_EVENTS = 30.0  # effective events for confidence 0.5 (platform-wide)

# Declared cross-model correlation priors (uncertainty inflation, not
# weights). Named pairs share information sources; everything else shares
# only the stock's forward-return history.
BASELINE_CORRELATION = 0.2
OVERLAP_CORRELATION = 0.5
OVERLAPPING_PAIRS = (
    frozenset({"interest_rate_sensitivity", "macro_regime"}),
    frozenset({"sector_rotation", "relative_strength"}),
    frozenset({"momentum_exhaustion", "relative_strength"}),
    # the analogue model reuses the same feature information as every
    # regime model, so every pairing gets the conservative overlap prior
    *(
        frozenset({"historical_analogues", other})
        for other in (
            "interest_rate_sensitivity",
            "sector_rotation",
            "momentum_exhaustion",
            "valuation",
            "earnings_behavior",
            "macro_regime",
            "relative_strength",
        )
    ),
    # the conditional probability engine pools the same feature conditions as
    # every model, so every pairing gets the conservative overlap prior
    *(
        frozenset({"conditional_probability", other})
        for other in (
            "interest_rate_sensitivity",
            "sector_rotation",
            "momentum_exhaustion",
            "valuation",
            "earnings_behavior",
            "macro_regime",
            "relative_strength",
            "historical_analogues",
        )
    ),
)


def model_correlation(model_a: str, model_b: str) -> float:
    if model_a == model_b:
        return 1.0
    if frozenset({model_a, model_b}) in OVERLAPPING_PAIRS:
        return OVERLAP_CORRELATION
    return BASELINE_CORRELATION


@dataclass(frozen=True)
class ModelContribution:
    """One model's traceable share of the combined evidence."""

    model: str
    score: float
    effect: float  # the model's expected excess return
    se: float  # equal per-model standard error (see model_standard_error)
    z_raw: float
    confidence: float
    effective_sample_size: float
    weight_share: float  # this model's precision share of the combination
    signed_contribution: float  # weight_share x effect (sums to combined effect)
    saturated: bool

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "score": self.score,
            "effect": self.effect,
            "se": self.se,
            "z_raw": self.z_raw,
            "confidence": self.confidence,
            "effective_sample_size": self.effective_sample_size,
            "weight_share": self.weight_share,
            "signed_contribution": self.signed_contribution,
            "saturated": self.saturated,
        }


@dataclass(frozen=True)
class DecisionDiagnostics:
    participating: int
    z_raw: float
    z_clipped: float
    agreement: float
    saturated: bool
    mean_prior_correlation: float

    def to_dict(self) -> dict:
        return {
            "participating": self.participating,
            "z_raw": self.z_raw,
            "z_clipped": self.z_clipped,
            "agreement": self.agreement,
            "saturated": self.saturated,
            "mean_prior_correlation": self.mean_prior_correlation,
        }


@dataclass(frozen=True)
class DecisionEvidence:
    """The combined evidence for one symbol at one horizon. Descriptive
    only — deliberately contains no recommendation, label, or score of
    action."""

    symbol: str
    horizon: str
    as_of: date
    # historical expectations (None when nothing participates)
    expected_return: float | None
    expected_excess_return: float | None
    expected_downside: float | None
    expected_upside: float | None
    historical_hit_rate: float | None
    # combined evidence
    combined_score: float  # 0-100 evidence convention; 50 = no combined edge
    combined_confidence: float
    evidence_strength: float
    contradictory_evidence: float
    effective_sample_size: float
    participating_models: tuple[str, ...]
    neutral_models: tuple[str, ...]  # evaluated, honestly found nothing
    omitted_models: tuple[str, ...]  # could not evaluate here
    # portfolio context (verbatim; never folded into the statistics)
    portfolio_name: str | None
    portfolio_weight: float | None
    risk_contribution: float | None
    diversification_contribution: float | None
    concentration_flags: tuple[str, ...]
    # explainability
    dominant_positive_models: tuple[str, ...]
    dominant_negative_models: tuple[str, ...]
    strongest_supporting_reason: dict | None
    strongest_opposing_reason: dict | None
    evidence_breakdown: tuple[ModelContribution, ...]
    diagnostics: DecisionDiagnostics | None
    shadow_models: tuple[str, ...] = ()  # informational only; never in the score
    model_context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "horizon": self.horizon,
            "as_of": self.as_of.isoformat(),
            "expected_return": self.expected_return,
            "expected_excess_return": self.expected_excess_return,
            "expected_downside": self.expected_downside,
            "expected_upside": self.expected_upside,
            "historical_hit_rate": self.historical_hit_rate,
            "combined_score": self.combined_score,
            "combined_confidence": self.combined_confidence,
            "evidence_strength": self.evidence_strength,
            "contradictory_evidence": self.contradictory_evidence,
            "effective_sample_size": self.effective_sample_size,
            "participating_models": list(self.participating_models),
            "neutral_models": list(self.neutral_models),
            "shadow_models": list(self.shadow_models),
            "omitted_models": list(self.omitted_models),
            "portfolio_name": self.portfolio_name,
            "portfolio_weight": self.portfolio_weight,
            "risk_contribution": self.risk_contribution,
            "diversification_contribution": self.diversification_contribution,
            "concentration_flags": list(self.concentration_flags),
            "dominant_positive_models": list(self.dominant_positive_models),
            "dominant_negative_models": list(self.dominant_negative_models),
            "strongest_supporting_reason": self.strongest_supporting_reason,
            "strongest_opposing_reason": self.strongest_opposing_reason,
            "evidence_breakdown": [c.to_dict() for c in self.evidence_breakdown],
            "diagnostics": self.diagnostics.to_dict() if self.diagnostics else None,
            "model_context": self.model_context,
        }


# -- per-model uncertainty ----------------------------------------------------

EQUAL_SE = 1.0  # frozen scale for the equal-uncertainty rule
MIN_N_EFF = 1.0  # smallest admissible effective sample size


def model_standard_error(n_eff: float | None) -> float:
    """The per-model standard error entering cross-model combination.

    EQUAL UNCERTAINTY. Every participating model receives the same standard
    error, so precision weights are equal and normalized weights are exactly
    1/n — bounded by construction and independent of the reported effect.

    Why not se = k_h / sqrt(n_eff), the estimator validated in the V6
    recovered-SE repair experiment: that estimator is defined only together
    with a per-horizon scale constant k_h, and k_h was fixed in the research
    design by matching the median combined |z| of the DEFECTIVE system. Once
    the defective system is removed there is no production analogue for k_h,
    and fitting one is not authorized. Equal uncertainty is the fallback the
    research record authorizes and needs no scale constant to produce weights.

    `n_eff` is validated explicitly so that zero, negative, missing and
    non-finite inputs are rejected here rather than propagating into the
    combination. The returned value is the same either way; the guard exists
    so the contract is testable and the failure mode is not silent.
    """
    if n_eff is None:
        return EQUAL_SE
    try:
        value = float(n_eff)
    except (TypeError, ValueError):
        return EQUAL_SE
    if not math.isfinite(value) or value < MIN_N_EFF:
        return EQUAL_SE
    return EQUAL_SE


def _usable(evidence: NormalizedEvidence) -> bool:
    """A model participates only with a real, invertible effect estimate."""
    return (
        not evidence.neutral
        and evidence.expected_excess_return is not None
        and evidence.diagnostics is not None
        and evidence.diagnostics.z_raw != 0
        and evidence.expected_excess_return != 0
    )


def _reason_payload(model: str, reason) -> dict:
    return {
        "model": model,
        "label": reason.label,
        "description": reason.description,
        "n": reason.n,
        "n_eff": reason.n_eff,
        "mean": reason.mean,
        "baseline_mean": reason.baseline_mean,
        "excess": reason.excess,
        "hit_rate": reason.hit_rate,
    }


def combine_model_evidence(
    symbol: str,
    horizon: str,
    as_of: date,
    per_model: dict[str, NormalizedEvidence],
    omitted: tuple[str, ...] = (),
    assessment: PortfolioPositionAssessment | None = None,
    shadow: frozenset[str] = SHADOW_MODELS,
) -> DecisionEvidence:
    """The reusable combination: NormalizedEvidence per model in, one
    DecisionEvidence out. Pure — no database, no side effects."""
    shadow_map = {m: e for m, e in per_model.items() if m in shadow}
    official = {m: e for m, e in per_model.items() if m not in shadow}
    participating = {m: e for m, e in official.items() if _usable(e)}
    model_context = {m: e.context for m, e in per_model.items() if e.context}
    shadow_models = tuple(sorted(shadow_map))
    neutral = tuple(sorted(set(official) - set(participating)))
    portfolio_fields = {
        "portfolio_name": assessment.portfolio_name if assessment else None,
        "portfolio_weight": assessment.portfolio_weight if assessment else None,
        "risk_contribution": assessment.risk_contribution if assessment else None,
        "diversification_contribution": (
            assessment.diversification_contribution if assessment else None
        ),
        "concentration_flags": tuple(assessment.concentration_flags) if assessment else (),
    }

    if not participating:
        return DecisionEvidence(
            symbol=symbol,
            horizon=horizon,
            as_of=as_of,
            expected_return=None,
            expected_excess_return=None,
            expected_downside=None,
            expected_upside=None,
            historical_hit_rate=None,
            combined_score=50.0,
            combined_confidence=0.0,
            evidence_strength=0.0,
            contradictory_evidence=0.0,
            effective_sample_size=0.0,
            participating_models=(),
            neutral_models=neutral,
            shadow_models=shadow_models,
            omitted_models=tuple(sorted(omitted)),
            dominant_positive_models=(),
            dominant_negative_models=(),
            strongest_supporting_reason=None,
            strongest_opposing_reason=None,
            evidence_breakdown=(),
            diagnostics=None,
            model_context=model_context,
            **portfolio_fields,
        )

    names = sorted(participating)  # deterministic order
    effects = [participating[m].expected_excess_return for m in names]
    ses = [model_standard_error(participating[m].effective_sample_size) for m in names]
    correlation = [[model_correlation(a, b) for b in names] for a in names]
    combined = combine_evidence(effects, ses, correlation)
    assert combined is not None  # ses > 0 by construction

    weights = [1.0 / s**2 for s in ses]
    total_weight = sum(weights)
    shares = [w / total_weight for w in weights]

    def weighted(values: list[float | None]) -> float | None:
        pairs = [(s, v) for s, v in zip(shares, values, strict=True) if v is not None]
        if not pairs:
            return None
        share_total = sum(s for s, _ in pairs)
        return sum(s * v for s, v in pairs) / share_total

    expected = weighted([participating[m].expected_return for m in names])
    volatility = weighted([participating[m].expected_volatility for m in names])
    hit_rate = weighted([participating[m].historical_hit_rate for m in names])
    max_n_eff = max(participating[m].effective_sample_size for m in names)
    confidence = confidence_from_evidence(max_n_eff, combined.agreement, PRIOR_EVENTS)
    score = score_from_z(combined.z)

    breakdown = tuple(
        ModelContribution(
            model=m,
            score=participating[m].score,
            effect=effects[i],
            se=ses[i],
            z_raw=participating[m].diagnostics.z_raw,
            confidence=participating[m].confidence,
            effective_sample_size=participating[m].effective_sample_size,
            weight_share=shares[i],
            signed_contribution=shares[i] * effects[i],
            saturated=participating[m].diagnostics.saturated,
        )
        for i, m in enumerate(names)
    )
    positive = sorted((c for c in breakdown if c.effect > 0), key=lambda c: -c.signed_contribution)
    negative = sorted((c for c in breakdown if c.effect < 0), key=lambda c: c.signed_contribution)

    def strongest(reasons_key: str, want_positive: bool) -> dict | None:
        best, best_ratio = None, 0.0
        for m in names:
            for reason in getattr(participating[m], reasons_key):
                if reason.se <= 0:
                    continue
                if want_positive != (reason.excess > 0):
                    continue
                ratio = abs(reason.excess / reason.se)
                if ratio > best_ratio:
                    best, best_ratio = _reason_payload(m, reason), ratio
        return best

    off_diagonal = [correlation[i][j] for i in range(len(names)) for j in range(i + 1, len(names))]
    diagnostics = DecisionDiagnostics(
        participating=len(names),
        z_raw=combined.z_raw,
        z_clipped=combined.z,
        agreement=combined.agreement,
        saturated=abs(combined.z_raw) > Z_CLIP,
        mean_prior_correlation=(sum(off_diagonal) / len(off_diagonal) if off_diagonal else 0.0),
    )
    return DecisionEvidence(
        symbol=symbol,
        horizon=horizon,
        as_of=as_of,
        expected_return=expected,
        expected_excess_return=combined.effect,
        expected_downside=(expected - volatility if None not in (expected, volatility) else None),
        expected_upside=(expected + volatility if None not in (expected, volatility) else None),
        historical_hit_rate=hit_rate,
        combined_score=score,
        combined_confidence=confidence,
        evidence_strength=abs(score - 50.0) / 50.0,
        contradictory_evidence=1.0 - combined.agreement,
        effective_sample_size=max_n_eff,
        participating_models=tuple(names),
        neutral_models=neutral,
        shadow_models=shadow_models,
        omitted_models=tuple(sorted(omitted)),
        dominant_positive_models=tuple(c.model for c in positive),
        dominant_negative_models=tuple(c.model for c in negative),
        strongest_supporting_reason=strongest("supporting_reasons", True),
        strongest_opposing_reason=strongest("opposing_reasons", False),
        evidence_breakdown=breakdown,
        diagnostics=diagnostics,
        model_context=model_context,
        **portfolio_fields,
    )


class DecisionEvidenceEngine:
    """Gathers normalized evidence through the public surfaces and combines
    it per symbol x horizon. Knows nothing about how evidence is made."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def assess(
        self,
        symbols: list[str] | None = None,
        portfolio: str | None = None,
        as_of: date | None = None,
    ) -> dict[str, list[DecisionEvidence]]:
        assessments: dict[str, PortfolioPositionAssessment] = {}
        if portfolio is not None:
            for assessment in PortfolioAnalyzer(self._session).analyze(
                portfolio, as_of=as_of, with_evidence=False
            ):
                assessments[assessment.symbol] = assessment
        if symbols is None:
            if portfolio is None:
                raise ConfigurationError("provide symbols or --portfolio")
            symbols = sorted(assessments)
        else:
            symbols = [s.strip().upper() for s in symbols]

        return {
            symbol: self._assess_symbol(symbol, assessments.get(symbol), as_of)
            for symbol in symbols
        }

    def gather(
        self, symbol: str, as_of: date | None = None
    ) -> tuple[dict[str, dict[str, NormalizedEvidence]], tuple[str, ...], date]:
        """One model pass: every model's normalized evidence per horizon,
        the omitted models, and the resolved as_of — the raw material for
        both the combination below and the Portfolio Intelligence Engine."""
        by_model: dict[str, dict[str, NormalizedEvidence]] = {}
        omitted: list[str] = []
        latest_as_of: date | None = as_of
        for model_cls in ALL_MODELS:
            try:
                batch = normalize_scores(model_cls(self._session).evaluate(symbol, as_of=as_of))
            except ConfigurationError:
                omitted.append(model_cls.name)
                continue
            by_model[batch[0].model_name] = {e.horizon: e for e in batch}
            resolved = batch[0].as_of
            if latest_as_of is None or resolved > latest_as_of:
                latest_as_of = resolved
        if latest_as_of is None:
            raise ConfigurationError(f"no model could evaluate {symbol!r}")
        return by_model, tuple(sorted(omitted)), latest_as_of

    def _assess_symbol(
        self,
        symbol: str,
        assessment: PortfolioPositionAssessment | None,
        as_of: date | None,
    ) -> list[DecisionEvidence]:
        by_model, omitted, latest_as_of = self.gather(symbol, as_of)
        return [
            combine_model_evidence(
                symbol,
                horizon,
                latest_as_of,
                {m: horizons[horizon] for m, horizons in by_model.items()},
                omitted=omitted,
                assessment=assessment,
            )
            for horizon in HORIZONS
        ]
