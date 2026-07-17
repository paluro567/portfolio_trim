"""Evidence Attribution Engine: exact decomposition of trim scores into
model, portfolio, and clip line items — sums verified by hand. No database."""

import ast
import inspect
import json
import math
from datetime import date

import pytest

from mip.core.exceptions import ConfigurationError
from mip.engine.attribution import attribute
from mip.engine.evidence import DecisionDiagnostics, DecisionEvidence, ModelContribution
from mip.engine.trim import assess_trim

AS_OF = date(2026, 7, 10)

SUPPORTING = {
    "model": "sector_rotation",
    "label": "bull regime",
    "description": "bullish historical regime",
    "n": 20,
    "n_eff": 15.0,
    "mean": 0.03,
    "baseline_mean": 0.01,
    "excess": 0.02,
    "hit_rate": 0.7,
}
OPPOSING = {
    "model": "macro_regime",
    "label": "bear regime",
    "description": "bearish historical regime",
    "n": 18,
    "n_eff": 12.0,
    "mean": -0.01,
    "baseline_mean": 0.01,
    "excess": -0.02,
    "hit_rate": 0.35,
}


def decision(
    score: float = 50.0,
    confidence: float = 0.5,
    *,
    contributions: list[tuple[str, float, float, float]] = (),  # (model, effect, share, se)
    horizon: str = "1m",
    contradiction: float = 0.1,
    weight: float | None = None,
    risk: float | None = None,
    neutral: tuple[str, ...] = (),
    omitted: tuple[str, ...] = (),
    symbol: str = "AAA",
) -> DecisionEvidence:
    """Hand-built DecisionEvidence whose breakdown is given explicitly;
    the combined excess is exactly the sum of signed contributions."""
    portfolio = {
        "portfolio_name": "main" if weight is not None else None,
        "portfolio_weight": weight,
        "risk_contribution": risk,
        "diversification_contribution": None,
        "concentration_flags": (),
    }
    if not contributions:
        return DecisionEvidence(
            symbol=symbol,
            horizon=horizon,
            as_of=AS_OF,
            expected_return=None,
            expected_excess_return=None,
            expected_downside=None,
            expected_upside=None,
            historical_hit_rate=None,
            combined_score=50.0,
            combined_confidence=0.0,
            evidence_strength=0.0,
            contradictory_evidence=0.0,
            effective_sample_size=0.0,
            participating_models=(),
            neutral_models=neutral,
            omitted_models=omitted,
            dominant_positive_models=(),
            dominant_negative_models=(),
            strongest_supporting_reason=None,
            strongest_opposing_reason=None,
            evidence_breakdown=(),
            diagnostics=None,
            **portfolio,
        )
    breakdown = tuple(
        ModelContribution(
            model=model,
            score=score,
            effect=effect,
            se=se,
            z_raw=effect / se,
            confidence=confidence,
            effective_sample_size=40.0,
            weight_share=share,
            signed_contribution=effect * share,
            saturated=False,
        )
        for model, effect, share, se in contributions
    )
    combined_excess = sum(c.signed_contribution for c in breakdown)
    return DecisionEvidence(
        symbol=symbol,
        horizon=horizon,
        as_of=AS_OF,
        expected_return=0.01 + combined_excess,
        expected_excess_return=combined_excess,
        expected_downside=0.01 + combined_excess - 0.12,
        expected_upside=0.01 + combined_excess + 0.12,
        historical_hit_rate=0.6,
        combined_score=score,
        combined_confidence=confidence,
        evidence_strength=abs(score - 50.0) / 50.0,
        contradictory_evidence=contradiction,
        effective_sample_size=40.0,
        participating_models=tuple(c.model for c in breakdown),
        neutral_models=neutral,
        omitted_models=omitted,
        dominant_positive_models=tuple(c.model for c in breakdown if c.effect > 0),
        dominant_negative_models=tuple(c.model for c in breakdown if c.effect < 0),
        strongest_supporting_reason=SUPPORTING,
        strongest_opposing_reason=OPPOSING,
        evidence_breakdown=breakdown,
        diagnostics=DecisionDiagnostics(
            participating=len(breakdown),
            z_raw=(score - 50.0) / 10.0,
            z_clipped=(score - 50.0) / 10.0,
            agreement=1.0 - contradiction,
            saturated=False,
            mean_prior_correlation=0.2,
        ),
        **portfolio,
    )


MIXED = [  # signed: -0.03 and +0.01 -> combined excess -0.02
    ("macro_regime", -0.05, 0.6, 0.02),
    ("sector_rotation", 0.025, 0.4, 0.01),
]


def report_for(evidence: DecisionEvidence):
    return attribute(assess_trim(evidence), evidence)


def total(report) -> float:
    return (
        report.neutral_baseline
        + sum(c.contribution for c in report.evidence_contributions)
        + report.portfolio_contributions.concentration_adjustment
        + report.portfolio_contributions.diversification_adjustment
        + report.clip_residual
    )


# -- the sum invariant -------------------------------------------------------------


