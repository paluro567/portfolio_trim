"""Prediction Archive & Outcome Evaluation: archive mapping, outcome
arithmetic, calibration, model/horizon/trim/regime analytics — every
number verified by hand. No database."""

import ast
import inspect
import json
from datetime import date, timedelta

import pytest

from mip.engine.trim import assess_trim
from mip.evaluation.analytics import (
    calibration_table,
    horizon_analytics,
    model_analytics,
    trim_analytics,
)
from mip.evaluation.archive import prediction_row
from mip.evaluation.outcomes import compute_outcome
from mip.evaluation.regimes import RegimeClassifier, regime_analytics
from tests.unit.test_attribution import MIXED, decision

AS_OF = date(2026, 7, 10)


def row(
    *,
    horizon: str = "1m",
    trim: float = 50.0,
    confidence: float = 0.5,
    expected_excess: float | None = 0.01,
    actual_excess: float | None = 0.02,
    error: float | None = None,
    direction: bool | None = None,
    label: str = "Mixed Evidence",
    contributions: list[dict] | None = None,
    as_of: date = AS_OF,
) -> dict:
    if error is None and None not in (expected_excess, actual_excess):
        error = actual_excess - expected_excess
    if direction is None and expected_excess not in (None, 0.0) and actual_excess is not None:
        direction = (expected_excess > 0) == (actual_excess > 0)
    return {
        "symbol": "AAA",
        "horizon": horizon,
        "as_of": as_of,
        "trim_score": trim,
        "confidence": confidence,
        "expected_excess_return": expected_excess,
        "recommendation_label": label,
        "data_quality_label": "moderate",
        "model_contributions": contributions or [],
        "actual_return": (actual_excess or 0.0) + 0.01,
        "actual_excess_return": actual_excess,
        "prediction_error": error,
        "absolute_error": abs(error) if error is not None else None,
        "direction_correct": direction,
    }


# -- outcome arithmetic --------------------------------------------------------------


def test_compute_outcome_by_hand() -> None:
    out = compute_outcome(100.0, 105.0, baseline_return=0.02, expected_excess=0.01)
    assert out["actual_return"] == pytest.approx(0.05)
    assert out["actual_excess_return"] == pytest.approx(0.03)
    assert out["prediction_error"] == pytest.approx(0.02)
    assert out["absolute_error"] == pytest.approx(0.02)
    assert out["direction_correct"] is True
    assert out["outperformed"] is True and out["underperformed"] is False

    down = compute_outcome(100.0, 95.0, baseline_return=0.02, expected_excess=0.01)
    assert down["actual_excess_return"] == pytest.approx(-0.07)
    assert down["prediction_error"] == pytest.approx(-0.08)
    assert down["direction_correct"] is False
    assert down["outperformed"] is False and down["underperformed"] is True


def test_outcome_without_evidence_is_never_scored() -> None:
    """Missing evidence at prediction time is not a right or wrong call."""
    out = compute_outcome(100.0, 95.0, baseline_return=None, expected_excess=None)
    assert out["actual_return"] == pytest.approx(-0.05)
    for field in (
        "actual_excess_return",
        "prediction_error",
        "absolute_error",
        "direction_correct",
        "outperformed",
        "underperformed",
    ):
        assert out[field] is None
    zero = compute_outcome(100.0, 95.0, baseline_return=0.0, expected_excess=0.0)
    assert zero["direction_correct"] is None  # zero expectation has no direction
    assert zero["underperformed"] is True


# -- archive mapping -----------------------------------------------------------------


