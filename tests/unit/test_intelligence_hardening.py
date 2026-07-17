"""Hardened evidence aggregation: overlap inflation, cross-regime
correlation, saturation diagnostics, and the empty-series neutral paths.
Every number is hand-derivable from the Bartlett-kernel covariance model."""

import math
from datetime import date, timedelta
from types import SimpleNamespace

import pandas as pd
import pytest

from mip.core.exceptions import ConfigurationError
from mip.domain.enums import FeatureScope
from mip.models.base import (
    Z_CLIP,
    RegimeEvidence,
    aggregate_horizon_evidence,
    combine_evidence,
    cross_regime_correlation,
    overlap_inflation,
    score_from_z,
)

BASE = date(2020, 1, 1)


def d(offset: int) -> date:
    return BASE + timedelta(days=offset)


def days(*offsets: int) -> list[date]:
    return [d(o) for o in offsets]


def make_evidence(label: str, excess: float, se: float, n_eff: float = 20.0) -> RegimeEvidence:
    return RegimeEvidence(
        label=label,
        description=label,
        feature="f",
        n=20,
        n_eff=n_eff,
        mean=0.01 + excess,
        hit_rate=0.6,
        baseline_mean=0.01,
        excess=excess,
        se=se,
        first_event=d(0),
        last_event=d(300),
    )


# -- overlap inflation (within a study) -----------------------------------------


def test_non_overlapping_events_have_no_inflation() -> None:
    # horizon 21 sessions ~ 29.4 calendar days; gaps of 100 days never overlap
    assert overlap_inflation(days(0, 100, 200), 21) == pytest.approx(1.0)


def test_single_or_empty_event_set_has_no_inflation() -> None:
    assert overlap_inflation(days(0), 252) == 1.0
    assert overlap_inflation([], 252) == 1.0


def test_coincident_events_inflate_by_their_count() -> None:
    # four identical windows = one observation counted four times
    assert overlap_inflation([d(0)] * 4, 21) == pytest.approx(4.0)


def test_partial_overlap_matches_bartlett_kernel() -> None:
    # horizon 10 sessions = 14 calendar days; gap 7 days -> kernel 0.5
    # inflation = (2 + 2*0.5) / 2 = 1.5
    assert overlap_inflation(days(0, 7), 10) == pytest.approx(1.5)


def test_dense_events_lose_almost_all_independence() -> None:
    # daily events under a 1y horizon: n=50 events, ~none independent
    dense = days(*range(50))
    inflation = overlap_inflation(dense, 252)
    assert inflation > 40.0  # ~n when every window overlaps almost fully
    assert inflation <= 50.0


# -- cross-regime correlation ------------------------------------------------------


def test_identical_event_sets_are_perfectly_correlated() -> None:
    a = days(0, 30, 60)
    assert cross_regime_correlation(a, list(a), 21) == pytest.approx(1.0)


def test_distant_event_sets_are_uncorrelated() -> None:
    assert cross_regime_correlation(days(0, 30), days(500, 530), 21) == 0.0


def test_correlation_is_symmetric_and_bounded() -> None:
    a, b = days(0, 20, 40, 60), days(5, 25, 45)
    rho = cross_regime_correlation(a, b, 21)
    assert rho == pytest.approx(cross_regime_correlation(b, a, 21))
    assert 0.0 < rho < 1.0


# -- correlated combination ---------------------------------------------------------


def test_identity_correlation_reproduces_independent_combination() -> None:
    effects, ses = [0.02, -0.03], [0.01, 0.02]
    independent = combine_evidence(effects, ses)
    identity = combine_evidence(effects, ses, [[1.0, 0.0], [0.0, 1.0]])
    assert identity.effect == pytest.approx(independent.effect)
    assert identity.se == pytest.approx(independent.se)
    assert identity.z == pytest.approx(independent.z)


def test_fully_correlated_duplicates_add_no_precision() -> None:
    """The same study entered twice with rho=1 must not shrink the SE —
    the sqrt(2) 'free precision' of naive pooling is the saturation bug."""
    single = combine_evidence([0.02], [0.01])
    doubled = combine_evidence([0.02, 0.02], [0.01, 0.01], [[1.0, 1.0], [1.0, 1.0]])
    assert doubled.se == pytest.approx(single.se)
    assert doubled.z == pytest.approx(single.z)


def test_z_raw_records_the_unclipped_value() -> None:
    combined = combine_evidence([0.5], [0.001])
    assert combined.z == pytest.approx(Z_CLIP)
    assert combined.z_raw == pytest.approx(500.0)
    mild = combine_evidence([0.01], [0.01])
    assert mild.z_raw == pytest.approx(mild.z) == pytest.approx(1.0)


# -- shared horizon aggregation -------------------------------------------------------


def test_duplicate_evidence_does_not_raise_confidence_or_score() -> None:
    evidence = make_evidence("A", excess=0.02, se=0.01)
    shared_dates = days(0, 60, 120, 180)

    once = aggregate_horizon_evidence([evidence], [shared_dates], 21, 1, prior_events=30.0)
    twice = aggregate_horizon_evidence(
        [evidence, evidence], [shared_dates, list(shared_dates)], 21, 2, prior_events=30.0
    )

    assert twice.confidence == pytest.approx(once.confidence)
    assert twice.score == pytest.approx(once.score)
    assert twice.diagnostics.mean_cross_correlation == pytest.approx(1.0)


