"""Decision Evidence Engine: correlated cross-model combination, contradiction
handling, missing-evidence semantics, traceability — no database."""

import ast
import inspect
import json
import math
from datetime import date

import pytest

from mip.core.exceptions import ConfigurationError
from mip.engine.evidence import (
    BASELINE_CORRELATION,
    OVERLAP_CORRELATION,
    DecisionEvidence,
    combine_model_evidence,
    model_correlation,
)
from mip.models import combine_evidence
from mip.models.base import RegimeEvidence, ScoreDiagnostics, score_from_z
from mip.models.evidence import NormalizedEvidence

AS_OF = date(2026, 7, 10)


def make_reason(label: str, excess: float) -> RegimeEvidence:
    return RegimeEvidence(
        label=label,
        description=f"description of {label}",
        feature="ret_63d",
        n=20,
        n_eff=15.0,
        mean=0.01 + excess,
        hit_rate=0.7,
        baseline_mean=0.01,
        excess=excess,
        se=0.01,
        first_event=date(2020, 1, 6),
        last_event=date(2026, 5, 4),
    )


def make_evidence(
    model: str,
    effect: float = 0.02,
    z_raw: float = 2.0,
    neutral: bool = False,
    n_eff: float = 25.0,
    confidence: float = 0.5,
) -> NormalizedEvidence:
    if neutral:
        return NormalizedEvidence(
            model_name=model,
            model_version=1,
            symbol="AAA",
            as_of=AS_OF,
            horizon="1m",
            horizon_sessions=21,
            score=50.0,
            neutral=True,
            expected_return=None,
            baseline_return=None,
            expected_excess_return=None,
            confidence=0.0,
            effective_sample_size=0.0,
            sample_size=0,
            historical_hit_rate=None,
            expected_volatility=None,
            downside_risk=None,
            upside_potential=None,
            evidence_strength=0.0,
            contradictory_evidence=0.0,
            supporting_reasons=(),
            opposing_reasons=(),
            active_regimes=(),
            explanation="nothing active",
            diagnostics=None,
        )
    score = score_from_z(max(-4.0, min(4.0, z_raw)))
    return NormalizedEvidence(
        model_name=model,
        model_version=1,
        symbol="AAA",
        as_of=AS_OF,
        horizon="1m",
        horizon_sessions=21,
        score=score,
        neutral=False,
        expected_return=0.01 + effect,
        baseline_return=0.01,
        expected_excess_return=effect,
        confidence=confidence,
        effective_sample_size=n_eff,
        sample_size=40,
        historical_hit_rate=0.65,
        expected_volatility=0.12,
        downside_risk=0.01 + effect - 0.12,
        upside_potential=0.01 + effect + 0.12,
        evidence_strength=abs(score - 50.0) / 50.0,
        contradictory_evidence=0.1,
        supporting_reasons=(make_reason(f"{model} bull", abs(effect)),) if effect > 0 else (),
        opposing_reasons=(make_reason(f"{model} bear", -abs(effect)),) if effect < 0 else (),
        active_regimes=(f"{model} regime",),
        explanation="because history",
        diagnostics=ScoreDiagnostics(
            active_regimes=3,
            evidence_studies=2,
            max_n_eff=n_eff,
            mean_cross_correlation=0.3,
            agreement=0.9,
            z_raw=z_raw,
            z_clipped=max(-4.0, min(4.0, z_raw)),
            saturated=abs(z_raw) > 4.0,
        ),
    )


def combine(per_model, omitted=(), assessment=None) -> DecisionEvidence:
    return combine_model_evidence("AAA", "1m", AS_OF, per_model, omitted, assessment)


# -- correlation priors ----------------------------------------------------------


