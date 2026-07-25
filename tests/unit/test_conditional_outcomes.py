"""Unit tests for the pooled outcome statistics (pure, no I/O)."""

from datetime import date

import numpy as np

from mip.research.outcomes import (
    build_distribution,
    calendar_episodes,
    exceedance_probability,
    herfindahl,
    independence_profile,
    path_excursions,
    wilson_interval,
)
from mip.research.statistics import WeightedSample


class TestWilsonInterval:
    def test_centered_and_ordered(self) -> None:
        low, high = wilson_interval(0.5, 100)
        assert 0.0 <= low < 0.5 < high <= 1.0
        # known Wilson values for p=0.5, n=100 ~ (0.404, 0.596)
        assert abs(low - 0.404) < 0.01
        assert abs(high - 0.596) < 0.01

    def test_effective_n_widens_interval(self) -> None:
        wide = wilson_interval(0.6, 10)
        narrow = wilson_interval(0.6, 200)
        assert (wide[1] - wide[0]) > (narrow[1] - narrow[0])

    def test_clipped_to_unit_interval(self) -> None:
        low, high = wilson_interval(1.0, 5)
        assert low >= 0.0 and high <= 1.0

    def test_degenerate_effective_n(self) -> None:
        assert wilson_interval(0.7, 0.0) == (0.0, 1.0)
        assert wilson_interval(0.7, -3.0) == (0.0, 1.0)


class TestPathExcursions:
    def test_drawdown_and_excursions(self) -> None:
        # entry 100, path 110, 90, 105 -> mfe +10%, mae -10%, mdd from 110->90
        window = np.array([100.0, 110.0, 90.0, 105.0])
        mdd, mae, mfe = path_excursions(window)
        assert abs(mfe - 0.10) < 1e-9
        assert abs(mae + 0.10) < 1e-9
        assert abs(mdd - (90.0 / 110.0 - 1.0)) < 1e-9

    def test_short_window_is_zero(self) -> None:
        assert path_excursions(np.array([100.0])) == (0.0, 0.0, 0.0)


class TestOutcomeDistribution:
    def test_build_distribution_uniform(self) -> None:
        returns = [0.1, -0.05, 0.2, 0.0]
        dates = [date(2020, 1, 6), date(2021, 3, 2), date(2022, 5, 9), date(2023, 8, 1)]
        dist = build_distribution("absolute", WeightedSample.uniform(returns), dates, 21)
        assert dist.n == 4
        assert dist.measure == "absolute"
        # two of four strictly positive -> 0.5 (0.0 is not > 0)
        assert dist.p_positive == 0.5
        assert (
            dist.p_positive_ci is not None and dist.p_positive_ci[0] < 0.5 < dist.p_positive_ci[1]
        )
        # widely-separated dates -> minimal overlap deflation
        assert dist.effective.effective > 3.0

    def test_overlap_deflates_effective_sample(self) -> None:
        returns = [0.1, 0.1, 0.1, 0.1]
        clustered = [date(2020, 1, 6), date(2020, 1, 7), date(2020, 1, 8), date(2020, 1, 9)]
        dist = build_distribution("absolute", WeightedSample.uniform(returns), clustered, 21)
        # four adjacent dates within a 21-session window are heavily overlapping
        assert dist.effective.effective < 2.0

    def test_empty_distribution(self) -> None:
        dist = build_distribution("absolute", WeightedSample.uniform([]), [], 21)
        assert dist.n == 0 and dist.mean is None and dist.p_positive is None

    def test_spy_relative_positive_is_beat_spy(self) -> None:
        excess = [0.02, -0.01, 0.03, -0.04, 0.05]
        dates = [date(2019 + i, 6, 1) for i in range(5)]
        dist = build_distribution("spy_relative", WeightedSample.uniform(excess), dates, 21)
        assert dist.measure == "spy_relative"
        assert dist.p_positive == 0.6  # 3 of 5 beat SPY

    def test_exceedance(self) -> None:
        sample = WeightedSample.uniform([0.1, -0.2, 0.3, -0.4])
        assert exceedance_probability(sample, 0.0, above=True) == 0.5
        assert exceedance_probability(sample, -0.3, above=False) == 0.25
        assert exceedance_probability(WeightedSample.uniform([]), 0.0, above=True) is None


class TestConcentration:
    def test_herfindahl_single_bucket_is_one(self) -> None:
        assert herfindahl(["A", "A", "A"]) == 1.0

    def test_herfindahl_uniform(self) -> None:
        assert abs(herfindahl(["A", "B", "C", "D"]) - 0.25) < 1e-9

    def test_herfindahl_empty(self) -> None:
        assert herfindahl([]) == 0.0

    def test_calendar_episodes_group_by_horizon(self) -> None:
        dates = [
            date(2020, 1, 6),
            date(2020, 1, 8),
            date(2020, 1, 10),
            date(2021, 6, 1),
            date(2021, 6, 3),
        ]
        ids = calendar_episodes(dates, 21)
        assert ids[0] == ids[1] == ids[2]
        assert ids[3] == ids[4]
        assert ids[0] != ids[3]

    def test_calendar_episodes_same_day_cross_symbol_same_episode(self) -> None:
        dates = [date(2020, 3, 2), date(2020, 3, 2)]
        assert len(set(calendar_episodes(dates, 21))) == 1

    def test_independence_profile(self) -> None:
        symbols = ["AMD", "AMD", "NVDA", "TSLA"]
        dates = [date(2020, 1, 6), date(2020, 1, 7), date(2021, 5, 3), date(2022, 8, 9)]
        prof = independence_profile(symbols, dates, 21)
        assert prof.raw_matches == 4
        assert prof.distinct_symbols == 3
        assert prof.distinct_years == 3
        assert prof.distinct_calendar_episodes == 3
        assert prof.symbol_concentration > 0.25


class TestWeightedSample:
    def test_uniform_matches_plain_stats(self) -> None:
        s = WeightedSample.uniform([1.0, 2.0, 3.0, 4.0])
        assert s.mean() == 2.5
        assert s.kish_size() == 4.0
        assert abs(s.quantile(0.5) - 2.5) < 1e-9

    def test_weight_concentration_shrinks_kish(self) -> None:
        s = WeightedSample(np.array([1.0, 2.0, 3.0]), np.array([10.0, 1.0, 1.0]))
        assert s.kish_size() < 3.0
        # weighted mean pulled toward the heavy first value
        assert s.mean() < 2.0