def test_contributions_sum_exactly_to_trim_score() -> None:
    """E = 50 + 0.5*(50-30) = 60; macro = 10*(-0.03/-0.02) = +15,
    sector = 10*(0.01/-0.02) = -5; A = 2.0 + 25*(0.25-0.18) = +3.75."""
    e = decision(score=30.0, confidence=0.5, contributions=MIXED, weight=0.18, risk=0.25)
    r = report_for(e)
    by_model = {c.model_name: c for c in r.evidence_contributions}
    assert by_model["macro_regime"].contribution == pytest.approx(15.0)
    assert by_model["sector_rotation"].contribution == pytest.approx(-5.0)
    assert r.portfolio_contributions.portfolio_overlay_contribution == pytest.approx(3.75)
    assert r.trim_score == pytest.approx(63.75)
    assert math.isclose(total(r), r.trim_score, abs_tol=1e-9)
    # the model rows alone reproduce the evidence deviation exactly
    assert sum(c.contribution for c in r.evidence_contributions) == pytest.approx(
        r.traceability["evidence_trim_score"] - 50.0
    )


def test_sum_invariant_across_scenarios() -> None:
    scenarios = [
        decision(score=30.0, confidence=0.5, contributions=MIXED),
        decision(score=80.0, confidence=0.9, contributions=[("valuation", 0.04, 1.0, 0.01)]),
        decision(score=30.0, confidence=0.5, contributions=MIXED, weight=0.6, risk=0.9),
        decision(score=2.0, confidence=0.95, contributions=MIXED, weight=0.6, risk=0.9),  # clips
        decision(),  # no evidence at all
    ]
    for e in scenarios:
        r = report_for(e)
        assert math.isclose(total(r), r.trim_score, abs_tol=1e-9), e.combined_score
        if r.contribution_ranking:
            assert r.contribution_ranking[-1].cumulative == pytest.approx(r.trim_score)


def test_direction_labels() -> None:
    r = report_for(decision(score=30.0, confidence=0.5, contributions=MIXED))
    by_model = {c.model_name: c for c in r.evidence_contributions}
    assert by_model["macro_regime"].direction == "raises_trim"
    assert by_model["sector_rotation"].direction == "lowers_trim"


# -- portfolio overlay split -------------------------------------------------------


def test_portfolio_split_uncapped_keeps_parts_separate() -> None:
    # W = 10*(0.30/0.15-1) = 10; R = 25*(0.10-0.30) = -5 -> A = +5
    e = decision(score=50.0, confidence=0.5, contributions=MIXED, weight=0.30, risk=0.10)
    r = report_for(e)
    assert r.portfolio_contributions.concentration_adjustment == pytest.approx(10.0)
    assert r.portfolio_contributions.diversification_adjustment == pytest.approx(-5.0)
    assert r.portfolio_contributions.portfolio_overlay_contribution == pytest.approx(5.0)


def test_portfolio_split_scales_proportionally_under_the_cap() -> None:
    # W = 30, R = -7.5 -> raw 22.5 capped to 10 -> scale 4/9
    e = decision(score=50.0, confidence=0.5, contributions=MIXED, weight=0.60, risk=0.30)
    r = report_for(e)
    conc = r.portfolio_contributions.concentration_adjustment
    div = r.portfolio_contributions.diversification_adjustment
    assert conc == pytest.approx(30.0 * (10.0 / 22.5))
    assert div == pytest.approx(-7.5 * (10.0 / 22.5))
    assert conc + div == pytest.approx(10.0)  # still sums to the applied adjustment


def test_no_portfolio_keeps_overlay_at_zero_and_out_of_ranking() -> None:
    r = report_for(decision(score=30.0, confidence=0.5, contributions=MIXED))
    assert r.portfolio_contributions.portfolio_overlay_contribution == 0.0
    assert r.portfolio_contributions.concentration_adjustment == 0.0
    assert all(item.kind != "portfolio" for item in r.contribution_ranking)
    assert r.dominant_portfolio_driver is None


# -- clip and missing evidence -----------------------------------------------------


def test_clip_residual_is_an_explicit_line_item() -> None:
    e = decision(
        score=2.0,
        confidence=0.95,
        contributions=[("macro_regime", -0.06, 1.0, 0.02)],
        weight=0.60,
        risk=0.90,
    )
    r = report_for(e)
    # E = 50 + 0.95*48 = 95.6; A = +10 -> 105.6 clipped to 100
    assert r.trim_score == pytest.approx(100.0)
    assert r.clip_residual == pytest.approx(-5.6)
    assert any(item.kind == "clip" for item in r.contribution_ranking)
    assert math.isclose(total(r), 100.0, abs_tol=1e-9)


def test_no_evidence_is_neutral_with_empty_decomposition() -> None:
    r = report_for(decision(neutral=("macro_regime",), omitted=("valuation",)))
    assert r.trim_score == 50.0
    assert r.evidence_contributions == () and r.contribution_ranking == ()
    assert r.strongest_positive_contributor is None
    assert r.strongest_negative_contributor is None
    assert r.largest_uncertainty is None
    assert r.neutral_models == ("macro_regime",)
    assert r.omitted_models == ("valuation",)
    assert math.isclose(total(r), 50.0, abs_tol=1e-9)