def test_highly_overlapping_regimes_barely_add_certainty() -> None:
    """Two regimes firing one day apart at a 63-session horizon are nearly
    the same experiment: combined |z| must stay close to a single study's,
    far below the sqrt(2) gain independence would grant."""
    a = days(0, 90, 180, 270)
    b = days(1, 91, 181, 271)
    e1 = make_evidence("A", excess=0.02, se=0.01)
    e2 = make_evidence("B", excess=0.02, se=0.01)

    one = aggregate_horizon_evidence([e1], [a], 63, 1, prior_events=30.0)
    both = aggregate_horizon_evidence([e1, e2], [a, b], 63, 2, prior_events=30.0)

    assert both.diagnostics.mean_cross_correlation > 0.9
    assert abs(both.diagnostics.z_raw) < abs(one.diagnostics.z_raw) * 1.05
    assert abs(both.diagnostics.z_raw) < abs(one.diagnostics.z_raw) * math.sqrt(2)


def test_contradictory_regimes_cancel_toward_neutral() -> None:
    bull = make_evidence("bull", excess=+0.02, se=0.01)
    bear = make_evidence("bear", excess=-0.02, se=0.01)
    agg = aggregate_horizon_evidence(
        [bull, bear], [days(0, 90, 180), days(500, 590, 680)], 21, 2, prior_events=30.0
    )
    assert agg.score == pytest.approx(50.0)
    assert agg.diagnostics.agreement == pytest.approx(0.5)
    assert agg.confidence == pytest.approx(0.5 * 20.0 / 50.0)  # volume x agreement
    assert agg.supporting[0].label == "bull" and agg.negative[0].label == "bear"


def test_saturation_is_flagged_not_hidden() -> None:
    strong = make_evidence("strong", excess=0.10, se=0.001)
    agg = aggregate_horizon_evidence([strong], [days(0, 90, 180)], 21, 1, prior_events=30.0)
    assert agg.diagnostics.saturated
    assert agg.diagnostics.z_raw == pytest.approx(100.0)
    assert agg.diagnostics.z_clipped == pytest.approx(Z_CLIP)
    assert agg.score == pytest.approx(score_from_z(Z_CLIP))

    calm = make_evidence("calm", excess=0.01, se=0.01)
    agg = aggregate_horizon_evidence([calm], [days(0, 90, 180)], 21, 1, prior_events=30.0)
    assert not agg.diagnostics.saturated
    assert agg.diagnostics.z_raw == pytest.approx(agg.diagnostics.z_clipped)


def test_diagnostics_report_the_aggregation_inputs() -> None:
    e1 = make_evidence("A", excess=0.02, se=0.01, n_eff=40.0)
    e2 = make_evidence("B", excess=0.01, se=0.02, n_eff=15.0)
    agg = aggregate_horizon_evidence(
        [e1, e2], [days(0, 90), days(45, 135)], 21, 5, prior_events=30.0
    )
    diag = agg.diagnostics
    assert diag.active_regimes == 5 and diag.evidence_studies == 2
    assert diag.max_n_eff == pytest.approx(40.0)
    assert 0.0 <= diag.mean_cross_correlation <= 1.0
    payload = diag.to_dict()
    assert set(payload) == {
        "active_regimes",
        "evidence_studies",
        "max_n_eff",
        "mean_cross_correlation",
        "agreement",
        "z_raw",
        "z_clipped",
        "saturated",
    }


# -- empty-series neutral paths (regression: TypeError on empty RangeIndex) -----------


def _empty_feature_repo(scope: FeatureScope = FeatureScope.MARKET) -> SimpleNamespace:
    return SimpleNamespace(
        get_definition=lambda name: SimpleNamespace(id=1, scope=scope),
        get_market_series=lambda feature_id: pd.Series(dtype=float),
        get_instrument_series=lambda feature_id, instrument_id: pd.Series(dtype=float),
    )


def test_rates_empty_series_at_as_of_is_neutral() -> None:
    from mip.models.rates import HORIZONS, InterestRateModel

    model = InterestRateModel.__new__(InterestRateModel)
    model.half_life_years, model.min_events, model.prior_events = 10.0, 5, 30.0
    model._features = _empty_feature_repo()

    scores = model.evaluate("ANY", as_of=date(2020, 1, 2))

    assert [s.horizon for s in scores] == list(HORIZONS)
    for s in scores:
        assert s.as_of == date(2020, 1, 2)
        assert s.score == 50.0 and s.confidence == 0.0
        assert s.expected_return is None and s.sample_size == 0
        assert s.diagnostics is None
        assert "insufficient data" in s.explanation.lower()


def test_rates_nothing_stored_without_as_of_still_raises() -> None:
    """No as_of + empty store = misconfiguration; the loud error stays."""
    from mip.models.rates import InterestRateModel

    model = InterestRateModel.__new__(InterestRateModel)
    model.half_life_years, model.min_events, model.prior_events = 10.0, 5, 30.0
    model._features = _empty_feature_repo()

    with pytest.raises(ConfigurationError, match="no rate-change features stored"):
        model.evaluate("ANY")


def test_sector_empty_series_at_as_of_is_neutral() -> None:
    from mip.models.sector import HORIZONS, SectorRotationModel

    model = SectorRotationModel.__new__(SectorRotationModel)
    model.half_life_years, model.min_events, model.prior_events = 10.0, 5, 30.0
    model._sector_etf = lambda symbol: "XLK"
    model._features = _empty_feature_repo()
    model._instrument_id = lambda symbol: 1

    scores = model.evaluate("AMD", as_of=date(2020, 1, 2))

    assert [s.horizon for s in scores] == list(HORIZONS)
    for s in scores:
        assert s.score == 50.0 and s.confidence == 0.0
        assert "insufficient data" in s.explanation.lower()
