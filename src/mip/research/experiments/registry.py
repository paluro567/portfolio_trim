"""The code-only research registry: the declarative source of truth for every
experiment (production benchmark components and shadow research experiments).

Stage-1 discipline (additive): this module DEFINES the registry and exposes
views derived from it, but does NOT yet replace the existing registration
constants. ``conformance_report`` proves the derived views equal
``ALL_MODELS`` / ``KNOWN_MODELS`` / ``SHADOW_MODELS`` / ``OVERLAPPING_PAIRS`` so a
later, separately-gated step can consolidate onto the registry with confidence.

Nothing here influences scoring. Registering an experiment does not make it
score; the existing decision engine still reads the legacy constants until
consolidation. An experiment reaches production ONLY through a recorded
promotion decision (a later stage), never by editing a status by hand and never
by its own standalone metrics.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from mip.core.exceptions import ConfigurationError
from mip.models import (
    ALL_MODELS,
    ConditionalProbabilityModel,
    EarningsBehaviorModel,
    HistoricalAnalogueModel,
    IntelligenceModel,
    InterestRateModel,
    MacroRegimeModel,
    MomentumExhaustionModel,
    RelativeStrengthModel,
    SectorRotationModel,
    ValuationModel,
)
from mip.models.evidence import HORIZONS


class LifecycleStatus(StrEnum):
    """The formal experiment lifecycle. ``status`` records where an experiment
    sits scientifically; it is orthogonal to ``Role`` (which governs scoring)."""

    PROPOSED = "proposed"
    APPROVED = "approved"
    IMPLEMENTED = "implemented"
    SHADOW = "shadow"
    VALIDATING = "validating"
    REJECTED = "rejected"
    PROMOTED = "promoted"
    MONITORING = "monitoring"
    RETIRED = "retired"


class Role(StrEnum):
    """Scoring participation. PRODUCTION components define the official combined
    score; SHADOW experiments are evaluated and reported but excluded from it."""

    PRODUCTION = "production"
    SHADOW = "shadow"


# Roles that a status is allowed to pair with (a shadow status can never be a
# production role, and vice versa) — the guard against accidental self-promotion.
_PRODUCTION_STATUSES = frozenset({LifecycleStatus.PROMOTED, LifecycleStatus.MONITORING})
_SHADOW_STATUSES = frozenset(
    {
        LifecycleStatus.PROPOSED,
        LifecycleStatus.APPROVED,
        LifecycleStatus.IMPLEMENTED,
        LifecycleStatus.SHADOW,
        LifecycleStatus.VALIDATING,
        LifecycleStatus.REJECTED,
        LifecycleStatus.RETIRED,
    }
)


class ModelFamily(StrEnum):
    """How the model reasons — deliberately coarse and open to extension."""

    REGIME = "regime"  # conditional-regime studies over one symbol's history
    TECHNICAL = "technical"  # price/return structure
    FUNDAMENTAL = "fundamental"
    EVENT = "event"  # catalyst/earnings-anchored
    SIMILARITY = "similarity"  # nearest-neighbour analogue
    CROSS_SECTIONAL = "cross_sectional"  # pooled cross-symbol conditional history


class InformationFamily(StrEnum):
    """The information source the model exploits — the axis along which future
    experiments diversify (a NEW information family needs new PIT ingestion +
    features, never merely a registry entry)."""

    RATES = "rates"
    MACRO = "macro"
    SECTOR = "sector"
    PRICE_TECHNICAL = "price_technical"
    RELATIVE_STRENGTH = "relative_strength"
    VALUATION = "valuation"
    EARNINGS = "earnings"
    HISTORICAL_SIMILARITY = "historical_similarity"
    CROSS_SECTIONAL_CONDITIONAL = "cross_sectional_conditional"


@dataclass(frozen=True)
class PromotionCriterion:
    """One promotion gate. ``statement`` is always human-readable; the optional
    machine fields let a later stage evaluate the criterion mechanically against
    a results object. Absent machine fields ⇒ evaluated qualitatively."""

    id: str
    statement: str
    metric: str | None = None
    comparator: str | None = None  # '>', '>=', '<', '<=', 'ci_low>', ...
    threshold: float | None = None
    horizon: str | None = None


@dataclass(frozen=True)
class ExperimentSpec:
    """The declarative record for one experiment. Immutable; the historical
    record of a rejected/retired experiment must never be silently rewritten."""

    experiment_id: str  # unique; must equal model_cls.name
    display_name: str
    version: int
    model_cls: type[IntelligenceModel]
    hypothesis: str
    null_hypothesis: str
    model_family: ModelFamily
    information_family: InformationFamily
    required_data_sources: tuple[str, ...]
    supported_horizons: tuple[str, ...]
    status: LifecycleStatus
    role: Role
    owner: str
    introduction_date: date
    overlaps: frozenset[str] = frozenset()  # partner ids sharing information (overlap prior)
    validation_plan_reference: str | None = None
    report_reference: str | None = None
    promotion_criteria: tuple[PromotionCriterion, ...] = ()
    ablation_dimensions: tuple[str, ...] = ()
    notes: str = ""
    limitations: str = ""

    def __post_init__(self) -> None:
        if not self.experiment_id:
            raise ConfigurationError("experiment_id must be non-empty")
        if getattr(self.model_cls, "name", None) != self.experiment_id:
            raise ConfigurationError(
                f"experiment_id {self.experiment_id!r} != model_cls.name "
                f"{getattr(self.model_cls, 'name', None)!r}"
            )
        if self.version < 1:
            raise ConfigurationError(f"{self.experiment_id}: version must be >= 1")
        unknown = set(self.supported_horizons) - set(HORIZONS)
        if unknown:
            raise ConfigurationError(f"{self.experiment_id}: unknown horizons {sorted(unknown)}")
        if self.role is Role.PRODUCTION and self.status not in _PRODUCTION_STATUSES:
            raise ConfigurationError(
                f"{self.experiment_id}: production role requires status in "
                f"{sorted(s.value for s in _PRODUCTION_STATUSES)}, got {self.status.value!r}"
            )
        if self.role is Role.SHADOW and self.status not in _SHADOW_STATUSES:
            raise ConfigurationError(
                f"{self.experiment_id}: shadow role requires a non-production status, "
                f"got {self.status.value!r}"
            )
        if self.experiment_id in self.overlaps:
            raise ConfigurationError(f"{self.experiment_id}: cannot overlap itself")

    @property
    def is_shadow(self) -> bool:
        return self.role is Role.SHADOW


# -- the registry ---------------------------------------------------------------

_SEVEN = (
    (
        "interest_rate_sensitivity",
        "Interest Rate Sensitivity",
        InterestRateModel,
        ModelFamily.REGIME,
        InformationFamily.RATES,
        ("prices", "macro"),
        {"macro_regime"},
    ),
    (
        "sector_rotation",
        "Sector Rotation",
        SectorRotationModel,
        ModelFamily.REGIME,
        InformationFamily.SECTOR,
        ("prices",),
        {"relative_strength"},
    ),
    (
        "momentum_exhaustion",
        "Momentum Exhaustion",
        MomentumExhaustionModel,
        ModelFamily.TECHNICAL,
        InformationFamily.PRICE_TECHNICAL,
        ("prices",),
        {"relative_strength"},
    ),
    (
        "valuation",
        "Valuation",
        ValuationModel,
        ModelFamily.FUNDAMENTAL,
        InformationFamily.VALUATION,
        ("prices", "fundamentals"),
        set(),
    ),
    (
        "earnings_behavior",
        "Earnings Behavior",
        EarningsBehaviorModel,
        ModelFamily.EVENT,
        InformationFamily.EARNINGS,
        ("prices", "earnings"),
        set(),
    ),
    (
        "macro_regime",
        "Macro Regime",
        MacroRegimeModel,
        ModelFamily.REGIME,
        InformationFamily.MACRO,
        ("prices", "macro"),
        set(),
    ),
    (
        "relative_strength",
        "Relative Strength",
        RelativeStrengthModel,
        ModelFamily.TECHNICAL,
        InformationFamily.RELATIVE_STRENGTH,
        ("prices",),
        set(),
    ),
)


def _production_seven() -> list[ExperimentSpec]:
    specs = []
    for eid, name, cls, mf, inf, sources, overlaps in _SEVEN:
        specs.append(
            ExperimentSpec(
                experiment_id=eid,
                display_name=name,
                version=getattr(cls, "version", 1),
                model_cls=cls,
                hypothesis=(
                    f"{name} historical conditional-regime evidence carries information "
                    "about a holding's forward returns."
                ),
                null_hypothesis=f"{name} adds no forward-return information.",
                model_family=mf,
                information_family=inf,
                required_data_sources=sources,
                supported_horizons=HORIZONS,
                status=LifecycleStatus.MONITORING,
                role=Role.PRODUCTION,
                owner="platform",
                introduction_date=date(2026, 7, 11),
                overlaps=frozenset(overlaps),
                notes="Established production benchmark component (predates the framework).",
            )
        )
    return specs


_ANALOGUE = ExperimentSpec(
    experiment_id="historical_analogues",
    display_name="Historical Analogues",
    version=1,
    model_cls=HistoricalAnalogueModel,
    hypothesis=(
        "The combined market/sector/company/catalyst state most similar to today, in the "
        "same stock's history, predicts its forward returns."
    ),
    null_hypothesis="Nearest-analogue outcomes add no out-of-sample forward-return information.",
    model_family=ModelFamily.SIMILARITY,
    information_family=InformationFamily.HISTORICAL_SIMILARITY,
    required_data_sources=("prices", "macro", "fundamentals", "earnings"),
    supported_horizons=HORIZONS,
    status=LifecycleStatus.REJECTED,
    role=Role.SHADOW,
    owner="research",
    introduction_date=date(2026, 7, 17),
    overlaps=frozenset(eid for eid, *_ in _SEVEN),
    validation_plan_reference="data/validation/analogue_v1/",
    report_reference="data/validation/analogue_v1/",
    ablation_dimensions=("market", "sector", "company", "catalyst"),
    notes=(
        "Walk-forward + embargoed revalidation: below coin-flip at <=1m, long-horizon promise "
        "was leakage, confidence inverted; company domain harmful, market domain = era "
        "persistence. Demoted to shadow; not promotable."
    ),
    limitations=(
        "Cross-sectional era persistence; inverted confidence; not independent of "
        "the regime models."
    ),
)


_CPE = ExperimentSpec(
    experiment_id="conditional_probability",
    display_name="Conditional Probability Engine",
    version=1,
    model_cls=ConditionalProbabilityModel,
    hypothesis=(
        "Pooled cross-sectional history under a predeclared conjunction of current market/"
        "sector/company/catalyst conditions provides incremental forward-return information "
        "beyond the seven-model system."
    ),
    null_hypothesis=(
        "The conditional engine adds no incremental predictive information; combined - baseline "
        "<= 0 within block-bootstrap noise, and/or standalone <= naive, and/or miscalibrated, "
        "and/or confidence does not discriminate."
    ),
    model_family=ModelFamily.CROSS_SECTIONAL,
    information_family=InformationFamily.CROSS_SECTIONAL_CONDITIONAL,
    required_data_sources=("prices", "macro", "fundamentals", "earnings"),
    supported_horizons=HORIZONS,
    status=LifecycleStatus.REJECTED,
    role=Role.SHADOW,
    owner="research",
    introduction_date=date(2026, 7, 22),
    # the CPE reuses the same feature information as every other model (incl. the
    # analogue) -> conservative overlap prior against ALL of them.
    overlaps=frozenset({*(eid for eid, *_ in _SEVEN), "historical_analogues"}),
    validation_plan_reference="docs/CPE_VALIDATION_PLAN.md",
    report_reference="data/validation/conditional_v1/REPORT.md",
    promotion_criteria=(
        PromotionCriterion(
            "incremental_1m",
            "Combined - baseline directional-accuracy improvement CI lower bound > 0 at 1m.",
            metric="delta_direction_accuracy",
            comparator="ci_low>",
            threshold=0.0,
            horizon="1m",
        ),
        PromotionCriterion(
            "calibration",
            "Holdout ECE <= 0.10 at the primary horizon.",
            metric="ece",
            comparator="<=",
            threshold=0.10,
            horizon="1m",
        ),
        PromotionCriterion(
            "confidence_discriminates",
            "High-confidence accuracy exceeds low-confidence accuracy (non-inverted).",
            metric="confidence_delta",
            comparator=">",
            threshold=0.0,
            horizon="1m",
        ),
    ),
    ablation_dimensions=("market", "sector", "company", "catalyst"),
    notes=(
        "Rejected: incremental CI includes 0 at every horizon; ECE ~0.14 (fails 0.10); confidence "
        "INVERTED (high-conf accuracy < low-conf); forced-scope ablation shows accuracy falls as "
        "conditioning is added -> the standalone edge is market-era persistence, not conditional "
        "skill. Stays shadow."
    ),
    limitations=(
        "Survivorship-biased universe; no PIT fundamentals (valuation inert); catalyst domain "
        "never forms; edge concentrated in the smallest-sample cells."
    ),
)


EXPERIMENTS: tuple[ExperimentSpec, ...] = (*_production_seven(), _ANALOGUE, _CPE)


# -- lookups & validation -------------------------------------------------------


def get_experiment(experiment_id: str) -> ExperimentSpec:
    for spec in EXPERIMENTS:
        if spec.experiment_id == experiment_id:
            return spec
    raise ConfigurationError(f"unknown experiment {experiment_id!r}")


def validate_registry(experiments: tuple[ExperimentSpec, ...] = EXPERIMENTS) -> None:
    """Structural integrity: unique ids, resolvable overlaps."""
    ids = [s.experiment_id for s in experiments]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ConfigurationError(f"duplicate experiment ids: {duplicates}")
    known = set(ids)
    for spec in experiments:
        missing = spec.overlaps - known
        if missing:
            raise ConfigurationError(
                f"{spec.experiment_id}: overlaps reference unknown experiments {sorted(missing)}"
            )


# -- derived views (asserted equal to the legacy constants) ---------------------


def derived_all_models() -> tuple[type[IntelligenceModel], ...]:
    return tuple(s.model_cls for s in EXPERIMENTS)


def derived_known_models() -> tuple[str, ...]:
    return tuple(s.experiment_id for s in EXPERIMENTS)


def derived_shadow_models() -> frozenset[str]:
    return frozenset(s.experiment_id for s in EXPERIMENTS if s.is_shadow)


def derived_overlapping_pairs() -> frozenset[frozenset[str]]:
    pairs: set[frozenset[str]] = set()
    for spec in EXPERIMENTS:
        for partner in spec.overlaps:
            pairs.add(frozenset({spec.experiment_id, partner}))
    return frozenset(pairs)


def conformance_report() -> dict:
    """Compare every derived view to the live legacy constant. Imports the
    legacy sources lazily to keep this module import-light and cycle-free."""
    from mip.engine.evidence import OVERLAPPING_PAIRS, SHADOW_MODELS
    from mip.models.evidence import KNOWN_MODELS

    validate_registry()
    checks = {
        "all_models": derived_all_models() == ALL_MODELS,
        "known_models": derived_known_models() == KNOWN_MODELS,
        "shadow_models": derived_shadow_models() == SHADOW_MODELS,
        "overlapping_pairs": derived_overlapping_pairs() == set(OVERLAPPING_PAIRS),
    }
    return {
        "conformant": all(checks.values()),
        "checks": checks,
        "legacy": {
            "all_models": [c.name for c in ALL_MODELS],
            "known_models": list(KNOWN_MODELS),
            "shadow_models": sorted(SHADOW_MODELS),
            "overlapping_pairs": sorted(sorted(p) for p in OVERLAPPING_PAIRS),
        },
    }
