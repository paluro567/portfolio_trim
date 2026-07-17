"""Evidence Normalization Framework: schema, derivations, validation,
serialization round-trips, and cross-model identity — no database."""

import json
import math
from datetime import date

import pytest

from mip.core.exceptions import ConfigurationError
from mip.models.base import ModelScore, RegimeEvidence, ScoreDiagnostics
from mip.models.evidence import (
    KNOWN_MODELS,
    DefaultNormalizer,
    NormalizedEvidence,
    normalize_score,
    normalize_scores,
    validate_evidence,
)

AS_OF = date(2026, 7, 10)


def make_reason(
    label: str = "study",
    excess: float = 0.02,
    se: float = 0.01,
    n_eff: float = 16.0,
    mean: float | None = None,
) -> RegimeEvidence:
    return RegimeEvidence(
        label=label,
        description=f"description of {label}",
        feature="ret_63d",
        n=20,
        n_eff=n_eff,
        mean=0.0312345678 if mean is None else mean,  # non-round: rounding = loss
        hit_rate=0.7123456,
        baseline_mean=0.01,
        excess=excess,
        se=se,
        first_event=date(2020, 3, 2),
        last_event=date(2026, 5, 4),
    )


def make_score(
    model: str = "momentum_exhaustion", neutral: bool = False, **overrides
) -> ModelScore:
    if neutral:
        fields = dict(
            score=50.0,
            confidence=0.0,
            expected_return=None,
            historical_hit_rate=None,
            sample_size=0,
            strongest_supporting_regimes=(),
            strongest_negative_regimes=(),
            diagnostics=None,
            baseline_return=None,
            excess_return=None,
            active_regimes=(),
        )
    else:
        fields = dict(
            score=71.4,
            confidence=0.42,
            expected_return=0.031,
            historical_hit_rate=0.68,
            sample_size=57,
            strongest_supporting_regimes=(make_reason("bullish"),),
            strongest_negative_regimes=(make_reason("bearish", excess=-0.01, se=0.02),),
            diagnostics=ScoreDiagnostics(
                active_regimes=4,
                evidence_studies=3,
                max_n_eff=22.5123456,  # non-round on purpose: rounding = loss
                mean_cross_correlation=0.3123456,
                agreement=0.83,
                z_raw=0.8712345,
                z_clipped=0.8712345,
                saturated=False,
            ),
            baseline_return=0.012,
            excess_return=0.019,
            active_regimes=("regime A", "regime B"),
        )
    fields.update(overrides)
    return ModelScore(
        model=model,
        model_version=1,
        symbol="AMD",
        as_of=AS_OF,
        horizon="1m",
        horizon_sessions=21,
        explanation="because history says so",
        **fields,
    )


# -- derivations ----------------------------------------------------------------


def test_normalization_carries_all_model_statistics() -> None:
    score = make_score()
    evidence = normalize_score(score)

    assert evidence.model_name == "momentum_exhaustion"
    assert evidence.symbol == "AMD" and evidence.horizon == "1m"
    assert evidence.score == score.score and not evidence.neutral
    assert evidence.expected_return == score.expected_return
    assert evidence.baseline_return == score.baseline_return
    assert evidence.expected_excess_return == score.excess_return
    assert evidence.confidence == score.confidence
    assert evidence.effective_sample_size == score.diagnostics.max_n_eff
    assert evidence.sample_size == score.sample_size
    assert evidence.historical_hit_rate == score.historical_hit_rate
    assert evidence.supporting_reasons == score.strongest_supporting_regimes
    assert evidence.opposing_reasons == score.strongest_negative_regimes
    assert evidence.diagnostics == score.diagnostics  # preserved verbatim
    assert evidence.explanation == score.explanation


def test_evidence_strength_is_distance_from_no_edge() -> None:
    assert normalize_score(make_score(score=50.0)).evidence_strength == 0.0
    assert normalize_score(make_score(score=75.0)).evidence_strength == pytest.approx(0.5)
    assert normalize_score(make_score(score=10.0)).evidence_strength == pytest.approx(0.8)


def test_contradictory_evidence_is_dissenting_precision_share() -> None:
    evidence = normalize_score(make_score())
    assert evidence.contradictory_evidence == pytest.approx(1.0 - 0.83)


def test_majority_dissent_is_valid_evidence() -> None:
    """Agreement below 0.5 is real: a high-magnitude minority study can pull
    the combined effect against the precision majority. The contract must
    carry that contradiction to the Decision Engine, not reject it."""
    from dataclasses import replace

    score = make_score()
    score = replace(score, diagnostics=replace(score.diagnostics, agreement=0.41))
    evidence = normalize_score(score)
    assert evidence.contradictory_evidence == pytest.approx(0.59)


