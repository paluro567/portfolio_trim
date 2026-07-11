"""Evidence statistics and scoring math: hand-verified correctness."""

import math
from datetime import date

import pandas as pd
import pytest

from mip.models.base import (
    combine_evidence,
    confidence_from_evidence,
    recency_weighted_stats,
    score_from_z,
)
from mip.models.rates import HORIZONS, InterestRateModel, RateRegime, all_regimes

AS_OF = date(2026, 7, 10)


def series(values: dict[date, float]) -> pd.Series:
    return pd.Series(list(values.values()), index=pd.to_datetime(list(values.keys())))


def test_uniform_weights_reduce_to_ordinary_stats() -> None:
    returns = series(
        {
            date(2026, 1, 5): 0.10,
            date(2026, 2, 5): -0.05,
            date(2026, 3, 5): 0.20,
            date(2026, 4, 5): 0.05,
        }
    )
    stats = recency_weighted_stats(returns, AS_OF, half_life_years=1e9)  # no decay

    assert stats.n == 4
    assert stats.n_eff == pytest.approx(4.0)
    assert stats.mean == pytest.approx(0.075)
    assert stats.se == pytest.approx(math.sqrt((0.0325 / 3) / 4))  # s/sqrt(n)
    assert stats.hit_rate == pytest.approx(0.75)
    assert stats.first_event == date(2026, 1, 5)
    assert stats.last_event == date(2026, 4, 5)


def test_recency_shifts_mean_toward_recent_events() -> None:
    returns = series(
        {
            date(2016, 7, 10): -0.10,  # ten years old
            date(2026, 7, 10): +0.10,  # today
        }
    )
    stats = recency_weighted_stats(returns, AS_OF, half_life_years=5.0)
    assert stats.mean > 0  # the recent event dominates
    assert stats.n_eff < 2.0  # unequal weights reduce effective n


def test_fewer_than_two_events_is_no_evidence() -> None:
    assert recency_weighted_stats(series({date(2026, 1, 5): 0.1}), AS_OF, 10.0) is None
    assert recency_weighted_stats(pd.Series(dtype=float), AS_OF, 10.0) is None


def test_combine_single_study_passes_through() -> None:
    combined = combine_evidence([0.02], [0.01])
    assert combined.effect == pytest.approx(0.02)
    assert combined.se == pytest.approx(0.01)
    assert combined.z == pytest.approx(2.0)
    assert combined.agreement == pytest.approx(1.0)


def test_combine_is_inverse_variance_weighted() -> None:
    # weights 1/0.01² = 10000 and 1/0.02² = 2500 -> 4:1
    combined = combine_evidence([0.02, -0.03], [0.01, 0.02])
    expected = (10000 * 0.02 + 2500 * -0.03) / 12500  # +0.01
    assert combined.effect == pytest.approx(expected)
    assert combined.se == pytest.approx(math.sqrt(1 / 12500))
    assert combined.agreement == pytest.approx(10000 / 12500)  # dissenter down-weighted


def test_combined_z_is_clipped() -> None:
    combined = combine_evidence([0.5], [0.001])  # z would be 500
    assert combined.z == pytest.approx(4.0)


def test_score_mapping_is_calibrated() -> None:
    assert score_from_z(0.0) == pytest.approx(50.0)
    assert score_from_z(1.959963984540054) == pytest.approx(97.5)
    assert score_from_z(-1.959963984540054) == pytest.approx(2.5)
    assert 0.0 < score_from_z(-4.0) < score_from_z(4.0) < 100.0


def test_confidence_combines_volume_and_agreement() -> None:
    # exactly `prior_events` effective events with full agreement -> 0.5
    assert confidence_from_evidence(30.0, 1.0, prior_events=30.0) == pytest.approx(0.5)
    assert confidence_from_evidence(1e9, 1.0, prior_events=30.0) == pytest.approx(1.0, abs=1e-6)
    assert confidence_from_evidence(30.0, 0.5, 30.0) == pytest.approx(0.25)
    assert confidence_from_evidence(0.0, 1.0, 30.0) == 0.0


# -- regime grammar -----------------------------------------------------------


def test_regime_library_covers_spec() -> None:
    regimes = all_regimes()
    assert len(regimes) == 2 * 4 * 6  # series x windows x signed thresholds
    assert len({r.label for r in regimes}) == len(regimes)
    assert set(HORIZONS.values()) == {5, 10, 21, 63, 126, 252}


def test_regime_filters_use_percentage_points() -> None:
    rising = RateRegime("10Y", 21, +50, "dgs10_chg_21d")
    assert rising.research_filter.op == ">=" and rising.research_filter.value == 0.5
    falling = RateRegime("2Y", 63, -25, "dgs2_chg_63d")
    assert falling.research_filter.op == "<=" and falling.research_filter.value == -0.25
    assert "fell more than 25 bps over 63 sessions" in falling.description


def test_no_active_regimes_yields_neutral_scores() -> None:
    model = InterestRateModel.__new__(InterestRateModel)  # no DB needed on this path
    model.half_life_years, model.min_events, model.prior_events = 10.0, 5, 30.0
    model._latest_changes = lambda as_of: ({}, AS_OF)
    model._active_regimes = lambda values: []

    scores = model.evaluate("ANY")

    assert [s.horizon for s in scores] == list(HORIZONS)
    for s in scores:
        assert s.score == 50.0 and s.confidence == 0.0
        assert s.expected_return is None and s.sample_size == 0
        assert "No interest-rate regime is currently active" in s.explanation
