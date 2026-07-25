"""Stage 8 — migration completeness + immutability of historical records.

The CPE and historical-analogue experiments must be migrated into the registry
with their scientifically accurate final status and their full research record
preserved. Their records must be immutable.
"""

import pytest

from mip.research.experiments.registry import LifecycleStatus, Role, get_experiment


def test_cpe_record_is_complete() -> None:
    cpe = get_experiment("conditional_probability")
    # scientifically accurate final status (NOT production)
    assert cpe.status is LifecycleStatus.REJECTED
    assert cpe.role is Role.SHADOW
    # hypothesis + null preserved
    assert cpe.hypothesis and cpe.null_hypothesis
    # validation plan + report locations
    assert cpe.validation_plan_reference == "docs/CPE_VALIDATION_PLAN.md"
    assert cpe.report_reference == "data/validation/conditional_v1/REPORT.md"
    # key findings: calibration failure, inverted confidence, ablation conclusion
    notes = cpe.notes.lower()
    assert "ece" in notes  # calibration failure recorded
    assert "inverted" in notes  # inverted-confidence finding
    assert "era persistence" in notes  # forced-scope ablation conclusion
    assert "shadow" in notes  # final decision: stays shadow
    # promotion criteria preserved for re-evaluation
    assert {c.id for c in cpe.promotion_criteria} == {
        "incremental_1m",
        "calibration",
        "confidence_discriminates",
    }
    assert cpe.ablation_dimensions == ("market", "sector", "company", "catalyst")


def test_analogue_record_is_complete() -> None:
    a = get_experiment("historical_analogues")
    assert a.status is LifecycleStatus.REJECTED
    assert a.role is Role.SHADOW
    assert a.hypothesis and a.null_hypothesis
    assert "leakage" in a.notes.lower() or "era persistence" in a.notes.lower()


def test_records_are_immutable() -> None:
    cpe = get_experiment("conditional_probability")
    with pytest.raises((AttributeError, TypeError)):  # frozen dataclass
        cpe.status = LifecycleStatus.PROMOTED  # type: ignore[misc]


def test_no_experimental_model_is_production() -> None:
    # shadow experiments must never be labelled production
    for eid in ("conditional_probability", "historical_analogues"):
        assert get_experiment(eid).role is Role.SHADOW