def test_prediction_row_maps_assessment_verbatim() -> None:
    e = decision(score=30.0, confidence=0.5, contributions=MIXED, weight=0.18, risk=0.25)
    a = assess_trim(e)
    archived = prediction_row(a, instrument_id=7)
    assert archived["instrument_id"] == 7
    assert archived["portfolio_key"] == "main"
    assert archived["as_of"] == a.as_of and archived["horizon"] == a.horizon
    assert archived["horizon_sessions"] == a.horizon_sessions
    assert archived["trim_score"] == a.trim_score
    assert archived["evidence_trim_score"] == a.evidence_trim_score
    assert archived["portfolio_adjustment"] == a.portfolio_adjustment
    assert archived["confidence"] == a.confidence
    assert archived["recommendation_label"] == a.recommendation_label
    assert archived["baseline_return"] == pytest.approx(
        a.expected_return - a.expected_excess_return
    )
    assert archived["model_contributions"] == [c.to_dict() for c in a.model_contributions]
    assert archived["participating_models"] == list(a.participating_models)
    assert archived["evidence"]["neutral_models"] == list(a.neutral_models)
    assert archived["evidence"]["limitations"] == list(a.limitations)
    assert archived["trim_engine_version"] == a.engine_version
    json.dumps({k: v for k, v in archived.items() if k != "as_of"})  # JSON-safe payloads

    no_evidence = prediction_row(assess_trim(decision()), instrument_id=3)
    assert no_evidence["portfolio_key"] == ""
    assert no_evidence["expected_return"] is None
    assert no_evidence["baseline_return"] is None


# -- calibration ---------------------------------------------------------------------


def test_calibration_table_by_hand() -> None:
    rows = [
        row(confidence=0.10, direction=True, error=0.01),
        row(confidence=0.50, direction=True, error=0.02),
        row(confidence=0.55, direction=False, error=-0.04),
        row(confidence=0.90, direction=True, error=0.01),
        row(confidence=0.95, expected_excess=None, actual_excess=None),  # excluded
    ]
    table = calibration_table(rows)
    by_bucket = {b["bucket"]: b for b in table}
    assert by_bucket["0.00-0.20"]["n"] == 1
    assert by_bucket["0.00-0.20"]["direction_accuracy"] == 1.0
    mid = by_bucket["0.40-0.60"]
    assert mid["n"] == 2
    assert mid["direction_accuracy"] == pytest.approx(0.5)
    assert mid["mean_confidence"] == pytest.approx(0.525)
    assert mid["mean_absolute_error"] == pytest.approx(0.03)
    assert by_bucket["0.80-1.00"]["n"] == 1  # the None-direction row never lands anywhere
    assert by_bucket["0.20-0.40"]["n"] == 0
    assert by_bucket["0.20-0.40"]["direction_accuracy"] is None


# -- model analytics -----------------------------------------------------------------


def contribution(model: str, effect: float, share: float) -> dict:
    return {
        "model": model,
        "effect": effect,
        "weight_share": share,
        "signed_contribution": effect * share,
        "score": 50.0,
        "se": 0.01,
        "z_raw": effect / 0.01,
        "confidence": 0.5,
        "effective_sample_size": 40.0,
        "saturated": False,
    }


def test_model_analytics_by_hand() -> None:
    rows = [
        row(
            expected_excess=-0.02,
            actual_excess=-0.03,
            contributions=[
                contribution("macro_regime", -0.05, 0.6),
                contribution("sector_rotation", 0.025, 0.4),
            ],
        ),
        row(
            expected_excess=0.04,
            actual_excess=0.01,
            contributions=[contribution("macro_regime", 0.04, 1.0)],
        ),
    ]
    table = {m["model"]: m for m in model_analytics(rows)}
    macro = table["macro_regime"]
    assert macro["n"] == 2
    assert macro["agreement_rate"] == 1.0 and macro["contradiction_rate"] == 0.0
    assert macro["directional_accuracy"] == 1.0 and macro["directional_edge"] == 0.5
    assert macro["mae"] == pytest.approx(0.025)  # (0.02 + 0.03) / 2
    assert macro["naive_mae"] == pytest.approx(0.02)  # (0.03 + 0.01) / 2
    assert macro["information_gain"] == pytest.approx(-0.005)
    assert macro["avg_weight_share"] == pytest.approx(0.8)
    sector = table["sector_rotation"]
    assert sector["agreement_rate"] == 0.0 and sector["contradiction_rate"] == 1.0
    assert sector["directional_accuracy"] == 0.0
    assert sector["mae"] == pytest.approx(0.055)
    assert sector["information_gain"] == pytest.approx(0.03 - 0.055)


# -- horizon analytics ---------------------------------------------------------------


