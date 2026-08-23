"""The structured research contract.

Two hard rules are encoded in these types rather than left to prompt wording,
because a prompt is a request and a type is a constraint:

1. **The model never writes a URL.** It may only reference source IDs that
   Python assigned from the web-search tool's own output. A fabricated citation
   is therefore an ID that does not exist in the catalogue, which is
   mechanically detectable. See ``sources.py``.

2. **The model never emits a numeric probability or expected return.**
   Scenario likelihood is an ordinal enum, and every likelihood carries a
   ``likelihood_type`` recording where it came from. Free-text fields are
   additionally screened by ``numeric_probability_violations``.

Every field is required (``| None`` for "not available") because the OpenAI
strict-schema subset does not support optional properties.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    """Base: forbids extra keys so the emitted JSON schema is strict."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------- enumerations
class ClaimType(StrEnum):
    """Where a statement comes from. Rendered visibly; never collapsed."""

    FACT = "FACT"  # verifiable, and must carry >= 1 source
    INFERENCE = "INFERENCE"  # reasoned from facts; reasoning is the model's
    MODEL_JUDGMENT = "MODEL_JUDGMENT"  # opinion/assessment, not derivable
    HISTORICAL_STATISTIC = "HISTORICAL_STATISTIC"  # from the supplied quant payload
    UNVERIFIED = "UNVERIFIED"  # asserted but unsupported; never shown as fact


class LikelihoodType(StrEnum):
    """Provenance of any likelihood statement. Survives into the report."""

    EMPIRICAL_HISTORICAL = "EMPIRICAL_HISTORICAL"  # measured frequency, supplied
    VALIDATED_MODEL = "VALIDATED_MODEL"  # reserved; nothing qualifies today
    QUALITATIVE_LLM = "QUALITATIVE_LLM"  # ordinal judgment, not a probability
    UNAVAILABLE = "UNAVAILABLE"


class QualitativeLikelihood(StrEnum):
    """The ONLY likelihood scale the model may use. Deliberately ordinal."""

    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    UNAVAILABLE = "UNAVAILABLE"


