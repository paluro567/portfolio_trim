"""Stage 5 — standardized report + mechanical promotion evaluation.

Regression: the four-state promotion logic must reproduce the CPE's scientific
conclusion (fail on every gate -> stay shadow) from its holdout numbers, and
must never promote on a single improved standalone metric.
"""

from dataclasses import replace

from mip.research.experiments.manifest import ReproducibilityManifest
from mip.research.experiments.registry import PromotionCriterion, get_experiment
from mip.research.experiments.report import (
    CriterionStatus,
    evaluate_promotion,
    promotion_recommendation,
    render_report,
)

CPE = get_experiment("conditional_probability")


def _results(ci_low, ece, hi, lo, delta=0.0036, n=100) -> dict:
    return {
        "participation": {"1m": {"cells": 5425, "neutral": 2043, "participation_rate": 0.62}},
        "splits": {
            "holdout": {
                "per_system": {
                    "1m": {
                        "baseline": {"direction_accuracy": 0.4994},
                        "combined": {"direction_accuracy": 0.5060},
                        "experiment_only": {"direction_accuracy": 0.5531},
                    }
                },
                "incremental_combined_minus_baseline": {
                    "1m": {"delta": delta, "ci_low": ci_low, "ci_high": 0.0145, "n": n}
                },
                "calibration_experiment": {"1m": {"ece": ece}},
                "confidence_experiment": {
                    "1m": {"high_confidence_accuracy": hi, "low_confidence_accuracy": lo}
                },
            }
        },
    }


def _manifest() -> ReproducibilityManifest:
    return ReproducibilityManifest(
        experiment_id="conditional_probability",
        experiment_version=1,
        run_id="r1",
        created_at="2026-07-24T00:00:00",
        harness_version="1.0",
        config_hash="h",
        scoring_window=("2013-01-02", "2026-07-01"),
        holdout_window=("2022-01-01", "2026-07-01"),
        walk_forward_schedule="monthly",
        supported_horizons=("1w", "2w", "1m", "3m", "6m", "1y"),
        random_seeds={"block_bootstrap": 7},
        promotion_thresholds=(),
        git_commit="abc",
        git_dirty=False,
        dataset_versions={},
        feature_versions={},
        universe_hash="u",
        runtime_environment={},
    )


def test_cpe_conclusion_reproduced_all_fail() -> None:
    # archived CPE holdout numbers
    results = _results(ci_low=-0.0081, ece=0.1356, hi=0.5289, lo=0.5836)
    criteria = evaluate_promotion(CPE, results)
    by_id = {c.id: c for c in criteria}
    assert by_id["incremental_1m"].status is CriterionStatus.FAIL
    assert by_id["calibration"].status is CriterionStatus.FAIL
    assert by_id["confidence_discriminates"].status is CriterionStatus.FAIL
    recommend, reason = promotion_recommendation(criteria)
    assert recommend is False
    assert "blocked by" in reason


def test_all_pass_recommends_promotion() -> None:
    results = _results(ci_low=0.02, ece=0.05, hi=0.60, lo=0.55)
    criteria = evaluate_promotion(CPE, results)
    assert all(c.status is CriterionStatus.PASS for c in criteria)
    recommend, reason = promotion_recommendation(criteria)
    assert recommend is True
    assert "all promotion criteria passed" in reason


def test_single_improved_standalone_metric_does_not_promote() -> None:
    # calibration + confidence great, but the incremental gate still fails
    results = _results(ci_low=-0.001, ece=0.04, hi=0.62, lo=0.55)
    recommend, reason = promotion_recommendation(evaluate_promotion(CPE, results))
    assert recommend is False


def test_inconclusive_when_no_interval() -> None:
    results = _results(ci_low=None, ece=0.05, hi=0.60, lo=0.55)
    results["splits"]["holdout"]["incremental_combined_minus_baseline"]["1m"] = {"n": 0}
    criteria = evaluate_promotion(CPE, results)
    inc = next(c for c in criteria if c.id == "incremental_1m")
    assert inc.status is CriterionStatus.INCONCLUSIVE
    assert promotion_recommendation(criteria)[0] is False


def test_not_measurable_when_metric_unmapped() -> None:
    spec = replace(
        CPE,
        promotion_criteria=(
            PromotionCriterion(
                "mystery",
                "some unmapped metric",
                metric="unknown_metric",
                comparator=">",
                threshold=0.0,
                horizon="1m",
            ),
        ),
    )
    criteria = evaluate_promotion(spec, _results(0.02, 0.05, 0.6, 0.55))
    assert criteria[0].status is CriterionStatus.NOT_MEASURABLE
    assert promotion_recommendation(criteria)[0] is False


def test_no_criteria_never_promotes() -> None:
    spec = replace(CPE, promotion_criteria=())
    recommend, reason = promotion_recommendation(
        evaluate_promotion(spec, _results(0.02, 0.05, 0.6, 0.55))
    )
    assert recommend is False
    assert "no promotion criteria" in reason


def test_render_report_contains_sections_and_verdict() -> None:
    report = render_report(CPE, _manifest(), _results(-0.0081, 0.1356, 0.5289, 0.5836))
    for section in (
        "Executive summary",
        "Null hypothesis",
        "Point-in-time safeguards",
        "Promotion-criteria evaluation",
        "Final recommendation",
        "Limitations",
        "Reproduction",
        "Participation coverage",
    ):
        assert section in report, f"missing section: {section}"
    assert "DO NOT PROMOTE" in report
    assert "REMAIN SHADOW" in report