def test_horizon_analytics_by_hand() -> None:
    rows = [
        row(horizon="1m", expected_excess=0.01, actual_excess=0.03, confidence=0.6, label="Trim"),
        row(
            horizon="1m",
            expected_excess=-0.02,
            actual_excess=-0.02 - 0.04,  # error -0.04
            confidence=0.4,
            label="Maintain",
        ),
        row(horizon="1w", expected_excess=0.01, actual_excess=0.02, confidence=0.5),
    ]
    table = {h["horizon"]: h for h in horizon_analytics(rows)}
    one_month = table["1m"]
    assert one_month["n"] == 2
    assert one_month["mae"] == pytest.approx(0.03)  # |0.02|, |-0.04|
    assert one_month["rmse"] == pytest.approx((0.0002 + 0.0008) ** 0.5 / (2**0.5) * (2**0.5))
    assert one_month["rmse"] == pytest.approx(((0.02**2 + 0.04**2) / 2) ** 0.5)
    assert one_month["direction_accuracy"] == 1.0  # both signs matched
    # aligned excess: +0.03 (long side), +0.06 (reduction side, sign-flipped)
    mean = (0.03 + 0.06) / 2
    std = (((0.03 - mean) ** 2 + (0.06 - mean) ** 2) / 1) ** 0.5
    assert one_month["sharpe"] == pytest.approx(mean / std)
    assert one_month["avg_confidence"] == pytest.approx(0.5)
    assert one_month["calibration_gap"] == pytest.approx(0.5 - 1.0)
    assert one_month["recommendation_frequency"] == {"Maintain": 1, "Trim": 1}
    assert table["1w"]["sharpe"] is None  # a single observation has no dispersion
    assert table["1y"]["n"] == 0 and table["1y"]["rmse"] is None


# -- trim buckets --------------------------------------------------------------------


def test_trim_buckets_monotonicity_and_rank_correlation() -> None:
    pairs = [(10, 0.08), (15, 0.06), (30, 0.03), (50, 0.0), (70, -0.02), (85, -0.05), (95, -0.09)]
    rows = [row(trim=t, expected_excess=0.01, actual_excess=a) for t, a in pairs]
    result = trim_analytics(rows)
    buckets = {b["bucket"]: b for b in result["buckets"]}
    assert buckets["0-20"]["avg_actual_excess"] == pytest.approx(0.07)
    assert buckets["80-100"]["avg_actual_excess"] == pytest.approx(-0.07)
    assert buckets["0-20"]["hit_rate"] == 1.0  # maintain side: positive excess
    assert buckets["80-100"]["hit_rate"] == 1.0  # trim side: negative excess
    assert buckets["40-60"]["hit_rate"] is None  # neutral band claims nothing
    assert result["monotonic"] is True and result["inversions"] == 0
    assert result["rank_correlation"] == pytest.approx(-1.0)


def test_trim_buckets_detect_inversions() -> None:
    pairs = [(10, -0.05), (30, 0.01), (50, 0.0), (70, 0.04), (90, 0.06)]
    rows = [row(trim=t, expected_excess=0.01, actual_excess=a) for t, a in pairs]
    result = trim_analytics(rows)
    assert result["monotonic"] is False
    assert result["inversions"] >= 1
    assert result["rank_correlation"] > 0  # backwards scores show positive correlation


# -- regimes -------------------------------------------------------------------------


def daily(start: date, values: list[float]) -> list[tuple[date, float]]:
    return [(start + timedelta(days=i), v) for i, v in enumerate(values)]


def classifier(*, bull: bool, vix: float, rising: bool, inflationary: bool) -> RegimeClassifier:
    start = AS_OF - timedelta(days=400)
    closes = [100 + (0.1 if bull else -0.1) * i for i in range(300)]
    fed_now, fed_prior = (4.0, 3.0) if rising else (3.0, 4.0)
    # Four anchors hit by the four lookups exactly:
    #   yoy(now)   = cpi(-5d) / cpi(-370d) - 1     (base = last obs <= as_of - 365d)
    #   yoy(prior) = cpi(-185d) / cpi(-550d) - 1   (base = last obs <= as_of - 547d)
    # inflationary: 110.25/105 - 1 = 5.0%  >  103/100 - 1 = 3.0%
    # disinflationary: 104/105 - 1 = -0.95%  <  3.0%
    cpi_now = 110.25 if inflationary else 104.0
    return RegimeClassifier(
        spy_closes=daily(start, closes),
        vix=[(AS_OF - timedelta(days=3), vix)],
        fedfunds=[
            (AS_OF - timedelta(days=200), fed_prior),
            (AS_OF - timedelta(days=10), fed_now),
        ],
        cpi=[
            (AS_OF - timedelta(days=550), 100.0),
            (AS_OF - timedelta(days=370), 105.0),
            (AS_OF - timedelta(days=185), 103.0),
            (AS_OF - timedelta(days=5), cpi_now),
        ],
    )


