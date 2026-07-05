"""Statistical accuracy of ResearchMetric against hand-computed values."""

import math

import pandas as pd
import pytest

from mip.research.metrics import Z_95, summarize

RETURNS = [0.10, -0.05, 0.20, 0.05]
# hand-derived: mean 0.075; sorted [-0.05, 0.05, 0.10, 0.20]
# deviations [0.025, -0.125, 0.125, -0.025] -> ss = 0.0325 -> var = 0.0325/3
STD = math.sqrt(0.0325 / 3)


def test_summary_golden_values() -> None:
    metric = summarize(21, pd.Series(RETURNS))

    assert metric.horizon == 21
    assert metric.sample_size == 4
    assert metric.mean == pytest.approx(0.075)
    assert metric.median == pytest.approx(0.075)  # midpoint of 0.05 and 0.10
    assert metric.volatility == pytest.approx(STD)
    assert metric.hit_rate == pytest.approx(0.75)  # three of four positive
    assert metric.max_gain == pytest.approx(0.20)
    assert metric.max_loss == pytest.approx(-0.05)
    # pandas linear interpolation: q25 between -0.05 and 0.05, q75 between 0.10 and 0.20
    assert metric.q25 == pytest.approx(0.025)
    assert metric.q75 == pytest.approx(0.125)
    half_width = Z_95 * STD / 2  # sqrt(4)
    assert metric.ci_low == pytest.approx(0.075 - half_width)
    assert metric.ci_high == pytest.approx(0.075 + half_width)


def test_histogram_partitions_the_sample() -> None:
    metric = summarize(5, pd.Series(RETURNS))
    assert sum(count for _, _, count in metric.histogram) == 4
    assert metric.histogram[0][0] == pytest.approx(-0.05)  # first bin starts at min
    assert metric.histogram[-1][1] == pytest.approx(0.20)  # last bin ends at max


def test_empty_sample_reports_zero_not_fake_stats() -> None:
    metric = summarize(63, pd.Series(dtype=float))
    assert metric.sample_size == 0
    assert metric.mean is None and metric.hit_rate is None and metric.ci_low is None
    assert metric.histogram == ()


def test_single_observation_has_no_dispersion_stats() -> None:
    metric = summarize(1, pd.Series([0.03]))
    assert metric.sample_size == 1
    assert metric.mean == pytest.approx(0.03)
    assert metric.median == pytest.approx(0.03)
    assert metric.volatility is None  # undefined for n=1
    assert metric.ci_low is None and metric.ci_high is None
    assert metric.hit_rate == pytest.approx(1.0)


def test_nans_are_dropped_before_stats() -> None:
    metric = summarize(5, pd.Series([0.1, float("nan"), -0.1]))
    assert metric.sample_size == 2
    assert metric.mean == pytest.approx(0.0)
    assert metric.hit_rate == pytest.approx(0.5)