def test_missing_models_get_no_invented_rows() -> None:
    e = decision(
        score=30.0,
        confidence=0.5,
        contributions=MIXED,
        neutral=("earnings_behavior", "valuation"),
        omitted=("relative_strength",),
    )
    r = report_for(e)
    assert {c.model_name for c in r.evidence_contributions} == {
        "macro_regime",
        "sector_rotation",
    }
    assert r.neutral_models == ("earnings_behavior", "valuation")
    assert r.omitted_models == ("relative_strength",)


# -- summary -----------------------------------------------------------------------


def test_summary_fields() -> None:
    e = decision(score=30.0, confidence=0.5, contributions=MIXED, weight=0.18, risk=0.25)
    r = report_for(e)
    assert r.strongest_positive_contributor == "macro_regime"  # +15 beats +3.75 overlay
    assert r.strongest_negative_contributor == "sector_rotation"
    assert r.largest_uncertainty == {"model": "macro_regime", "standard_error": 0.02}
    # deviation is toward trim -> dominant regime is the bearish reason
    assert r.dominant_historical_regime == OPPOSING
    assert r.dominant_portfolio_driver == "weight_concentration"  # W 2.0 >= |R| 1.75


def test_dominant_regime_flips_with_favorable_evidence() -> None:
    e = decision(score=80.0, confidence=0.6, contributions=[("valuation", 0.04, 1.0, 0.01)])
    r = report_for(e)
    assert r.dominant_historical_regime == SUPPORTING  # maintain-side deviation


def test_portfolio_driver_branches() -> None:
    mixed = MIXED
    cases = [
        ({"weight": 0.10, "risk": 0.50}, "risk_concentration"),  # R = +10, W = 0
        ({"weight": 0.10, "risk": 0.02}, "diversification_benefit"),  # R = -2, W = 0
        ({"weight": 0.10, "risk": 0.10}, "none"),  # both terms zero
        ({}, None),  # no portfolio context
    ]
    for kwargs, expected in cases:
        r = report_for(decision(score=40.0, confidence=0.5, contributions=mixed, **kwargs))
        assert r.dominant_portfolio_driver == expected, kwargs


# -- ranking, determinism, serialization, lineage ----------------------------------


def test_ranking_is_ordered_by_magnitude_with_running_total() -> None:
    e = decision(score=30.0, confidence=0.5, contributions=MIXED, weight=0.18, risk=0.25)
    r = report_for(e)
    magnitudes = [abs(item.contribution) for item in r.contribution_ranking]
    assert magnitudes == sorted(magnitudes, reverse=True)
    running = r.neutral_baseline
    for item in r.contribution_ranking:
        running += item.contribution
        assert item.cumulative == pytest.approx(running)
    assert r.contribution_ranking[-1].cumulative == pytest.approx(r.trim_score)


def test_deterministic_and_json_round_trip() -> None:
    e = decision(score=30.0, confidence=0.5, contributions=MIXED, weight=0.18, risk=0.25)
    first, second = report_for(e), report_for(e)
    assert first == second
    payload = first.to_dict()
    assert json.loads(json.dumps(payload)) == payload
    assert payload["as_of"] == AS_OF.isoformat()
    assert payload["traceability"]["attribution_engine_version"] == 1


def test_traceability_and_lineage_guard() -> None:
    e = decision(score=30.0, confidence=0.5, contributions=MIXED, weight=0.18, risk=0.25)
    a = assess_trim(e)
    r = attribute(a, e)
    assert r.traceability["decision_combined_score"] == e.combined_score
    assert r.traceability["decision_combined_confidence"] == e.combined_confidence
    assert r.traceability["evidence_trim_score"] == a.evidence_trim_score
    assert r.traceability["portfolio_adjustment"] == a.portfolio_adjustment
    assert r.traceability["combined_expected_excess_return"] == e.expected_excess_return
    assert r.traceability["recommendation_label"] == a.recommendation_label
    # a report can never mix lineages
    other_horizon = decision(score=30.0, confidence=0.5, contributions=MIXED, horizon="3m")
    with pytest.raises(ConfigurationError, match="does not derive"):
        attribute(a, other_horizon)
    tampered = decision(score=31.0, confidence=0.5, contributions=MIXED)
    with pytest.raises(ConfigurationError, match="does not derive"):
        attribute(a, tampered)


# -- architecture conformance ------------------------------------------------------


def test_attribution_consumes_only_trim_and_decision_layers() -> None:
    import mip.engine.attribution as module

    tree = ast.parse(inspect.getsource(module))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = (
        "mip.models",
        "mip.portfolio",
        "mip.research",
        "mip.features",
        "mip.providers",
        "mip.repositories",
        "mip.domain",
        "mip.ingestion",
    )
    for name in imported:
        assert not name.startswith(forbidden), f"forbidden import in attribution engine: {name}"
    mip_imports = {name for name in imported if name.startswith("mip.")}
    assert mip_imports == {"mip.engine.evidence", "mip.engine.trim", "mip.core.exceptions"}
