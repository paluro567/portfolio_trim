"""Horizon-Specific Trim Score Engine: DecisionEvidence in, TrimAssessment out.

The trim score answers "how strongly does the current statistical and
portfolio evidence support reducing exposure over this horizon?" — never
"will the stock go down?". It is an evidence-strength measure (0 = evidence
strongly favors maintaining exposure, 50 = balanced/contradictory/
insufficient, 100 = evidence strongly favors reducing), not a probability
of decline, not an expected loss, and not a trade instruction. Labels
summarize historical evidence; they are not personalized financial advice.

The complete transformation (everything else is copied verbatim from
DecisionEvidence):

    E = 50 + c * (50 - s)                 evidence_trim_score
    W = P_w * max(0, w / L_w - 1)         weight term (beyond declared limit)
    R = P_r * (rc - w)                    risk-share term (risk vs capital share)
    A = clip(W + R, -A_max, +A_max)       portfolio_adjustment (0 without portfolio)
    T = clip(E + A, 0, 100)               trim_score

where s = combined_score and c = combined_confidence from DecisionEvidence,
w = portfolio weight, rc = risk contribution share. E is credibility
weighting toward the neutral prior: E = c*(100-s) + (1-c)*50 — the
reflection of the evidence score, shrunk by the confidence the decision
engine already computed. Contradiction enters exactly once, through c
(the decision engine already cancels disagreeing effects in s and
discounts c by agreement); this layer adds no further contradiction term.
Neutral and omitted models were excluded upstream and exert no directional
pressure here. The portfolio overlay is small, bounded by A_max, monotonic
in weight and risk share, and always reported separately from E.

Isolation: this layer consumes ONLY DecisionEvidence — never intelligence
models, NormalizedEvidence, the research engine, features, providers,
repositories, or the portfolio ledger (portfolio context arrives on
DecisionEvidence verbatim).
"""

from dataclasses import dataclass, field, replace
from datetime import date

from sqlalchemy.orm import Session

from mip.core.exceptions import ConfigurationError
from mip.engine.evidence import (
    HORIZONS,
    DecisionEvidence,
    DecisionEvidenceEngine,
    ModelContribution,
)

ENGINE_VERSION = 1

# Frozen platform horizon vocabulary (ARCHITECTURE.md: 1w, 2w, 1m, 3m, ...).
HORIZON_SESSIONS = {"1w": 5, "2w": 10, "1m": 21, "3m": 63, "6m": 126, "1y": 252}
assert tuple(HORIZON_SESSIONS) == HORIZONS


@dataclass(frozen=True)
class LabelBand:
    """One recommendation-label band: applies to scores below `upper`
    (the last band also covers its upper bound). `min_confidence` gates
    aggressive labels — a score in this band with lower confidence is
    downgraded stepwise toward the neutral band, with a recorded warning."""

    upper: float
    label: str
    min_confidence: float = 0.0


DEFAULT_BANDS = (
    LabelBand(25.0, "Maintain", 0.40),
    LabelBand(40.0, "Hold / Monitor"),
    LabelBand(60.0, "Mixed Evidence"),
    LabelBand(75.0, "Trim Consideration"),
    LabelBand(90.0, "Trim", 0.40),
    LabelBand(100.0, "Strong Trim Candidate", 0.60),
)