def test_regime_classification_all_dimensions() -> None:
    up = classifier(bull=True, vix=25.0, rising=True, inflationary=True)
    assert up.classify(AS_OF) == {
        "trend": "bull",
        "volatility": "high_vix",
        "rates": "rising_rates",
        "inflation": "inflationary",
    }
    down = classifier(bull=False, vix=12.0, rising=False, inflationary=False)
    assert down.classify(AS_OF) == {
        "trend": "bear",
        "volatility": "low_vix",
        "rates": "falling_rates",
        "inflation": "disinflationary",
    }


def test_regime_classification_is_honest_about_missing_history() -> None:
    sparse = RegimeClassifier(
        spy_closes=daily(AS_OF - timedelta(days=50), [100.0] * 30),
        vix=[],
        fedfunds=[(AS_OF - timedelta(days=1), 4.0)],  # no 6-month-old value
        cpi=[],
    )
    assert sparse.classify(AS_OF) == {
        "trend": None,
        "volatility": None,
        "rates": None,
        "inflation": None,
    }


def test_regime_analytics_groups_outcomes() -> None:
    c = classifier(bull=True, vix=25.0, rising=True, inflationary=True)
    rows = [
        row(actual_excess=0.02, error=0.01, direction=True),
        row(actual_excess=-0.01, error=-0.02, direction=False),
    ]
    table = regime_analytics(rows, c)
    bull_rows = [r for r in table if r["dimension"] == "trend"]
    assert bull_rows == [
        {
            "dimension": "trend",
            "regime": "bull",
            "n": 2,
            "direction_accuracy": 0.5,
            "mae": pytest.approx(0.015),
            "avg_actual_excess": pytest.approx(0.005),
        }
    ]
    assert {r["dimension"] for r in table} == {"trend", "volatility", "rates", "inflation"}


# -- determinism, serialization, isolation -------------------------------------------


def test_analytics_deterministic_and_json_round_trip() -> None:
    rows = [
        row(confidence=0.3, expected_excess=0.02, actual_excess=0.01, trim=25.0),
        row(confidence=0.7, expected_excess=-0.01, actual_excess=-0.03, trim=75.0, horizon="3m"),
    ]
    outputs = {
        "calibration": calibration_table(rows),
        "models": model_analytics(rows),
        "horizons": horizon_analytics(rows),
        "trim": trim_analytics(rows),
    }
    again = {
        "calibration": calibration_table(list(rows)),
        "models": model_analytics(list(rows)),
        "horizons": horizon_analytics(list(rows)),
        "trim": trim_analytics(list(rows)),
    }
    assert outputs == again
    assert json.loads(json.dumps(outputs)) == outputs


def test_evaluation_layer_isolation() -> None:
    """Evaluation consumes TrimAssessments and market data through its
    repository — never models, features, providers, or portfolio logic."""
    import mip.evaluation.analytics
    import mip.evaluation.archive
    import mip.evaluation.outcomes
    import mip.evaluation.regimes

    forbidden = (
        "mip.models",
        "mip.features",
        "mip.providers",
        "mip.portfolio",
        "mip.research",
        "mip.ingestion",
        "mip.domain",
    )
    allowed = {"mip.engine.trim", "mip.repositories.predictions", "mip.core.exceptions"}
    for module in (
        mip.evaluation.analytics,
        mip.evaluation.archive,
        mip.evaluation.outcomes,
        mip.evaluation.regimes,
    ):
        tree = ast.parse(inspect.getsource(module))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        for name in imported:
            assert not name.startswith(forbidden), f"{module.__name__} imports {name}"
            if name.startswith("mip.") and not name.startswith("mip.evaluation"):
                assert name in allowed, f"{module.__name__} imports {name}"
