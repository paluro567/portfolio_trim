"""Stage 1 — additive research registry: conformance + validation.

The registry must reproduce the existing registration constants EXACTLY (it is
additive; scoring still reads the legacy constants). These tests are the safety
net that lets a later stage consolidate onto the registry.
"""

from dataclasses import replace
from datetime import date

import pytest

from mip.core.exceptions import ConfigurationError
from mip.engine.evidence import OVERLAPPING_PAIRS, SHADOW_MODELS
from mip.models import ALL_MODELS
from mip.models.evidence import KNOWN_MODELS
from mip.research.experiments import (
    EXPERIMENTS,
    ExperimentSpec,
    LifecycleStatus,
    Role,
    conformance_report,
    derived_all_models,
    derived_known_models,
    derived_overlapping_pairs,
    derived_shadow_models,
    get_experiment,
    validate_registry,
)
from mip.research.experiments.registry import InformationFamily, ModelFamily


def test_registry_is_structurally_valid() -> None:
    validate_registry()  # unique ids, resolvable overlaps


def test_conformance_with_legacy_constants() -> None:
    report = conformance_report()
    assert report["conformant"], report["checks"]


def test_derived_all_models_matches() -> None:
    assert derived_all_models() == ALL_MODELS


def test_derived_known_models_matches() -> None:
    assert derived_known_models() == KNOWN_MODELS


def test_derived_shadow_models_matches() -> None:
    assert derived_shadow_models() == SHADOW_MODELS
    assert derived_shadow_models() == frozenset({"historical_analogues", "conditional_probability"})


def test_derived_overlapping_pairs_matches() -> None:
    assert derived_overlapping_pairs() == set(OVERLAPPING_PAIRS)


def test_seven_officials_are_production() -> None:
    production = [s.experiment_id for s in EXPERIMENTS if s.role is Role.PRODUCTION]
    assert len(production) == 7
    assert "historical_analogues" not in production
    assert "conditional_probability" not in production


def test_analogue_and_cpe_are_rejected_shadow() -> None:
    for eid in ("historical_analogues", "conditional_probability"):
        spec = get_experiment(eid)
        assert spec.role is Role.SHADOW
        assert spec.status is LifecycleStatus.REJECTED  # scientifically accurate, not production


def test_cpe_record_retains_findings() -> None:
    cpe = get_experiment("conditional_probability")
    assert cpe.validation_plan_reference == "docs/CPE_VALIDATION_PLAN.md"
    assert "REPORT.md" in (cpe.report_reference or "")
    assert "inverted" in cpe.notes.lower()
    assert cpe.promotion_criteria  # criteria preserved for mechanical evaluation later


def _minimal(**overrides) -> dict:
    base = dict(
        experiment_id="interest_rate_sensitivity",
        display_name="x",
        version=1,
        model_cls=ALL_MODELS[0],
        hypothesis="h",
        null_hypothesis="n",
        model_family=ModelFamily.REGIME,
        information_family=InformationFamily.RATES,
        required_data_sources=("prices",),
        supported_horizons=("1m",),
        status=LifecycleStatus.MONITORING,
        role=Role.PRODUCTION,
        owner="o",
        introduction_date=date(2026, 1, 1),
    )
    base.update(overrides)
    return base


def test_id_must_match_model_name() -> None:
    with pytest.raises(ConfigurationError, match="!= model_cls.name"):
        ExperimentSpec(**_minimal(experiment_id="wrong_name"))


def test_production_role_requires_production_status() -> None:
    with pytest.raises(ConfigurationError, match="production role"):
        ExperimentSpec(**_minimal(status=LifecycleStatus.SHADOW, role=Role.PRODUCTION))


def test_shadow_role_rejects_production_status() -> None:
    with pytest.raises(ConfigurationError, match="shadow role"):
        ExperimentSpec(**_minimal(status=LifecycleStatus.PROMOTED, role=Role.SHADOW))


def test_unknown_horizon_rejected() -> None:
    with pytest.raises(ConfigurationError, match="unknown horizons"):
        ExperimentSpec(**_minimal(supported_horizons=("1m", "9y")))


def test_cannot_overlap_itself() -> None:
    with pytest.raises(ConfigurationError, match="overlap itself"):
        ExperimentSpec(**_minimal(overlaps=frozenset({"interest_rate_sensitivity"})))


def test_duplicate_ids_rejected() -> None:
    dup = replace(EXPERIMENTS[0])
    with pytest.raises(ConfigurationError, match="duplicate experiment ids"):
        validate_registry((*EXPERIMENTS, dup))


def test_unresolvable_overlap_rejected() -> None:
    spec = replace(get_experiment("valuation"), overlaps=frozenset({"nonexistent_model"}))
    others = tuple(s for s in EXPERIMENTS if s.experiment_id != "valuation")
    with pytest.raises(ConfigurationError, match="unknown experiments"):
        validate_registry((*others, spec))
