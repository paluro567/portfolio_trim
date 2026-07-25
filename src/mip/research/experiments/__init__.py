"""Generalized quantitative research framework.

Permanent infrastructure for evaluating experimental evidence models under the
same rigorous, pre-registered validation the Conditional Probability Engine
received. This package is a NEW layer built alongside the existing
``mip/validation`` primitives (which it reuses) — it does not replace them, and
it does not change any production scoring behavior.

Stage 1 surface: the code-only research registry (the single declarative source
of truth for every experiment) plus derived views that are asserted equal to the
existing registration constants (``ALL_MODELS`` / ``KNOWN_MODELS`` /
``SHADOW_MODELS`` / ``OVERLAPPING_PAIRS``). Consolidation onto the registry is a
later, separately-gated step; for now the registry is additive.
"""

from mip.research.experiments.ablation import (
    analyze_ablation,
    variant_metrics,
    variant_names,
)
from mip.research.experiments.harness import (
    CaptureStats,
    ModelSet,
    WalkForwardHarness,
    WalkForwardPlan,
)
from mip.research.experiments.manifest import (
    HARNESS_VERSION,
    ReproducibilityManifest,
    Unavailable,
    config_hash,
    file_hash,
    git_state,
    runtime_environment,
)
from mip.research.experiments.registry import (
    EXPERIMENTS,
    ExperimentSpec,
    InformationFamily,
    LifecycleStatus,
    ModelFamily,
    PromotionCriterion,
    Role,
    conformance_report,
    derived_all_models,
    derived_known_models,
    derived_overlapping_pairs,
    derived_shadow_models,
    get_experiment,
    validate_registry,
)
from mip.research.experiments.report import (
    CriterionResult,
    CriterionStatus,
    evaluate_promotion,
    promotion_recommendation,
    render_report,
)

__all__ = [
    "EXPERIMENTS",
    "HARNESS_VERSION",
    "CaptureStats",
    "CriterionResult",
    "CriterionStatus",
    "ExperimentSpec",
    "ModelSet",
    "WalkForwardHarness",
    "WalkForwardPlan",
    "analyze_ablation",
    "evaluate_promotion",
    "promotion_recommendation",
    "render_report",
    "variant_metrics",
    "variant_names",
    "InformationFamily",
    "LifecycleStatus",
    "ModelFamily",
    "PromotionCriterion",
    "ReproducibilityManifest",
    "Role",
    "Unavailable",
    "conformance_report",
    "config_hash",
    "derived_all_models",
    "derived_known_models",
    "derived_overlapping_pairs",
    "derived_shadow_models",
    "file_hash",
    "git_state",
    "get_experiment",
    "runtime_environment",
    "validate_registry",
]
