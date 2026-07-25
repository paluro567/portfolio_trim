"""Stage 3 — generalized capture harness: model-agnostic mechanics.

DB-free: exercises the capture logic with fake models and a fake session so the
failure-isolation, neutral-vs-failure distinction, PIT assertion, row schema,
resumability parsing, and registry-driven model selection are all deterministic.
Full historical CPE capture parity is an explicit reproduction command, not a
default unit test.
"""

from datetime import date

import pytest

from mip.core.exceptions import ConfigurationError
from mip.models.base import ModelScore, RegimeEvidence, ScoreDiagnostics
from mip.research.experiments.harness import (
    CaptureStats,
    ModelSet,
    WalkForwardHarness,
    WalkForwardPlan,
    _production_ids,
)

D = date(2023, 6, 1)


def _score(horizon: str, neutral: bool, as_of: date = D) -> ModelScore:
    if neutral:
        return ModelScore(
            model="conditional_probability",
            model_version=1,
            symbol="NVDA",
            as_of=as_of,
            horizon=horizon,
            horizon_sessions=21,
            score=50.0,
            confidence=0.0,
            expected_return=None,
            historical_hit_rate=None,
            sample_size=0,
            strongest_supporting_regimes=(),
            strongest_negative_regimes=(),
            explanation="",
        )
    reg = RegimeEvidence(
        label="x",
        description="d",
        feature="f",
        n=100,
        n_eff=30.0,
        mean=0.02,
        hit_rate=0.55,
        baseline_mean=0.01,
        excess=0.01,
        se=0.005,
        first_event=date(2015, 1, 1),
        last_event=date(2022, 1, 1),
    )
    return ModelScore(
        model="conditional_probability",
        model_version=1,
        symbol="NVDA",
        as_of=as_of,
        horizon=horizon,
        horizon_sessions=21,
        score=60.0,
        confidence=0.5,
        expected_return=0.02,
        historical_hit_rate=0.55,
        sample_size=100,
        strongest_supporting_regimes=(reg,),
        strongest_negative_regimes=(),
        explanation="",
        active_regimes=(),
        diagnostics=ScoreDiagnostics(
            active_regimes=1,
            evidence_studies=1,
            max_n_eff=30.0,
            mean_cross_correlation=0.0,
            agreement=1.0,
            z_raw=0.25,
            z_clipped=0.25,
            saturated=False,
        ),
        baseline_return=0.01,
        excess_return=0.01,
        context={"fallback_level": "market"},
    )


class FakeModel:
    def __init__(self, scores):
        self._scores = scores

    def evaluate(self, symbol, as_of=None):
        return self._scores


class RaisingModel:
    def __init__(self, exc):
        self._exc = exc

    def evaluate(self, symbol, as_of=None):
        raise self._exc


class FakeSession:
    def rollback(self):
        pass


def _harness(tmp_path):
    return WalkForwardHarness(factory=None, artifacts_dir=tmp_path)


def test_captures_evidence_and_counts_neutral(tmp_path) -> None:
    h = _harness(tmp_path)
    stats = CaptureStats()
    model = FakeModel([_score("1m", neutral=False), _score("2w", neutral=True)])
    rows = h._capture_pair(
        FakeSession(), {"conditional_probability": model}, "NVDA", D, True, stats
    )
    evidence = [r for r in rows if "horizon" in r]
    assert len(evidence) == 2
    assert stats.evidence_rows == 2
    assert stats.neutral_rows == 1
    assert stats.failures == 0
    # row schema matches the shipped _row + fallback passthrough
    non_neutral = next(r for r in evidence if not r["neutral"])
    assert non_neutral["model"] == "conditional_probability"
    assert non_neutral["fallback_level"] == "market"
    assert "z_raw" in non_neutral and "n_eff" in non_neutral