def test_correlation_priors() -> None:
    assert model_correlation("macro_regime", "macro_regime") == 1.0
    assert model_correlation("interest_rate_sensitivity", "macro_regime") == OVERLAP_CORRELATION
    assert model_correlation("sector_rotation", "relative_strength") == OVERLAP_CORRELATION
    assert model_correlation("momentum_exhaustion", "relative_strength") == OVERLAP_CORRELATION
    assert model_correlation("valuation", "earnings_behavior") == BASELINE_CORRELATION


def test_combination_matches_the_shared_framework_by_hand() -> None:
    """Two agreeing unrelated models: the engine must reproduce the shared
    correlated fixed-effect combination exactly (never score averaging)."""
    a = make_evidence("valuation", effect=0.02, z_raw=2.0)  # se = 0.01
    b = make_evidence("earnings_behavior", effect=0.04, z_raw=2.0)  # se = 0.02
    result = combine({"valuation": a, "earnings_behavior": b})

    rho = BASELINE_CORRELATION
    expected = combine_evidence([0.04, 0.02], [0.02, 0.01], [[1, rho], [rho, 1]])
    assert result.expected_excess_return == pytest.approx(expected.effect)
    assert result.combined_score == pytest.approx(score_from_z(expected.z))
    assert result.diagnostics.z_raw == pytest.approx(expected.z_raw)


def test_overlapping_models_gain_less_certainty_than_unrelated_ones() -> None:
    """rates+macro (rho .5) must combine to LESS evidence strength than the
    same two effects from unrelated models (rho .2) — the anti-double-count."""
    overlapped = combine(
        {
            "interest_rate_sensitivity": make_evidence("interest_rate_sensitivity"),
            "macro_regime": make_evidence("macro_regime"),
        }
    )
    unrelated = combine(
        {
            "valuation": make_evidence("valuation"),
            "earnings_behavior": make_evidence("earnings_behavior"),
        }
    )
    assert abs(overlapped.diagnostics.z_raw) < abs(unrelated.diagnostics.z_raw)
    assert overlapped.evidence_strength < unrelated.evidence_strength


def test_contradictory_strong_models_cancel_and_lose_confidence() -> None:
    agreeing = combine(
        {
            "valuation": make_evidence("valuation", effect=0.02),
            "earnings_behavior": make_evidence("earnings_behavior", effect=0.02),
        }
    )
    contradicting = combine(
        {
            "valuation": make_evidence("valuation", effect=0.02),
            "earnings_behavior": make_evidence("earnings_behavior", effect=-0.02),
        }
    )
    assert contradicting.expected_excess_return == pytest.approx(0.0)
    assert contradicting.combined_score == pytest.approx(50.0)
    assert contradicting.evidence_strength == pytest.approx(0.0)
    assert contradicting.contradictory_evidence == pytest.approx(0.5)
    assert contradicting.combined_confidence < agreeing.combined_confidence / 1.9
    assert contradicting.dominant_positive_models == ("valuation",)
    assert contradicting.dominant_negative_models == ("earnings_behavior",)


def test_missing_evidence_is_not_neutral_evidence() -> None:
    """Neutral models are EXCLUDED from the statistics (a zero-effect row
    would fabricate precision) and listed separately from omitted ones."""
    with_neutral = combine(
        {
            "valuation": make_evidence("valuation", effect=0.02, z_raw=2.0),
            "macro_regime": make_evidence("macro_regime", neutral=True),
        },
        omitted=("earnings_behavior",),
    )
    alone = combine({"valuation": make_evidence("valuation", effect=0.02, z_raw=2.0)})

    assert with_neutral.participating_models == ("valuation",)
    assert with_neutral.neutral_models == ("macro_regime",)
    assert with_neutral.omitted_models == ("earnings_behavior",)
    # the neutral model changed NOTHING statistically
    assert with_neutral.combined_score == pytest.approx(alone.combined_score)
    assert with_neutral.combined_confidence == pytest.approx(alone.combined_confidence)