class Directionality(StrEnum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    MIXED = "MIXED"
    UNCLEAR = "UNCLEAR"


class CatalystType(StrEnum):
    EARNINGS = "EARNINGS"
    GUIDANCE_UPDATE = "GUIDANCE_UPDATE"
    INVESTOR_DAY = "INVESTOR_DAY"
    PRODUCT = "PRODUCT"
    REGULATORY = "REGULATORY"
    LEGAL = "LEGAL"
    CLINICAL_OR_FDA = "CLINICAL_OR_FDA"
    CONFERENCE = "CONFERENCE"
    LOCKUP = "LOCKUP"
    INDEX_CHANGE = "INDEX_CHANGE"
    MACRO = "MACRO"
    CONTRACT_DECISION = "CONTRACT_DECISION"
    CORPORATE_ACTION = "CORPORATE_ACTION"
    OTHER = "OTHER"


class SourceType(StrEnum):
    """Quality hierarchy, best first. Assigned by Python from the domain."""

    SEC_FILING = "SEC_FILING"
    COMPANY_IR = "COMPANY_IR"
    EARNINGS_CALL = "EARNINGS_CALL"
    GOVERNMENT = "GOVERNMENT"
    WIRE_NEWS = "WIRE_NEWS"
    FINANCIAL_NEWS = "FINANCIAL_NEWS"
    INDUSTRY_PUBLICATION = "INDUSTRY_PUBLICATION"
    SECONDARY_COMMENTARY = "SECONDARY_COMMENTARY"
    UNKNOWN = "UNKNOWN"


class ResearchStatus(StrEnum):
    """Outcome of an attempt. Never a property of the model's output."""

    OK = "OK"
    CACHED = "CACHED"
    DISABLED = "DISABLED"
    FAILED = "FAILED"


# -------------------------------------------------------------- building block
class Claim(_Strict):
    """One statement, classified, with its supporting source IDs."""

    text: str = Field(description="One self-contained statement. No URLs.")
    claim_type: ClaimType
    source_ids: list[str] = Field(
        default_factory=list,
        description=(
            "IDs from the supplied source catalogue, e.g. ['S3','S7']. "
            "Required for FACT. Never invent an ID and never write a URL."
        ),
    )


class Scenario(_Strict):
    thesis: str
    likelihood_type: LikelihoodType
    likelihood: QualitativeLikelihood
    likelihood_rationale: str = Field(
        description="Why this ordinal band. No percentages, no expected returns."
    )
    key_assumptions: list[str]
    evidence: list[Claim]
    what_would_confirm: list[str]
    what_would_invalidate: list[str]


class Catalyst(_Strict):
    name: str
    date: str | None = Field(description="ISO date if verified, else null. Never guess.")
    date_is_verified: bool
    type: CatalystType
    directionality: Directionality
    potential_impact: str
    why_it_matters: str
    source_ids: list[str]


class WatchItem(_Strict):
    metric_or_event: str
    condition: str = Field(description="The specific observable that would trip this.")
    why_it_matters: str
    expected_date: str | None


class PriceActionAnalysis(_Strict):
    observed_move: str = Field(
        description="Restate the supplied move. Do not recompute or alter numbers."
    )
    verified_drivers: list[Claim]
    likely_drivers: list[Claim]
    unexplained_components: list[str]
    attribution_confidence: QualitativeLikelihood
    no_single_catalyst_identified: bool


class EarningsAnalysis(_Strict):
    latest_report_summary: str | None
    key_beats: list[Claim]
    key_misses: list[Claim]
    margins: str | None
    segments: list[Claim]
    guidance: str | None
    guidance_direction: Directionality
    management_commentary: list[Claim]
    expectation_context: str | None


class CurrentSetup(_Strict):
    quantitative_setup: str = Field(
        description="Read back the supplied quant state. Interpret; never recompute."
    )
    market_environment: str
    fundamental_setup: str
    catalyst_setup: str


class ThesisChanges(_Strict):
    positive_changes: list[Claim]
    negative_changes: list[Claim]
    unchanged: list[str]


class QuantVsQual(_Strict):
    """The core synthesis. Where the two evidence streams agree and collide."""

    confirmations: list[Claim]
    contradictions: list[Claim]
    unresolved: list[str]
    what_matters_most: str
    what_could_change_the_conclusion: str


class ActionAssessment(_Strict):
    supports_add: list[Claim]
    supports_hold: list[Claim]
    supports_trim: list[Claim]
    supports_exit: list[Claim]
    add_if: list[str]
    hold_while: list[str]
    trim_if: list[str]
    exit_if: list[str]
    strongest_counterargument: str
    key_decision_variable: str


class IntegratedView(_Strict):
    """The model's own view, held SEPARATELY from the deterministic action."""

    llm_research_view: str = Field(
        description=(
            "ADD / HOLD / TRIM / EXIT / ABSTAIN as the qualitative research alone "
            "would suggest for the SECURITY. This never overwrites the "
            "deterministic action; both are shown."
        )
    )
    agrees_with_deterministic_action: bool
    disagreement_explanation: str | None
    integrated_decision_commentary: str
    position_sizing_note: str = Field(
        description=(
            "Sizing/concentration commentary kept separate from the security "
            "thesis. Never invent a portfolio limit the owner has not supplied."
        )
    )
    overall_uncertainty: QualitativeLikelihood
    uncertainty_explanation: str


class InvestmentResearchResult(_Strict):
    """The full structured research object returned by the extraction call."""

    symbol: str
    company_summary: str
    what_matters_now: list[str] = Field(description="At most five bullets.")
    current_setup: CurrentSetup
    recent_developments: list[Claim]
    earnings_analysis: EarningsAnalysis
    price_action_analysis: PriceActionAnalysis
    catalysts: list[Catalyst]
    competitive_context: list[Claim]
    analyst_expectations: list[Claim]
    bull_case: Scenario
    base_case: Scenario
    bear_case: Scenario
    risk_factors: list[Claim]
    thesis_changes: ThesisChanges
    quant_vs_qual: QuantVsQual
    action_assessment: ActionAssessment
    integrated_view: IntegratedView
    watch_items: list[WatchItem]
    limitations: list[str]
    cited_source_ids: list[str] = Field(description="Every source ID referenced anywhere above.")


# --------------------------------------------- portfolio-level synthesis object
class PortfolioFlag(_Strict):
    symbol: str
    reason: str
    detail: str


class PortfolioCluster(_Strict):
    name: str
    symbols: list[str]
    shared_exposure: str
    why_it_matters: str


class PortfolioResearchResult(_Strict):
    as_of: str
    highest_priority_reviews: list[PortfolioFlag]
    clustered_risks: list[PortfolioCluster]
    shared_macro_exposures: list[PortfolioCluster]
    upcoming_catalyst_clusters: list[PortfolioCluster]
    cross_position_contradictions: list[PortfolioFlag]
    quant_qual_disagreements: list[PortfolioFlag]
    large_weights_deteriorating: list[PortfolioFlag]
    attractive_but_size_constrained: list[PortfolioFlag]
    summary: str
    limitations: list[str]


# ------------------------------------------------- numeric-probability policing
# Targets FORWARD-LOOKING probability and expected-return phrasing only. Ordinary
# reported percentages ("revenue grew 12%", "gross margin 34%") must survive,
# because scrubbing them would gut legitimate research.
_PROB_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "percent-likelihood",
        re.compile(
            r"\b\d{1,3}(?:\.\d+)?\s*%\s*(?:chance|probability|odds|likelihood|"
            r"likely|confident|confidence)\b",
            re.I,
        ),
    ),
    (
        "likelihood-of-percent",
        re.compile(
            r"\b(?:chance|probability|odds|likelihood)\s+(?:of|that|for|is|:|=)"
            r"[^.;\n]{0,80}?\b\d{1,3}(?:\.\d+)?\s*%",
            re.I,
        ),
    ),
    (
        "decimal-probability",
        # The keyword and the number may be separated by a few words
        # ("the probability of upside is 0.62"), so allow a bounded gap.
        re.compile(
            r"\b(?:chance|probability|odds|likelihood)\b[^.;\n]{0,60}?"
            r"\b(?:is|of|at|near|around|about|=|:)\s*0?\.\d+",
            re.I,
        ),
    ),
    (
        "bare-decimal-probability",
        re.compile(r"\bp\s*(?:=|:)\s*0?\.\d+", re.I),
    ),
    (
        "expected-return",
        re.compile(
            r"\bexpected\s+(?:return|value|move|gain|loss|upside|downside)\b"
            r"[^.;\n]{0,60}?[-+]?\d",
            re.I,
        ),
    ),
    (
        "probability-weighted",
        re.compile(r"\bprobability[- ]weighted\b", re.I),
    ),
    (
        "p-up-notation",
        re.compile(r"\bp\s*\(\s*(?:up|down|gain|loss)\s*\)", re.I),
    ),
    (
        "n-in-n-odds",
        re.compile(r"\b\d\s+(?:in|out\s+of)\s+\d{1,2}\s+(?:chance|odds|likelihood)\b", re.I),
    ),
)


def numeric_probability_violations(text: str) -> list[str]:
    """Return the names of any forward-probability patterns present in ``text``.

    Empty list means the text is compliant with the probability policy.
    """
    if not text:
        return []
    return [name for name, pattern in _PROB_PATTERNS if pattern.search(text)]
