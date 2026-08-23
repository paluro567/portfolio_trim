"""Historical calibration: the gate, the lookup, and the prohibitions.

The prohibitions are the point of this file. Calibration is the channel most
likely to produce a confident-looking number that means nothing, so the tests
here are mostly about what must NOT happen:

* no LLM output may enter the historical channel, at any depth;
* no statistic may be shown for an unavailable or rejected calibration;
* no survivor-only universe may pass the gate;
* research may never overwrite a deterministic action.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from mip.calibration.contracts import (
    HORIZONS,
    HorizonCalibration,
    ValidationStatus,
    unavailable,
)
from mip.calibration.lookup import CalibrationLookup
from mip.calibration.readiness import Check, ReadinessReport
from mip.calibration.signal_definition import current_signal_definition
from mip.calibration.source import (
    REQUIRED_DATASETS,
    HistoricalSourceUnavailableError,
    blocked_source,
)


# ==========================================================================
# PROHIBITION 1 — NO LLM INPUT IN THE HISTORICAL CHANNEL
# ==========================================================================
def test_calibration_package_never_imports_the_research_layer():
    """Hindsight contamination is prevented structurally, not by convention."""
    offenders = []
    for path in Path("src/mip/calibration").glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            module = ""
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
            elif isinstance(node, ast.Import):
                module = ",".join(a.name for a in node.names)
            if "research_assistant" in module or "openai" in module.lower():
                offenders.append(f"{path.name}: {module}")
    assert offenders == [], f"calibration must not touch the LLM layer: {offenders}"


def test_calibration_contract_has_no_llm_shaped_fields():
    """No conviction, bias, setup, narrative or rationale in a historical stat."""
    forbidden = {
        "conviction",
        "bias",
        "setup",
        "rationale",
        "narrative",
        "thesis",
        "commentary",
        "summary",
        "research",
    }
    fields = set(HorizonCalibration.__dataclass_fields__)
    assert not (fields & forbidden), f"LLM-shaped fields in calibration: {fields & forbidden}"


def test_calibration_dict_is_pure_statistics():
    cal = unavailable("6m", "POSITIVE", "gate failed")
    body = cal.to_dict()
    for key in body:
        assert "llm" not in key and "research" not in key


# ==========================================================================
# PROHIBITION 2 — NOTHING SHOWN WHEN NOTHING IS EARNED
# ==========================================================================
def test_unavailable_calibration_shows_a_reason_not_a_number():
    cal = unavailable("6m", "POSITIVE", "no survivorship-clean data")
    assert not cal.available
    assert cal.sample_n is None
    assert "unavailable" in cal.summary_line()
    assert "%" not in cal.summary_line()


def test_rejected_calibration_is_not_presented():
    cal = HorizonCalibration(
        horizon="1m",
        signal_state="POSITIVE",
        validation_status=ValidationStatus.REJECTED,
        sample_n=500,
        positive_return_rate=0.63,
    )
    assert not cal.validation_status.presentable
    assert not cal.available
    assert "REJECTED" in cal.summary_line()
    assert "63" not in cal.summary_line(), "a rejected result must not show its figures"


def test_only_validated_is_authoritative():
    assert ValidationStatus.VALIDATED.authoritative
    for status in (
        ValidationStatus.PROMISING_BUT_UNPROVEN,
        ValidationStatus.INCONCLUSIVE,
        ValidationStatus.REJECTED,
        ValidationStatus.UNAVAILABLE,
    ):
        assert not status.authoritative


def test_presentable_statuses_carry_their_status_label():
    cal = HorizonCalibration(
        horizon="6m",
        signal_state="POSITIVE",
        validation_status=ValidationStatus.PROMISING_BUT_UNPROVEN,
        sample_n=412,
        positive_return_rate=0.63,
        spy_outperformance_rate=0.58,
        median_forward_return=0.084,
    )
    line = cal.summary_line()
    assert "63% positive" in line
    assert "58% beat SPY" in line
    assert "median +8.4%" in line
    assert "N=412" in line
    assert "PROMISING_BUT_UNPROVEN" in line


def test_summary_never_uses_forecast_language():
    cal = HorizonCalibration(
        horizon="6m",
        signal_state="POSITIVE",
        validation_status=ValidationStatus.VALIDATED,
        sample_n=412,
        positive_return_rate=0.63,
    )
    line = cal.summary_line().lower()
    for word in ("chance", "probability", "likely", "expected", "forecast", "will"):
        assert word not in line, f"forecast language leaked: {word}"


# ==========================================================================
# THE READINESS GATE
# ==========================================================================
def _failing_report() -> ReadinessReport:
    return ReadinessReport(
        checks=[
            Check("survivorship_control", False, "0 delisted", "delisted present", "survivor-only"),
            Check("pit_fundamentals", False, "3 as-of dates", "vintages", "snapshot only"),
            Check("price_history_depth", True, "537 deep", "100+", None),
        ]
    )


def test_gate_fails_when_any_check_fails():
    report = _failing_report()
    assert not report.gate_passed
    assert len(report.blockers) == 2
    assert "survivor-only" in report.reason()


def test_gate_passes_only_when_every_check_passes():
    report = ReadinessReport(
        checks=[Check("a", True, "", "", None), Check("b", True, "", "", None)]
    )
    assert report.gate_passed
    assert report.reason() == ""


def test_failing_gate_produces_an_unavailable_lookup():
    report = _failing_report()
    lookup = CalibrationLookup.unavailable_because(report.reason())
    assert not lookup.available
    cal = lookup.lookup("POSITIVE", "6m")
    assert cal.validation_status is ValidationStatus.UNAVAILABLE
    assert "survivor-only" in (cal.unavailable_reason or "")


def test_gate_reason_reaches_every_horizon():
    lookup = CalibrationLookup.unavailable_because("gate failed")
    cals = lookup.for_all_horizons(dict.fromkeys(HORIZONS, "POSITIVE"))
    assert set(cals) == set(HORIZONS)
    assert all(c.validation_status is ValidationStatus.UNAVAILABLE for c in cals.values())


# ==========================================================================
# THE LOOKUP
# ==========================================================================
def test_lookup_refuses_artifacts_built_for_a_different_signal(tmp_path):
    """A calibration computed under other thresholds describes another signal."""
    root = tmp_path / "calibration"
    (root / "SIGNATURE_A").mkdir(parents=True)
    (root / "SIGNATURE_A" / "calibration.json").write_text(
        json.dumps({"signal_signature": "SOMETHING_ELSE", "cells": {"POSITIVE|6m": {}}})
    )
    lookup = CalibrationLookup.load("SIGNATURE_A", root=root)
    assert not lookup.available
    assert "different signal definition" in (lookup.unavailable_reason or "")


def test_lookup_reports_absence_when_no_artifact_exists(tmp_path):
    lookup = CalibrationLookup.load("SIG", root=tmp_path)
    assert not lookup.available
    assert "no calibration study has been run" in (lookup.unavailable_reason or "")


def test_lookup_gate_reason_takes_precedence_over_any_artifact(tmp_path):
    """Even a present artifact must not be served while the gate is failing."""
    root = tmp_path / "calibration"
    (root / "SIG").mkdir(parents=True)
    (root / "SIG" / "calibration.json").write_text(
        json.dumps(
            {
                "signal_signature": "SIG",
                "cells": {"POSITIVE|6m": {"validation_status": "VALIDATED", "sample_n": 9}},
            }
        )
    )
    lookup = CalibrationLookup.load("SIG", root=root, gate_reason="survivor-only universe")
    assert not lookup.available
    assert lookup.lookup("POSITIVE", "6m").validation_status is ValidationStatus.UNAVAILABLE


def test_lookup_serves_a_matching_artifact(tmp_path):
    root = tmp_path / "calibration"
    (root / "SIG").mkdir(parents=True)
    (root / "SIG" / "calibration.json").write_text(
        json.dumps(
            {
                "signal_signature": "SIG",
                "cells": {
                    "POSITIVE|6m": {
                        "validation_status": "PROMISING_BUT_UNPROVEN",
                        "sample_n": 412,
                        "positive_return_rate": 0.63,
                        "median_forward_return": 0.084,
                    }
                },
            }
        )
    )
    lookup = CalibrationLookup.load("SIG", root=root)
    assert lookup.available
    cal = lookup.lookup("POSITIVE", "6m")
    assert cal.sample_n == 412
    assert cal.validation_status is ValidationStatus.PROMISING_BUT_UNPROVEN
    # A state with no calibrated cell is absent, not approximated.
    assert lookup.lookup("NEGATIVE", "6m").validation_status is ValidationStatus.UNAVAILABLE


def test_unreadable_artifact_degrades_rather_than_raising(tmp_path):
    root = tmp_path / "calibration"
    (root / "SIG").mkdir(parents=True)
    (root / "SIG" / "calibration.json").write_text("{not json")
    lookup = CalibrationLookup.load("SIG", root=root)
    assert not lookup.available
    assert "unreadable" in (lookup.unavailable_reason or "")


# ==========================================================================
# SIGNAL DEFINITION FREEZE
# ==========================================================================
def test_signal_signature_is_stable_and_covers_the_thresholds():
    a = current_signal_definition()
    b = current_signal_definition()
    assert a.signature == b.signature
    body = a.body
    assert body["own_history_top"] == 0.70
    assert body["own_history_bottom"] == 0.30
    assert body["valuation_horizons"] == ["6m", "1y"]
    assert body["quality_voting_horizons"] == ["1y"]


def test_signal_signature_changes_when_a_threshold_changes():
    from mip.calibration.signal_definition import SignalDefinition

    base = current_signal_definition()
    altered = SignalDefinition(body={**base.body, "own_history_top": 0.75})
    assert altered.signature != base.signature


# ==========================================================================
# PROVIDER-NEUTRAL SOURCE CONTRACT
# ==========================================================================
def test_blocked_source_raises_rather_than_falling_back():
    """Falling back to the survivor-only tables would look complete and be wrong."""
    try:
        blocked_source()
    except HistoricalSourceUnavailableError as exc:
        assert "survivorship-clean" in str(exc)
    else:
        raise AssertionError("blocked_source must raise")


def test_ingestion_contract_names_every_required_dataset():
    names = {d.name for d in REQUIRED_DATASETS}
    assert names == {
        "security_master",
        "prices",
        "fundamentals_pit",
        "sector_history",
        "earnings_history",
        "corporate_actions",
        "delistings",
        "universe_membership",
    }


def test_contract_reuses_existing_tables_where_the_concept_exists():
    for dataset in REQUIRED_DATASETS:
        assert dataset.existing_table, f"{dataset.name} should map to a repo table"
        assert dataset.status, f"{dataset.name} must declare its population status"


def test_delistings_are_flagged_as_the_critical_gap():
    delistings = next(d for d in REQUIRED_DATASETS if d.name == "delistings")
    assert "delisting_return" in delistings.required_fields
    assert "EMPTY" in delistings.status