def test_no_participating_models_is_explicit_no_evidence() -> None:
    result = combine(
        {"macro_regime": make_evidence("macro_regime", neutral=True)},
        omitted=("valuation",),
    )
    assert result.participating_models == ()
    assert result.combined_score == 50.0 and result.combined_confidence == 0.0
    assert result.expected_return is None and result.expected_excess_return is None
    assert result.evidence_breakdown == () and result.diagnostics is None
    assert result.neutral_models == ("macro_regime",)
    assert result.omitted_models == ("valuation",)


# -- explainability ---------------------------------------------------------------


def test_breakdown_is_fully_traceable() -> None:
    result = combine(
        {
            "valuation": make_evidence("valuation", effect=0.02, z_raw=2.0),
            "earnings_behavior": make_evidence("earnings_behavior", effect=-0.01, z_raw=-1.0),
        }
    )
    assert {c.model for c in result.evidence_breakdown} == {"valuation", "earnings_behavior"}
    assert sum(c.weight_share for c in result.evidence_breakdown) == pytest.approx(1.0)
    # signed contributions decompose the combined effect exactly
    assert sum(c.signed_contribution for c in result.evidence_breakdown) == pytest.approx(
        result.expected_excess_return
    )
    assert result.strongest_supporting_reason["model"] == "valuation"
    assert result.strongest_opposing_reason["model"] == "earnings_behavior"
    assert "description" in result.strongest_supporting_reason


def test_expectations_are_precision_weighted() -> None:
    a = make_evidence("valuation", effect=0.02, z_raw=2.0)  # se .01, weight 10000
    b = make_evidence("earnings_behavior", effect=0.04, z_raw=1.0)  # se .04, weight 625
    result = combine({"valuation": a, "earnings_behavior": b})
    w_a, w_b = 10000 / 10625, 625 / 10625
    assert result.expected_return == pytest.approx(w_a * 0.03 + w_b * 0.05)
    assert result.expected_downside == pytest.approx(result.expected_return - 0.12)
    assert result.expected_upside == pytest.approx(result.expected_return + 0.12)
    assert result.effective_sample_size == 25.0  # max, never summed


def test_deterministic_and_json_serializable() -> None:
    per_model = {
        "valuation": make_evidence("valuation", effect=0.02),
        "macro_regime": make_evidence("macro_regime", effect=-0.01, z_raw=-1.5),
    }
    first = combine(dict(per_model))
    second = combine(dict(reversed(list(per_model.items()))))  # order-independent
    assert first == second
    payload = json.loads(json.dumps(first.to_dict()))
    assert payload["symbol"] == "AAA" and payload["horizon"] == "1m"
    assert not math.isnan(payload["combined_score"])
    for banned in ("trim_score", "recommendation", "action"):
        assert banned not in payload  # descriptive only, forever


def test_engine_requires_symbols_or_portfolio() -> None:
    from mip.engine.evidence import DecisionEvidenceEngine

    engine = DecisionEvidenceEngine.__new__(DecisionEvidenceEngine)
    with pytest.raises(ConfigurationError, match="symbols or --portfolio"):
        engine.assess(symbols=None, portfolio=None)


# -- architecture conformance ---------------------------------------------------


def test_engine_is_isolated_from_evidence_production() -> None:
    """The Decision Engine consumes only NormalizedEvidence and
    PortfolioPositionAssessment through public surfaces — never model
    internals, research, features, providers, repositories, or tables."""
    import mip.engine.evidence as module

    tree = ast.parse(inspect.getsource(module))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    submodules = (
        "rates",
        "sector",
        "momentum",
        "valuation",
        "earnings",
        "macro",
        "relative",
        "base",
        "evidence",
    )
    forbidden = tuple(f"mip.models.{name}" for name in submodules) + (
        "mip.research",
        "mip.features",
        "mip.providers",
        "mip.repositories",
        "mip.domain",
        "mip.ingestion",
    )
    for name in imported:
        assert not name.startswith(forbidden), f"forbidden import in decision engine: {name}"
    assert "mip.models" in imported and "mip.portfolio.analytics" in imported