@dataclass(frozen=True)
class TrimConfig:
    """Every knob of the trim transformation, documented and bounded.

    Portfolio overlay: `weight_limit` mirrors the portfolio analyzer's
    declared concentration limit; `weight_excess_points` are score points
    per full limit-multiple of excess weight (a position at 2x the limit
    adds exactly `weight_excess_points`); `risk_share_points` are points
    per unit of (risk_contribution - weight) — positive for positions
    contributing more risk than capital, negative for diversifiers. The
    total adjustment is clipped to +/- `max_portfolio_adjustment`.
    """

    bands: tuple[LabelBand, ...] = DEFAULT_BANDS
    insufficient_evidence_label: str = "Insufficient Evidence"
    max_portfolio_adjustment: float = 10.0
    weight_limit: float = 0.15
    weight_excess_points: float = 10.0
    risk_share_points: float = 25.0
    # data-quality thresholds (summaries, not statistics)
    sparse_n_eff: float = 15.0
    sparse_max_participants: int = 2
    conflicted_contradiction: float = 0.5
    strong_min_participants: int = 4
    strong_min_n_eff: float = 30.0
    strong_max_contradiction: float = 0.25
    # cross-horizon explanation signals (not errors)
    abrupt_score_change: float = 20.0
    confidence_drop: float = 0.25

    def __post_init__(self) -> None:
        if not self.bands:
            raise ConfigurationError("TrimConfig.bands must not be empty")
        uppers = [band.upper for band in self.bands]
        if uppers != sorted(uppers) or len(set(uppers)) != len(uppers):
            raise ConfigurationError("TrimConfig.bands must have strictly ascending bounds")
        if self.bands[-1].upper < 100.0:
            raise ConfigurationError("TrimConfig.bands must cover scores up to 100")
        if any(not 0.0 <= band.min_confidence <= 1.0 for band in self.bands):
            raise ConfigurationError("LabelBand.min_confidence must be within [0, 1]")
        if self.max_portfolio_adjustment < 0:
            raise ConfigurationError("max_portfolio_adjustment must be >= 0")
        if self.weight_limit <= 0:
            raise ConfigurationError("weight_limit must be positive")

    def band_index(self, score: float) -> int:
        for i, band in enumerate(self.bands):
            if score < band.upper:
                return i
        return len(self.bands) - 1

    def neutral_index(self) -> int:
        return self.band_index(50.0)


@dataclass(frozen=True)
class TrimDiagnostics:
    """Exact derivation record: the formula inputs and every term, so any
    trim score is reproducible by hand from this object alone."""

    source_combined_score: float
    source_combined_confidence: float
    evidence_deviation: float  # 50 - combined_score (pre-shrinkage direction)
    weight_term: float
    risk_term: float
    raw_portfolio_pressure: float  # weight_term + risk_term before the clip
    adjustment_bound: float
    adjustment_capped: bool
    label_before_gate: str
    label_downgraded: bool
    confidence_floor: float  # floor of the pre-gate band
    decision_z_raw: float | None
    decision_agreement: float | None
    decision_saturated: bool | None
    cross_horizon_notes: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "source_combined_score": self.source_combined_score,
            "source_combined_confidence": self.source_combined_confidence,
            "evidence_deviation": self.evidence_deviation,
            "weight_term": self.weight_term,
            "risk_term": self.risk_term,
            "raw_portfolio_pressure": self.raw_portfolio_pressure,
            "adjustment_bound": self.adjustment_bound,
            "adjustment_capped": self.adjustment_capped,
            "label_before_gate": self.label_before_gate,
            "label_downgraded": self.label_downgraded,
            "confidence_floor": self.confidence_floor,
            "decision_z_raw": self.decision_z_raw,
            "decision_agreement": self.decision_agreement,
            "decision_saturated": self.decision_saturated,
            "cross_horizon_notes": list(self.cross_horizon_notes),
        }