def test_expected_volatility_reconstructs_conditional_stdev() -> None:
    """se·sqrt(n_eff) recovers the recency-weighted stdev exactly: with
    std=0.08, kish n_eff=25 and overlap inflation 4, the model stored
    se = (0.08/5)·2 = 0.032 and n_eff = 25/4 = 6.25 -> 0.032·2.5 = 0.08."""
    reason = make_reason(se=0.032, n_eff=6.25)
    volatility = DefaultNormalizer._expected_volatility((reason,))
    assert volatility == pytest.approx(0.08)

    # precision-weighted across two studies (weights 1/se²)
    a = make_reason(se=0.01, n_eff=16.0)  # std 0.04, weight 10000
    b = make_reason(se=0.02, n_eff=25.0)  # std 0.10, weight 2500
    volatility = DefaultNormalizer._expected_volatility((a, b))
    assert volatility == pytest.approx((10000 * 0.04 + 2500 * 0.10) / 12500)


def test_risk_band_brackets_the_expected_return() -> None:
    evidence = normalize_score(make_score())
    assert evidence.expected_volatility is not None and evidence.expected_volatility > 0
    assert evidence.downside_risk == pytest.approx(
        evidence.expected_return - evidence.expected_volatility
    )
    assert evidence.upside_potential == pytest.approx(
        evidence.expected_return + evidence.expected_volatility
    )
    assert evidence.downside_risk < evidence.expected_return < evidence.upside_potential


def test_neutral_scores_normalize_to_explicit_neutral_evidence() -> None:
    evidence = normalize_score(make_score(neutral=True))
    assert evidence.neutral
    assert evidence.expected_return is None and evidence.expected_excess_return is None
    assert evidence.expected_volatility is None
    assert evidence.downside_risk is None and evidence.upside_potential is None
    assert evidence.confidence == 0.0 and evidence.evidence_strength == 0.0
    assert evidence.contradictory_evidence == 0.0
    assert evidence.effective_sample_size == 0.0
    assert evidence.supporting_reasons == () and evidence.opposing_reasons == ()
    assert evidence.diagnostics is None


# -- identical normalization across models ------------------------------------------


def test_all_models_normalize_identically() -> None:
    """The same statistical payload from any registered model must produce
    the same evidence, differing only in the model name — the Decision
    Engine never learns model-specific semantics."""
    payloads = [normalize_score(make_score(model=name)).to_dict() for name in KNOWN_MODELS]
    stripped = [{k: v for k, v in p.items() if k != "model_name"} for p in payloads]
    assert all(p == stripped[0] for p in stripped)
    assert [p["model_name"] for p in payloads] == list(KNOWN_MODELS)
    assert all(set(p) == set(payloads[0]) for p in payloads)  # one schema


def test_unknown_model_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="no evidence normalizer registered"):
        normalize_score(make_score(model="astrology"))


# -- determinism and information preservation -----------------------------------------


def test_normalization_is_deterministic() -> None:
    score = make_score()
    first = normalize_score(score)
    second = normalize_score(score)
    assert first == second
    assert first.to_dict() == second.to_dict()


def test_json_round_trip_loses_nothing() -> None:
    for score in (make_score(), make_score(neutral=True)):
        evidence = normalize_score(score)
        payload = json.loads(json.dumps(evidence.to_dict()))  # through real JSON
        restored = NormalizedEvidence.from_dict(payload)
        assert restored == evidence


def test_batch_normalization_preserves_order() -> None:
    scores = [make_score(score=60.0), make_score(neutral=True), make_score(score=40.0)]
    batch = normalize_scores(scores)
    assert [e.score for e in batch] == [60.0, 50.0, 40.0]
    assert batch[1].neutral and not batch[0].neutral


# -- validation ----------------------------------------------------------------------


def test_validation_rejects_contract_violations() -> None:
    good = normalize_score(make_score())
    from dataclasses import replace

    for broken, message in (
        (replace(good, confidence=1.5), "confidence"),
        (replace(good, score=140.0), "score"),
        (replace(good, evidence_strength=2.0), "evidence_strength"),
        (replace(good, horizon="42d"), "horizon"),
        (replace(good, model_name="astrology"), "unknown model"),
        (replace(good, expected_return=None), "expected_return"),
        (replace(good, historical_hit_rate=1.4), "hit rate"),
        (replace(good, downside_risk=math.inf), "risk band"),
    ):
        with pytest.raises(ConfigurationError, match="invalid normalized evidence"):
            validate_evidence(broken)
        assert message  # documents intent


def test_validation_enforces_neutral_consistency() -> None:
    from dataclasses import replace

    neutral = normalize_score(make_score(neutral=True))
    with pytest.raises(ConfigurationError, match="neutral evidence carries confidence"):
        validate_evidence(replace(neutral, confidence=0.4))


# -- backward compatibility -------------------------------------------------------------


def test_model_score_contract_is_unchanged() -> None:
    """The framework is purely additive: ModelScore's serialized contract
    (what the CLI --json emits today) must not change shape."""
    assert set(make_score().to_dict()) == {
        "model",
        "model_version",
        "symbol",
        "as_of",
        "horizon",
        "horizon_sessions",
        "score",
        "confidence",
        "expected_return",
        "historical_hit_rate",
        "sample_size",
        "active_regimes",
        "strongest_supporting_regimes",
        "strongest_negative_regimes",
        "explanation",
        "diagnostics",
        "baseline_return",
        "excess_return",
    }
