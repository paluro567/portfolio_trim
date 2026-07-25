"""Stage 7 — pre-registration integrity + CLI behavior (DB-free)."""

import json
from dataclasses import replace

import pytest
from typer.testing import CliRunner

from mip.core.exceptions import ConfigurationError
from mip.research.experiments.prereg import PreRegistration, draft_from_spec
from mip.research.experiments.registry import get_experiment

runner = CliRunner()


def _prereg() -> PreRegistration:
    return draft_from_spec(
        get_experiment("conditional_probability"),
        ("2013-01-02", "2026-07-01"),
        ("2022-01-01", "2026-07-01"),
    )


# -- pre-registration integrity -------------------------------------------------


def test_freeze_sets_hash_and_verifies() -> None:
    frozen = _prereg().freeze("2026-07-24T00:00:00")
    assert frozen.is_frozen
    frozen.verify_integrity()  # no raise


def test_double_freeze_rejected() -> None:
    frozen = _prereg().freeze("2026-07-24T00:00:00")
    with pytest.raises(ConfigurationError, match="already frozen"):
        frozen.freeze("2026-07-25T00:00:00")


def test_tampering_after_freeze_detected() -> None:
    frozen = _prereg().freeze("2026-07-24T00:00:00")
    tampered = replace(frozen, hypothesis="a different, sneaky hypothesis")
    with pytest.raises(ConfigurationError, match="integrity violation"):
        tampered.verify_integrity()


def test_unfrozen_verify_rejected() -> None:
    with pytest.raises(ConfigurationError, match="not frozen"):
        _prereg().verify_integrity()


def test_prereg_round_trips(tmp_path) -> None:
    frozen = _prereg().freeze("2026-07-24T00:00:00")
    path = tmp_path / "prereg.json"
    frozen.save(path)
    loaded = PreRegistration.load(path)
    assert loaded == frozen
    loaded.verify_integrity()


# -- CLI ------------------------------------------------------------------------


def _cli():
    from mip.cli.main import app

    return app


def test_cli_list() -> None:
    result = runner.invoke(_cli(), ["research", "experiment", "list"])
    assert result.exit_code == 0
    assert "conditional_probability" in result.stdout
    assert "rejected" in result.stdout


def test_cli_show_json() -> None:
    result = runner.invoke(
        _cli(), ["research", "experiment", "show", "conditional_probability", "--json"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["role"] == "shadow"
    assert payload["status"] == "rejected"


def test_cli_conformance() -> None:
    result = runner.invoke(_cli(), ["research", "experiment", "conformance"])
    assert result.exit_code == 0
    assert "conformant" in result.stdout


def test_cli_freeze_then_check_then_reject_overwrite(tmp_path) -> None:
    args = [
        "research",
        "experiment",
        "freeze",
        "conditional_probability",
        "--start",
        "2013-01-02",
        "--end",
        "2026-07-01",
        "--holdout-start",
        "2022-01-01",
        "--artifacts",
        str(tmp_path),
    ]
    r1 = runner.invoke(_cli(), args)
    assert r1.exit_code == 0, r1.stdout
    assert (tmp_path / "conditional_probability" / "prereg.json").exists()

    check = runner.invoke(
        _cli(),
        [
            "research",
            "experiment",
            "prereg-check",
            "conditional_probability",
            "--artifacts",
            str(tmp_path),
        ],
    )
    assert check.exit_code == 0
    assert "integrity OK" in check.stdout

    # freezing again must refuse to overwrite the frozen plan
    r2 = runner.invoke(_cli(), args)
    assert r2.exit_code != 0


def test_cli_prereg_check_detects_tampering(tmp_path) -> None:
    path = tmp_path / "conditional_probability" / "prereg.json"
    _prereg().freeze("2026-07-24T00:00:00").save(path)
    payload = json.loads(path.read_text())
    payload["hypothesis"] = "tampered"  # edit content without updating the hash
    path.write_text(json.dumps(payload))
    result = runner.invoke(
        _cli(),
        [
            "research",
            "experiment",
            "prereg-check",
            "conditional_probability",
            "--artifacts",
            str(tmp_path),
        ],
    )
    assert result.exit_code != 0


def test_cli_promotion_from_results_file(tmp_path) -> None:
    results = {
        "splits": {
            "holdout": {
                "incremental_combined_minus_baseline": {
                    "1m": {"delta": 0.0036, "ci_low": -0.0081, "ci_high": 0.0145, "n": 100}
                },
                "calibration_experiment": {"1m": {"ece": 0.1356}},
                "confidence_experiment": {
                    "1m": {"high_confidence_accuracy": 0.5289, "low_confidence_accuracy": 0.5836}
                },
            }
        }
    }
    results_file = tmp_path / "results.json"
    results_file.write_text(json.dumps(results))
    result = runner.invoke(
        _cli(),
        [
            "research",
            "experiment",
            "promotion",
            "conditional_probability",
            "--results-file",
            str(results_file),
        ],
    )
    assert result.exit_code == 1  # CPE fails promotion
    assert "DO NOT PROMOTE" in result.stdout
    assert "FAIL" in result.stdout