@dataclass(frozen=True)
class TrimAssessment:
    """The explainable trim assessment for one symbol and one horizon.

    `strongest_supporting_reason` supports THE TRIM (it is the strongest
    historical evidence against exposure — DecisionEvidence's strongest
    opposing reason); `strongest_opposing_reason` opposes the trim. Not a
    trade instruction: no quantities, no orders, no broker actions.
    """

    # identity
    symbol: str
    as_of: date
    horizon: str
    horizon_sessions: int
    engine_version: int
    # assessment
    trim_score: float  # final: clip(evidence_trim_score + portfolio_adjustment)
    evidence_trim_score: float
    portfolio_adjustment: float
    confidence: float
    recommendation_label: str
    expected_return: float | None
    expected_excess_return: float | None
    expected_downside: float | None
    expected_upside: float | None
    # evidence quality
    participating_models: tuple[str, ...]
    neutral_models: tuple[str, ...]
    omitted_models: tuple[str, ...]
    evidence_strength: float
    contradictory_evidence: float
    effective_sample_size: float
    data_quality_label: str
    # portfolio context (verbatim from DecisionEvidence)
    portfolio_name: str | None
    portfolio_weight: float | None
    risk_contribution: float | None
    diversification_contribution: float | None
    concentration_flags: tuple[str, ...]
    # reasoning
    primary_trim_drivers: tuple[str, ...]  # models pressing to reduce, strongest first
    primary_hold_strengths: tuple[str, ...]  # models arguing to maintain, strongest first
    strongest_supporting_reason: dict | None  # supports trimming
    strongest_opposing_reason: dict | None  # opposes trimming
    model_contributions: tuple[ModelContribution, ...]
    limitations: tuple[str, ...]
    explanation: str
    diagnostics: TrimDiagnostics
    context: dict = field(default_factory=dict)  # per-model structured context

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "as_of": self.as_of.isoformat(),
            "horizon": self.horizon,
            "horizon_sessions": self.horizon_sessions,
            "engine_version": self.engine_version,
            "trim_score": self.trim_score,
            "evidence_trim_score": self.evidence_trim_score,
            "portfolio_adjustment": self.portfolio_adjustment,
            "confidence": self.confidence,
            "recommendation_label": self.recommendation_label,
            "expected_return": self.expected_return,
            "expected_excess_return": self.expected_excess_return,
            "expected_downside": self.expected_downside,
            "expected_upside": self.expected_upside,
            "participating_models": list(self.participating_models),
            "neutral_models": list(self.neutral_models),
            "omitted_models": list(self.omitted_models),
            "evidence_strength": self.evidence_strength,
            "contradictory_evidence": self.contradictory_evidence,
            "effective_sample_size": self.effective_sample_size,
            "data_quality_label": self.data_quality_label,
            "portfolio_name": self.portfolio_name,
            "portfolio_weight": self.portfolio_weight,
            "risk_contribution": self.risk_contribution,
            "diversification_contribution": self.diversification_contribution,
            "concentration_flags": list(self.concentration_flags),
            "primary_trim_drivers": list(self.primary_trim_drivers),
            "primary_hold_strengths": list(self.primary_hold_strengths),
            "strongest_supporting_reason": self.strongest_supporting_reason,
            "strongest_opposing_reason": self.strongest_opposing_reason,
            "model_contributions": [c.to_dict() for c in self.model_contributions],
            "limitations": list(self.limitations),
            "explanation": self.explanation,
            "diagnostics": self.diagnostics.to_dict(),
            "context": self.context,
        }


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def evidence_trim_score(evidence: DecisionEvidence) -> float:
    """E = 50 + c*(50 - s): the reflection of the combined evidence score,
    credibility-shrunk toward the neutral prior by the combined confidence."""
    return 50.0 + evidence.combined_confidence * (50.0 - evidence.combined_score)


def portfolio_terms(
    evidence: DecisionEvidence, config: TrimConfig
) -> tuple[float, float, float, bool]:
    """(adjustment, weight_term, risk_term, capped). Zero without portfolio
    context; the risk-share term needs both weight and risk contribution."""
    weight = evidence.portfolio_weight
    if weight is None:
        return 0.0, 0.0, 0.0, False
    weight_term = config.weight_excess_points * max(0.0, weight / config.weight_limit - 1.0)
    risk_term = 0.0
    if evidence.risk_contribution is not None:
        risk_term = config.risk_share_points * (evidence.risk_contribution - weight)
    bound = config.max_portfolio_adjustment
    raw = weight_term + risk_term
    return _clip(raw, -bound, bound), weight_term, risk_term, abs(raw) > bound


def apply_label(
    score: float, confidence: float, config: TrimConfig
) -> tuple[str, str, bool, float]:
    """(label, label_before_gate, downgraded, confidence_floor). Bands whose
    floor exceeds the confidence are downgraded stepwise toward the neutral
    band; the raw score is never altered."""
    index = config.band_index(score)
    band = config.bands[index]
    before, floor = band.label, band.min_confidence
    neutral = config.neutral_index()
    while band.min_confidence > confidence and index != neutral:
        index += 1 if index < neutral else -1
        band = config.bands[index]
    return band.label, before, band.label != before, floor


def data_quality(evidence: DecisionEvidence, config: TrimConfig) -> str:
    participants = len(evidence.participating_models)
    if participants == 0:
        return "no_evidence"
    if (
        evidence.effective_sample_size < config.sparse_n_eff
        or participants <= config.sparse_max_participants
    ):
        return "sparse"
    if evidence.contradictory_evidence >= config.conflicted_contradiction:
        return "conflicted"
    if (
        participants >= config.strong_min_participants
        and evidence.effective_sample_size >= config.strong_min_n_eff
        and evidence.contradictory_evidence <= config.strong_max_contradiction
    ):
        return "strong"
    return "moderate"


