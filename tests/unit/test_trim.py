"""Trim Score Engine: the transparent DecisionEvidence -> TrimAssessment
transformation — shrinkage, bounded portfolio overlay, label gates,
cross-horizon signals, traceability. No database."""

import ast
import inspect
import json
import math
from datetime import date

import pytest

from mip.core.exceptions import ConfigurationError
from mip.engine.evidence import (
    HORIZONS,
    DecisionDiagnostics,
    DecisionEvidence,
    ModelContribution,
)
from mip.engine.trim import (
    LabelBand,
    TrimConfig,
    assess_symbol,
    assess_trim,
)

AS_OF = date(2026, 7, 10)
PARTICIPANTS = ("interest_rate_sensitivity", "macro_regime", "sector_rotation")

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


def make_decision(
    score: float = 50.0,
    confidence: float = 0.5,
    *,
    horizon: str = "1m",
    contradiction: float = 0.1,
    n_eff: float = 40.0,
    participating: tuple[str, ...] = PARTICIPANTS,
    neutral: tuple[str, ...] = (),
    omitted: tuple[str, ...] = (),
    weight: float | None = None,
    risk: float | None = None,
    diversification: float | None = None,
    flags: tuple[str, ...] = (),
    drivers: tuple[str, ...] | None = None,
    holds: tuple[str, ...] | None = None,
) -> DecisionEvidence:
    """Hand-calculable DecisionEvidence: excess = (score - 50) / 1000."""
    portfolio = {
        "portfolio_name": "main" if weight is not None else None,
        "portfolio_weight": weight,
        "risk_contribution": risk,
        "diversification_contribution": diversification,
        "concentration_flags": flags,
    }
    if not participating:
        return DecisionEvidence(
            symbol="AAA",
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
    excess = (score - 50.0) / 1000.0
    expected = 0.01 + excess
    k = len(participating)
    breakdown = tuple(
        ModelContribution(
            model=m,
            score=score,
            effect=excess,
            se=0.01,
            z_raw=excess / 0.01 if excess else 0.1,
            confidence=confidence,
            effective_sample_size=n_eff,
            weight_share=1.0 / k,
            signed_contribution=excess / k,
            saturated=False,
        )
        for m in participating
    )
    return DecisionEvidence(
        symbol="AAA",
        horizon=horizon,
        as_of=AS_OF,
        expected_return=expected,
        expected_excess_return=excess,
        expected_downside=expected - 0.12,
        expected_upside=expected + 0.12,
        historical_hit_rate=0.65,
        combined_score=score,
        combined_confidence=confidence,
        evidence_strength=abs(score - 50.0) / 50.0,
        contradictory_evidence=contradiction,
        effective_sample_size=n_eff,
        participating_models=participating,
        neutral_models=neutral,
        omitted_models=omitted,
        dominant_positive_models=(
            holds if holds is not None else (participating if excess > 0 else ())
        ),
        dominant_negative_models=(
            drivers if drivers is not None else (participating if excess < 0 else ())
        ),
        strongest_supporting_reason=SUPPORTING,
        strongest_opposing_reason=OPPOSING,
        evidence_breakdown=breakdown,
        diagnostics=DecisionDiagnostics(
            participating=k,
            z_raw=(score - 50.0) / 10.0,
            z_clipped=(score - 50.0) / 10.0,
            agreement=1.0 - contradiction,
            saturated=False,
            mean_prior_correlation=0.2,
        ),
        **portfolio,
    )


# -- direction and shrinkage -------------------------------------------------------


def test_strongly_favorable_evidence_scores_low() -> None:
    a = assess_trim(make_decision(score=90.0, confidence=0.8))
    assert a.trim_score == pytest.approx(18.0)  # 50 + 0.8 * (50 - 90)
    assert a.recommendation_label == "Maintain"  # confidence 0.8 clears the 0.40 floor
    assert not a.diagnostics.label_downgraded


def test_strongly_unfavorable_evidence_scores_high() -> None:
    a = assess_trim(make_decision(score=10.0, confidence=0.8))
    assert a.trim_score == pytest.approx(82.0)  # 50 + 0.8 * (50 - 10)
    assert a.recommendation_label == "Trim"


def test_balanced_contradictory_evidence_stays_near_50() -> None:
    a = assess_trim(make_decision(score=50.0, confidence=0.15, contradiction=0.5))
    assert a.trim_score == pytest.approx(50.0)
    assert a.recommendation_label == "Mixed Evidence"
    assert a.data_quality_label == "conflicted"


def test_contradiction_lowers_conviction_through_confidence() -> None:
    """Contradiction reaches this layer as reduced confidence (agreement
    already discounted it upstream) — the assessment stays nearer neutral."""
    agreeing = assess_trim(make_decision(score=20.0, confidence=0.8, contradiction=0.0))
    contradicted = assess_trim(make_decision(score=20.0, confidence=0.3, contradiction=0.6))
    assert abs(contradicted.trim_score - 50.0) < abs(agreeing.trim_score - 50.0)
    assert contradicted.confidence == 0.3  # carried verbatim, never re-derived


def test_contradiction_is_not_counted_twice() -> None:
    """Identical score and confidence with different contradiction values
    must yield identical trim scores: no third contradiction penalty."""
    low = assess_trim(make_decision(score=30.0, confidence=0.5, contradiction=0.05))
    high = assess_trim(make_decision(score=30.0, confidence=0.5, contradiction=0.6))
    assert low.trim_score == high.trim_score == pytest.approx(60.0)
    assert low.evidence_trim_score == high.evidence_trim_score
    # contradiction still shows up in reporting, honestly
    assert high.data_quality_label == "conflicted" and low.data_quality_label != "conflicted"


def test_low_confidence_shrinks_toward_neutral() -> None:
    scores = [
        assess_trim(make_decision(score=10.0, confidence=c)).trim_score
        for c in (0.0, 0.25, 0.5, 0.75, 1.0)
    ]
    assert scores == pytest.approx([50.0, 60.0, 70.0, 80.0, 90.0])  # 50 + 40c


# -- missing evidence --------------------------------------------------------------


def test_missing_models_create_no_directional_pressure() -> None:
    full = assess_trim(make_decision(score=70.0, confidence=0.6))
    sparse = assess_trim(
        make_decision(
            score=70.0,
            confidence=0.6,
            neutral=("momentum_exhaustion",),
            omitted=("valuation", "earnings_behavior"),
        )
    )
    assert sparse.trim_score == full.trim_score
    assert sparse.omitted_models == ("valuation", "earnings_behavior")
    assert any("could not be evaluated" in note for note in sparse.limitations)
    assert any("without active evidence" in note for note in sparse.limitations)


def test_no_evidence_output_is_neutral_and_labelled_explicitly() -> None:
    a = assess_trim(make_decision(participating=(), omitted=("valuation",)))
    assert a.trim_score == 50.0 and a.confidence == 0.0
    assert a.recommendation_label == "Insufficient Evidence"
    assert a.data_quality_label == "no_evidence"
    assert a.expected_return is None and a.expected_excess_return is None
    assert a.model_contributions == ()
    assert a.diagnostics.label_before_gate == "Mixed Evidence"


# -- portfolio overlay -------------------------------------------------------------


def test_concentration_raises_by_the_bounded_adjustment_only() -> None:
    a = assess_trim(make_decision(score=50.0, confidence=0.5, weight=0.60, risk=0.60))
    # weight term 10 * (0.60/0.15 - 1) = 30 -> capped at the +/-10 bound
    assert a.diagnostics.weight_term == pytest.approx(30.0)
    assert a.portfolio_adjustment == pytest.approx(10.0)
    assert a.diagnostics.adjustment_capped
    assert a.evidence_trim_score == pytest.approx(50.0)
    assert a.trim_score == pytest.approx(60.0)


def test_diversification_benefit_reduces_the_adjustment() -> None:
    a = assess_trim(make_decision(score=50.0, confidence=0.5, weight=0.10, risk=0.04))
    # within the weight limit; risk share 4% vs capital share 10% diversifies
    assert a.diagnostics.weight_term == 0.0
    assert a.diagnostics.risk_term == pytest.approx(-1.5)  # 25 * (0.04 - 0.10)
    assert a.portfolio_adjustment == pytest.approx(-1.5)
    assert a.trim_score < a.evidence_trim_score


def test_adjustment_never_exceeds_its_configured_bound() -> None:
    tight = TrimConfig(max_portfolio_adjustment=4.0)
    for weight in (0.0, 0.05, 0.15, 0.3, 0.6, 0.9):
        for risk in (0.0, 0.2, 0.5, 1.0):
            e = make_decision(score=25.0, confidence=0.7, weight=weight, risk=risk)
            assert abs(assess_trim(e).portfolio_adjustment) <= 10.0
            assert abs(assess_trim(e, tight).portfolio_adjustment) <= 4.0


def test_evidence_and_adjusted_scores_stay_separately_visible() -> None:
    a = assess_trim(make_decision(score=30.0, confidence=0.5, weight=0.18, risk=0.30))
    assert a.trim_score == pytest.approx(
        min(100.0, max(0.0, a.evidence_trim_score + a.portfolio_adjustment))
    )
    payload = a.to_dict()
    assert {"trim_score", "evidence_trim_score", "portfolio_adjustment"} <= set(payload)


def test_missing_risk_contribution_drops_only_the_risk_term() -> None:
    a = assess_trim(make_decision(score=50.0, confidence=0.5, weight=0.30, risk=None))
    assert a.diagnostics.weight_term == pytest.approx(10.0)  # 10 * (0.30/0.15 - 1)
    assert a.diagnostics.risk_term == 0.0
    assert any("risk contribution unavailable" in note for note in a.limitations)


def test_no_portfolio_means_zero_adjustment() -> None:
    a = assess_trim(make_decision(score=20.0, confidence=0.8))
    assert a.portfolio_adjustment == 0.0
    assert a.portfolio_weight is None and a.portfolio_name is None
    assert any("no portfolio context" in note for note in a.limitations)


# -- labels ------------------------------------------------------------------------


def test_low_confidence_high_raw_score_is_downgraded_with_warning() -> None:
    """Portfolio pressure can push a low-confidence score into the Trim
    band; the gate downgrades the label and says so, keeping the raw score."""
    a = assess_trim(make_decision(score=2.0, confidence=0.35, weight=0.30, risk=0.50))
    # E = 50 + 0.35*48 = 66.8; adjustment = clip(10 + 25*0.20, 10) = +10
    assert a.trim_score == pytest.approx(76.8)
    assert a.diagnostics.label_before_gate == "Trim"
    assert a.recommendation_label == "Trim Consideration"
    assert a.diagnostics.label_downgraded
    assert any("label downgraded" in note and "0.40" in note for note in a.limitations)


def test_aggressive_labels_require_sufficient_confidence() -> None:
    gated = assess_trim(make_decision(score=2.0, confidence=0.35, weight=0.30, risk=0.50))
    cleared = assess_trim(make_decision(score=2.0, confidence=0.60, weight=0.30, risk=0.50))
    assert gated.recommendation_label == "Trim Consideration"
    assert cleared.recommendation_label in ("Trim", "Strong Trim Candidate")
    assert not cleared.diagnostics.label_downgraded


def test_label_bands_and_floors_are_configuration_driven() -> None:
    config = TrimConfig(
        bands=(
            LabelBand(45.0, "Keep"),
            LabelBand(55.0, "Even"),
            LabelBand(100.0, "Reduce", 0.9),
        )
    )
    a = assess_trim(make_decision(score=0.0, confidence=0.2), config)  # E = 60
    assert a.diagnostics.label_before_gate == "Reduce"
    assert a.recommendation_label == "Even"  # downgraded toward the neutral band
    strong = assess_trim(make_decision(score=0.0, confidence=0.95), config)  # E = 97.5
    assert strong.recommendation_label == "Reduce"


def test_maintain_is_also_confidence_gated() -> None:
    config = TrimConfig(
        bands=(
            LabelBand(25.0, "Maintain", 0.60),
            LabelBand(40.0, "Hold / Monitor"),
            LabelBand(60.0, "Mixed Evidence"),
            LabelBand(100.0, "Trim"),
        )
    )
    a = assess_trim(make_decision(score=99.0, confidence=0.55), config)  # E = 23.05
    assert a.diagnostics.label_before_gate == "Maintain"
    assert a.recommendation_label == "Hold / Monitor"


def test_config_validation() -> None:
    with pytest.raises(ConfigurationError, match="ascending"):
        TrimConfig(bands=(LabelBand(60.0, "B"), LabelBand(40.0, "A")))
    with pytest.raises(ConfigurationError, match="cover scores"):
        TrimConfig(bands=(LabelBand(40.0, "A"), LabelBand(80.0, "B")))
    with pytest.raises(ConfigurationError, match="must not be empty"):
        TrimConfig(bands=())
    with pytest.raises(ConfigurationError, match="max_portfolio_adjustment"):
        TrimConfig(max_portfolio_adjustment=-1.0)
    with pytest.raises(ConfigurationError, match="min_confidence"):
        TrimConfig(bands=(LabelBand(100.0, "A", 1.5),))


def test_data_quality_labels() -> None:
    four = ("interest_rate_sensitivity", "macro_regime", "sector_rotation", "valuation")
    cases = {
        "no_evidence": make_decision(participating=()),
        "sparse": make_decision(score=30.0, confidence=0.5, n_eff=10.0),
        "conflicted": make_decision(score=30.0, confidence=0.5, contradiction=0.6),
        "strong": make_decision(
            score=30.0, confidence=0.5, participating=four, n_eff=40.0, contradiction=0.1
        ),
        "moderate": make_decision(score=30.0, confidence=0.5, n_eff=20.0, contradiction=0.3),
    }
    for expected, evidence in cases.items():
        assert assess_trim(evidence).data_quality_label == expected


# -- horizons ----------------------------------------------------------------------


def test_horizon_specific_differences_are_preserved() -> None:
    result = assess_symbol(
        [
            make_decision(score=20.0, confidence=0.8, horizon="1m"),
            make_decision(score=80.0, confidence=0.8, horizon="6m"),
        ]
    )
    by_horizon = {a.horizon: a for a in result}
    assert by_horizon["1m"].trim_score == pytest.approx(74.0)
    assert by_horizon["6m"].trim_score == pytest.approx(26.0)
    assert by_horizon["1m"].horizon_sessions == 21
    assert by_horizon["6m"].horizon_sessions == 126


def test_cross_horizon_signals_are_diagnosed() -> None:
    evidences = [
        make_decision(score=75.0, confidence=0.80, horizon="1w"),  # T = 30
        make_decision(score=75.0, confidence=0.80, horizon="2w"),  # T = 30
        make_decision(score=75.0, confidence=0.80, horizon="1m"),  # T = 30
        make_decision(  # T = 65: jump +35, side reversal, driver = macro
            score=30.0, confidence=0.75, horizon="3m", drivers=("macro_regime",)
        ),
        make_decision(  # driver changes to rates
            score=30.0,
            confidence=0.75,
            horizon="6m",
            drivers=("interest_rate_sensitivity",),
        ),
        make_decision(score=45.0, confidence=0.30, horizon="1y"),  # confidence drops 0.45
    ]
    result = assess_symbol(evidences)
    notes = result[0].diagnostics.cross_horizon_notes
    assert any("moves +35.0 points from 1m" in n for n in notes)
    assert any("reverses" in n and "1m" in n and "3m" in n for n in notes)
    assert any("driver changes from macro_regime (3m)" in n for n in notes)
    assert any("confidence deteriorates by 0.45 from 6m" in n for n in notes)
    assert all(a.diagnostics.cross_horizon_notes == notes for a in result)


def test_smooth_horizons_produce_no_notes() -> None:
    result = assess_symbol([make_decision(score=40.0, confidence=0.5, horizon=h) for h in HORIZONS])
    assert all(a.diagnostics.cross_horizon_notes == () for a in result)


# -- traceability, determinism, serialization --------------------------------------


def test_exact_traceability_to_decision_evidence() -> None:
    e = make_decision(
        score=35.0,
        confidence=0.6,
        contradiction=0.3,
        n_eff=27.4,
        neutral=("earnings_behavior",),
        omitted=("valuation",),
        weight=0.18,
        risk=0.25,
        diversification=0.012,
        flags=("weight 18.0% exceeds 15.0% limit",),
    )
    a = assess_trim(e)
    # the formula, by hand: E = 50 + 0.6*15 = 59; A = 2.0 + 25*(0.25-0.18) = 3.75
    assert a.evidence_trim_score == pytest.approx(59.0)
    assert a.portfolio_adjustment == pytest.approx(3.75)
    assert a.trim_score == pytest.approx(62.75)
    assert a.recommendation_label == "Trim Consideration"
    # sources carried verbatim
    assert a.diagnostics.source_combined_score == e.combined_score
    assert a.diagnostics.source_combined_confidence == e.combined_confidence
    assert a.confidence == e.combined_confidence
    assert a.participating_models == e.participating_models
    assert a.neutral_models == e.neutral_models
    assert a.omitted_models == e.omitted_models
    assert a.evidence_strength == e.evidence_strength
    assert a.contradictory_evidence == e.contradictory_evidence
    assert a.effective_sample_size == e.effective_sample_size
    assert a.expected_return == e.expected_return
    assert a.expected_excess_return == e.expected_excess_return
    assert a.expected_downside == e.expected_downside
    assert a.expected_upside == e.expected_upside
    assert a.portfolio_weight == e.portfolio_weight
    assert a.risk_contribution == e.risk_contribution
    assert a.diversification_contribution == e.diversification_contribution
    assert a.concentration_flags == e.concentration_flags
    assert a.model_contributions == e.evidence_breakdown
    # trim semantics: "supporting the trim" is the evidence AGAINST exposure
    assert a.strongest_supporting_reason == e.strongest_opposing_reason
    assert a.strongest_opposing_reason == e.strongest_supporting_reason
    assert a.diagnostics.decision_z_raw == e.diagnostics.z_raw
    assert a.diagnostics.decision_agreement == e.diagnostics.agreement


def test_deterministic_and_json_round_trip() -> None:
    e = make_decision(score=35.0, confidence=0.6, weight=0.18, risk=0.25)
    first, second = assess_trim(e), assess_trim(e)
    assert first == second
    payload = first.to_dict()
    assert json.loads(json.dumps(payload)) == payload
    assert payload["as_of"] == AS_OF.isoformat()
    assert not math.isnan(payload["trim_score"])
    assert payload["engine_version"] == 1


def _all_keys(node) -> set[str]:
    keys: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            keys.add(key)
            keys |= _all_keys(value)
    elif isinstance(node, list):
        for item in node:
            keys |= _all_keys(item)
    return keys


def test_no_execution_broker_or_order_fields() -> None:
    payload = assess_trim(make_decision(score=10.0, confidence=0.9, weight=0.4, risk=0.6)).to_dict()
    banned = {
        "order",
        "order_quantity",
        "quantity",
        "shares",
        "shares_to_trade",
        "execution",
        "execution_instruction",
        "broker",
        "broker_action",
        "action",
        "buy",
        "sell",
    }
    assert not banned & _all_keys(payload)


# -- architecture conformance ------------------------------------------------------


def test_trim_engine_consumes_nothing_below_decision_evidence() -> None:
    import mip.engine.trim as module

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
        assert not name.startswith(forbidden), f"forbidden import in trim engine: {name}"
    assert "mip.engine.evidence" in imported
    mip_imports = {name for name in imported if name.startswith("mip.")}
    assert mip_imports == {"mip.engine.evidence", "mip.core.exceptions"}