def test_model_crash_is_isolated_not_conflated_with_neutral(tmp_path) -> None:
    h = _harness(tmp_path)
    stats = CaptureStats()
    model = RaisingModel(ValueError("boom"))
    rows = h._capture_pair(
        FakeSession(), {"conditional_probability": model}, "NVDA", D, True, stats
    )
    assert stats.failures == 1
    assert stats.failures_by_model["conditional_probability"] == 1
    assert stats.neutral_rows == 0  # a crash is NOT neutral
    assert any(r.get("marker") == "model_error" for r in rows)


def test_configuration_error_is_omitted_not_failure(tmp_path) -> None:
    h = _harness(tmp_path)
    stats = CaptureStats()
    model = RaisingModel(ConfigurationError("no data here"))
    rows = h._capture_pair(
        FakeSession(), {"conditional_probability": model}, "NVDA", D, True, stats
    )
    assert stats.failures == 0  # omission is not a failure
    assert any(r.get("marker") == "omitted" for r in rows)


def test_pit_violation_raises_under_strict(tmp_path) -> None:
    h = _harness(tmp_path)
    stats = CaptureStats()
    future = FakeModel([_score("1m", neutral=False, as_of=date(2023, 12, 1))])  # after D
    with pytest.raises(AssertionError, match="pit_violation"):
        h._capture_pair(FakeSession(), {"conditional_probability": future}, "NVDA", D, True, stats)


def test_pit_violation_counted_when_not_strict(tmp_path) -> None:
    h = _harness(tmp_path)
    stats = CaptureStats()
    future = FakeModel([_score("1m", neutral=False, as_of=date(2023, 12, 1))])
    h._capture_pair(FakeSession(), {"conditional_probability": future}, "NVDA", D, False, stats)
    assert stats.pit_violations == 1


def test_model_selection_reads_registry() -> None:
    h = WalkForwardHarness(factory=None, artifacts_dir=".")
    plan = WalkForwardPlan(
        experiment_id="conditional_probability",
        targets=("NVDA",),
        scoring_dates=(D,),
        holdout_start=date(2022, 1, 1),
    )
    assert h._models_to_run(plan, ModelSet.BASELINE) == list(_production_ids())
    assert h._models_to_run(plan, ModelSet.EXPERIMENT) == ["conditional_probability"]
    all_models = h._models_to_run(plan, ModelSet.ALL)
    assert all_models[-1] == "conditional_probability"
    assert set(all_models[:-1]) == set(_production_ids())


def test_refuses_to_shadow_run_a_production_model() -> None:
    h = WalkForwardHarness(factory=None, artifacts_dir=".")
    plan = WalkForwardPlan(
        experiment_id="macro_regime",
        targets=("NVDA",),
        scoring_dates=(D,),
        holdout_start=date(2022, 1, 1),
    )
    with pytest.raises(ConfigurationError, match="not a shadow experiment"):
        h._models_to_run(plan, ModelSet.ALL)


def test_done_parsing_supports_resume(tmp_path) -> None:
    import json

    h = _harness(tmp_path)
    path = tmp_path / "p.jsonl"
    path.write_text(
        json.dumps({"marker": "pair_done", "symbol": "NVDA", "as_of": "2023-06-01"})
        + "\n"
        + json.dumps({"symbol": "NVDA", "as_of": "2023-06-01", "horizon": "1m", "model": "x"})
        + "\n"
    )
    assert h._done(path) == {"NVDA|2023-06-01"}


def test_plan_validation() -> None:
    with pytest.raises(ConfigurationError, match="target"):
        WalkForwardPlan(
            experiment_id="conditional_probability",
            targets=(),
            scoring_dates=(D,),
            holdout_start=date(2022, 1, 1),
        )
    with pytest.raises(ConfigurationError, match="scoring date"):
        WalkForwardPlan(
            experiment_id="conditional_probability",
            targets=("NVDA",),
            scoring_dates=(),
            holdout_start=date(2022, 1, 1),
        )