def _limitations(
    evidence: DecisionEvidence,
    quality: str,
    downgraded: bool,
    before: str,
    floor: float,
    risk_term_available: bool,
) -> tuple[str, ...]:
    notes: list[str] = []
    if not evidence.participating_models:
        notes.append("no model produced combinable evidence; the score is pure neutral")
    if downgraded:
        notes.append(
            f"label downgraded from {before!r}: confidence "
            f"{evidence.combined_confidence:.2f} is below the {floor:.2f} floor "
            "(raw score preserved)"
        )
    if evidence.neutral_models:
        notes.append(
            "evaluated but currently without active evidence: " + ", ".join(evidence.neutral_models)
        )
    if evidence.omitted_models:
        notes.append(
            "could not be evaluated in this data environment: " + ", ".join(evidence.omitted_models)
        )
    if quality == "sparse":
        notes.append("sparse evidence: interpret the score direction, not its magnitude")
    if evidence.diagnostics is not None and evidence.diagnostics.saturated:
        notes.append("combined z exceeded the reporting bound; score saturated at the clip")
    if evidence.portfolio_weight is None:
        notes.append("no portfolio context: portfolio adjustment is 0")
    elif not risk_term_available:
        notes.append("risk contribution unavailable: risk-share term omitted")
    notes.append("labels summarize historical evidence; not personalized financial advice")
    return tuple(notes)


def _explanation(
    evidence: DecisionEvidence,
    final: float,
    evidence_score: float,
    adjustment: float,
    label: str,
    quality: str,
) -> str:
    parts = [
        f"Trim score {final:.1f} = evidence {evidence_score:.1f} "
        f"(combined evidence score {evidence.combined_score:.1f} at confidence "
        f"{evidence.combined_confidence:.2f}, shrunk toward 50)"
        + (f" {adjustment:+.1f} portfolio adjustment." if adjustment else ".")
    ]
    if evidence.dominant_negative_models:
        parts.append(
            "Pressure to reduce comes from " + ", ".join(evidence.dominant_negative_models) + "."
        )
    if evidence.dominant_positive_models:
        parts.append(
            "Evidence for maintaining comes from "
            + ", ".join(evidence.dominant_positive_models)
            + "."
        )
    total = (
        len(evidence.participating_models)
        + len(evidence.neutral_models)
        + len(evidence.omitted_models)
    )
    parts.append(
        f"{len(evidence.participating_models)} of {total} models participate; "
        f"data quality {quality}; label {label!r}."
    )
    return " ".join(parts)


def assess_trim(evidence: DecisionEvidence, config: TrimConfig | None = None) -> TrimAssessment:
    """The pure transformation: one DecisionEvidence in, one TrimAssessment
    out. Cross-horizon notes are attached by assess_symbol."""
    cfg = config or TrimConfig()
    e_score = evidence_trim_score(evidence)
    adjustment, weight_term, risk_term, capped = portfolio_terms(evidence, cfg)
    final = _clip(e_score + adjustment, 0.0, 100.0)
    confidence = evidence.combined_confidence

    label, before, downgraded, floor = apply_label(final, confidence, cfg)
    if not evidence.participating_models:
        label, downgraded = cfg.insufficient_evidence_label, False
    quality = data_quality(evidence, cfg)
    risk_term_available = (
        evidence.portfolio_weight is not None and evidence.risk_contribution is not None
    )

    diagnostics = TrimDiagnostics(
        source_combined_score=evidence.combined_score,
        source_combined_confidence=confidence,
        evidence_deviation=50.0 - evidence.combined_score,
        weight_term=weight_term,
        risk_term=risk_term,
        raw_portfolio_pressure=weight_term + risk_term,
        adjustment_bound=cfg.max_portfolio_adjustment,
        adjustment_capped=capped,
        label_before_gate=before,
        label_downgraded=downgraded,
        confidence_floor=floor,
        decision_z_raw=evidence.diagnostics.z_raw if evidence.diagnostics else None,
        decision_agreement=evidence.diagnostics.agreement if evidence.diagnostics else None,
        decision_saturated=evidence.diagnostics.saturated if evidence.diagnostics else None,
    )
    return TrimAssessment(
        symbol=evidence.symbol,
        as_of=evidence.as_of,
        horizon=evidence.horizon,
        horizon_sessions=HORIZON_SESSIONS[evidence.horizon],
        engine_version=ENGINE_VERSION,
        trim_score=final,
        evidence_trim_score=e_score,
        portfolio_adjustment=adjustment,
        confidence=confidence,
        recommendation_label=label,
        expected_return=evidence.expected_return,
        expected_excess_return=evidence.expected_excess_return,
        expected_downside=evidence.expected_downside,
        expected_upside=evidence.expected_upside,
        participating_models=evidence.participating_models,
        neutral_models=evidence.neutral_models,
        omitted_models=evidence.omitted_models,
        evidence_strength=evidence.evidence_strength,
        contradictory_evidence=evidence.contradictory_evidence,
        effective_sample_size=evidence.effective_sample_size,
        data_quality_label=quality,
        portfolio_name=evidence.portfolio_name,
        portfolio_weight=evidence.portfolio_weight,
        risk_contribution=evidence.risk_contribution,
        diversification_contribution=evidence.diversification_contribution,
        concentration_flags=evidence.concentration_flags,
        primary_trim_drivers=evidence.dominant_negative_models,
        primary_hold_strengths=evidence.dominant_positive_models,
        strongest_supporting_reason=evidence.strongest_opposing_reason,
        strongest_opposing_reason=evidence.strongest_supporting_reason,
        model_contributions=evidence.evidence_breakdown,
        limitations=_limitations(evidence, quality, downgraded, before, floor, risk_term_available),
        explanation=_explanation(evidence, final, e_score, adjustment, label, quality),
        diagnostics=diagnostics,
        context=evidence.model_context,
    )


def _side(score: float, config: TrimConfig) -> int:
    """-1 below the neutral band (maintain side), +1 at/above it (trim
    side), 0 inside it — used only for label-reversal notes."""
    neutral = config.bands[config.neutral_index()]
    lower = config.bands[config.neutral_index() - 1].upper if config.neutral_index() else 0.0
    if score < lower:
        return -1
    if score >= neutral.upper:
        return 1
    return 0


def cross_horizon_notes(assessments: list[TrimAssessment], config: TrimConfig) -> tuple[str, ...]:
    """Explanation signals across adjacent horizons — never errors."""
    notes: list[str] = []
    for a, b in zip(assessments, assessments[1:], strict=False):
        delta = b.trim_score - a.trim_score
        if abs(delta) >= config.abrupt_score_change:
            notes.append(
                f"trim score moves {delta:+.1f} points from {a.horizon} "
                f"({a.trim_score:.1f}) to {b.horizon} ({b.trim_score:.1f})"
            )
        if _side(a.trim_score, config) * _side(b.trim_score, config) == -1:
            notes.append(
                f"assessment reverses from {a.recommendation_label!r} ({a.horizon}) "
                f"to {b.recommendation_label!r} ({b.horizon})"
            )
        drop = a.confidence - b.confidence
        if drop >= config.confidence_drop:
            notes.append(
                f"confidence deteriorates by {drop:.2f} from {a.horizon} "
                f"({a.confidence:.2f}) to {b.horizon} ({b.confidence:.2f})"
            )
        if (
            a.primary_trim_drivers
            and b.primary_trim_drivers
            and a.primary_trim_drivers[0] != b.primary_trim_drivers[0]
        ):
            notes.append(
                f"primary trim driver changes from {a.primary_trim_drivers[0]} "
                f"({a.horizon}) to {b.primary_trim_drivers[0]} ({b.horizon})"
            )
    return tuple(notes)


def assess_symbol(
    evidences: list[DecisionEvidence], config: TrimConfig | None = None
) -> list[TrimAssessment]:
    """Assess every horizon of one symbol and attach the symbol's
    cross-horizon explanation signals to each assessment's diagnostics."""
    cfg = config or TrimConfig()
    ordered = sorted(evidences, key=lambda e: HORIZONS.index(e.horizon))
    assessments = [assess_trim(e, cfg) for e in ordered]
    notes = cross_horizon_notes(assessments, cfg)
    if not notes:
        return assessments
    return [
        replace(a, diagnostics=replace(a.diagnostics, cross_horizon_notes=notes))
        for a in assessments
    ]


class TrimScoreEngine:
    """Drives the Decision Evidence Engine and applies the transparent trim
    transformation per symbol and horizon. Consumes nothing below
    DecisionEvidence."""

    def __init__(self, session: Session, config: TrimConfig | None = None) -> None:
        self._engine = DecisionEvidenceEngine(session)
        self._config = config or TrimConfig()

    def assess(
        self,
        symbols: list[str] | None = None,
        portfolio: str | None = None,
        as_of: date | None = None,
    ) -> dict[str, list[TrimAssessment]]:
        evidence = self._engine.assess(symbols=symbols, portfolio=portfolio, as_of=as_of)
        return {symbol: assess_symbol(items, self._config) for symbol, items in evidence.items()}
