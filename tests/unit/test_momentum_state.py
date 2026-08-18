"""Momentum-state study: PIT integrity and design-constant guarantees.

The study's only defensible claim is that its history is honest, so these tests
target exactly that: percentiles that cannot see the future, an embargo that
cannot let a design label reach past the split, and a price-poisoning
invariance in the pattern of tests/integration/test_pit_alignment.py.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from mip.research.momentum_state import (
    BUCKET_EDGES,
    BUCKET_LABELS,
    HORIZONS,
    MIN_EPISODES,
    MIN_OWN_HISTORY,
    SPLIT,
    Observation,
    _pit_percentile_series,
    bucket_of,
    build_observations,
    leakage_violations,
    split_observations,
    summarise,
)


def _series(n: int, seed: int = 0) -> tuple[list[date], np.ndarray]:
    rng = np.random.default_rng(seed)
    start = date(2009, 1, 1)
    dates, d = [], start
    while len(dates) < n:
        if d.weekday() < 5:
            dates.append(d)
        d += timedelta(days=1)
    steps = rng.normal(0.0005, 0.02, n)
    return dates, 100.0 * np.exp(np.cumsum(steps))


# -- design constants ---------------------------------------------------------
def test_buckets_are_the_preregistered_edges():
    assert BUCKET_EDGES == (0.0, 0.20, 0.40, 0.60, 0.80, 0.90, 0.95, 0.99, 1.0)
    assert len(BUCKET_LABELS) == len(BUCKET_EDGES) - 1


@pytest.mark.parametrize(
    "pct,idx",
    [(0.0, 0), (0.19, 0), (0.20, 1), (0.85, 4), (0.90, 5), (0.96, 6), (0.995, 7), (1.0, 7)],
)
def test_bucket_boundaries_are_exact(pct, idx):
    assert bucket_of(pct) == idx


def test_only_short_horizons_are_in_scope():
    assert set(HORIZONS) == {"1w", "1m"}


# -- point-in-time percentile -------------------------------------------------
def test_percentile_is_undefined_before_min_history():
    r = np.arange(300, dtype=float)
    out = _pit_percentile_series(r, MIN_OWN_HISTORY)
    assert np.isnan(out[: MIN_OWN_HISTORY - 1]).all()
    assert not np.isnan(out[MIN_OWN_HISTORY - 1])


def test_percentile_cannot_see_the_future():
    """Truncating the series must not change any surviving percentile."""
    r = np.random.default_rng(3).normal(size=600)
    full = _pit_percentile_series(r, MIN_OWN_HISTORY)
    half = _pit_percentile_series(r[:400], MIN_OWN_HISTORY)
    np.testing.assert_allclose(full[:400], half, equal_nan=True)


def test_monotone_series_puts_latest_at_the_top():
    """A new all-time high scores (n-1)/n, not 1.0: the percentile is the
    fraction STRICTLY below, so the running maximum approaches 1 without
    reaching it. It must still land in the top bucket."""
    r = np.arange(400, dtype=float)
    out = _pit_percentile_series(r, MIN_OWN_HISTORY)
    assert out[-1] == pytest.approx(399 / 400)
    assert bucket_of(float(out[-1])) == len(BUCKET_LABELS) - 1


# -- embargo ------------------------------------------------------------------
def _obs(sym, d, end_1m, excess=0.01):
    return Observation(
        symbol=sym,
        obs_date=d,
        momentum_pct=0.99,
        bucket=7,
        regime_bull=1,
        regime_high_vol=0,
        rel_spy_63d_positive=1,
        fwd={"1m": excess},
        excess={"1m": excess},
        mae={"1m": -0.01},
        mfe={"1m": 0.02},
        outcome_end={"1m": end_1m},
    )


def test_observation_straddling_the_split_is_dropped_from_both_sides():
    straddler = _obs("X", SPLIT - timedelta(days=5), SPLIT + timedelta(days=10))
    design, holdout = split_observations([straddler], "1m")
    assert design == [] and holdout == []


def test_design_labels_never_reach_past_the_split():
    obs = [
        _obs("X", date(2015, 3, 2), date(2015, 4, 1)),
        _obs("X", SPLIT - timedelta(days=3), SPLIT + timedelta(days=20)),
        _obs("X", SPLIT + timedelta(days=5), SPLIT + timedelta(days=35)),
    ]
    design, holdout = split_observations(obs, "1m")
    assert leakage_violations(design, holdout, "1m") == []
    assert all(o.outcome_end["1m"] < SPLIT for o in design)
    assert all(o.obs_date >= SPLIT for o in holdout)


def test_leakage_detector_actually_fires():
    bad = [_obs("X", date(2021, 12, 1), SPLIT + timedelta(days=1))]
    assert leakage_violations(bad, [], "1m")


# -- price poisoning ----------------------------------------------------------
def test_future_prices_cannot_change_past_observations():
    """Corrupt every price after a cutoff; observations whose whole window
    closed before it must be byte-identical. The study's PIT gold standard."""
    dates, close = _series(1200, seed=11)
    bench_dates, bench_close = _series(1200, seed=12)
    regime = {d: (1, 0) for d in dates}
    cutoff_i = 900
    cutoff = dates[cutoff_i]

    clean = build_observations({"AAA": (dates, close), "SPY": (bench_dates, bench_close)}, regime)
    poisoned_close = close.copy()
    poisoned_close[cutoff_i:] *= 3.7
    poisoned_bench = bench_close.copy()
    poisoned_bench[cutoff_i:] *= 0.4
    poisoned = build_observations(
        {"AAA": (dates, poisoned_close), "SPY": (bench_dates, poisoned_bench)}, regime
    )

    def safe(obs):
        return {
            (o.symbol, o.obs_date): (round(o.momentum_pct, 12), o.bucket, round(o.fwd["1m"], 12))
            for o in obs
            if o.symbol == "AAA" and "1m" in o.outcome_end and o.outcome_end["1m"] < cutoff
        }

    a, b = safe(clean), safe(poisoned)
    assert a and a == b


# -- statistics ---------------------------------------------------------------
def test_episode_count_collapses_adjacent_days():
    """20 consecutive sessions in one run are not 20 independent experiments."""
    base = date(2015, 1, 5)
    obs = [_obs("X", base + timedelta(days=i), base + timedelta(days=i + 40)) for i in range(20)]
    s = summarise(obs, "1m", "run")
    assert s.n_raw == 20
    assert s.n_episodes == 1
    assert not s.to_dict()["meets_episode_floor"]


def test_wilson_uses_effective_not_raw_sample():
    base = date(2015, 1, 5)
    obs = [_obs("X", base + timedelta(days=i), base + timedelta(days=i + 40)) for i in range(200)]
    s = summarise(obs, "1m", "run")
    low, high = s.wilson
    assert high - low > 0.5, "1 episode must yield a very wide interval"


def test_episode_floor_constant_is_the_preregistered_thirty():
    assert MIN_EPISODES == 30


# -- tie semantics ------------------------------------------------------------
def test_percentile_tie_semantics_are_strictly_below():
    """Lock the tie rule: the percentile counts values STRICTLY BELOW x.

    This is the specification, not an implementation detail. An abandoned
    ordered-insert draft used bisect_right (counting values <= x); it never
    produced an authoritative result, but the ambiguity cost real review time,
    so the intended semantics are pinned here explicitly.

    Series: 252 distinct warm-up values, then three exact repeats of a value
    that sits above all of them. Under STRICTLY-BELOW each repeat scores
    252/(252+k); under <= they would score (252+k)/(252+k) == 1.0.
    """
    warmup = np.arange(MIN_OWN_HISTORY, dtype=float)
    tied = np.array([1e6, 1e6, 1e6])
    out = _pit_percentile_series(np.concatenate([warmup, tied]), MIN_OWN_HISTORY)

    n = MIN_OWN_HISTORY
    assert out[n] == pytest.approx(n / (n + 1))
    assert out[n + 1] == pytest.approx(n / (n + 2))
    assert out[n + 2] == pytest.approx(n / (n + 3))
    assert all(v < 1.0 for v in out[n:]), "strictly-below can never reach 1.0"


def test_percentile_of_an_all_constant_series_is_zero_not_one():
    """Every value ties every other, so nothing is strictly below any of them.

    Under the abandoned <= rule this would be 1.0. Pinned because flat-price
    stretches (delistings, halts, pre-listing padding) make this the single most
    common tie case in the real universe.
    """
    out = _pit_percentile_series(np.zeros(MIN_OWN_HISTORY + 5), MIN_OWN_HISTORY)
    defined = out[~np.isnan(out)]
    assert defined.size == 6
    assert (defined == 0.0).all()
    assert bucket_of(0.0) == 0, "a fully flat series lands in the bottom bucket"


def test_tie_semantics_do_not_leak_across_the_min_history_boundary():
    """Ties before the warm-up completes still count toward the denominator."""
    r = np.concatenate([np.full(MIN_OWN_HISTORY - 1, 5.0), np.array([7.0, 5.0])])
    out = _pit_percentile_series(r, MIN_OWN_HISTORY)
    n = MIN_OWN_HISTORY
    # index n-1 is 7.0: the n-1 earlier 5.0s are strictly below it
    assert out[n - 1] == pytest.approx((n - 1) / n)
    # index n is 5.0: nothing is strictly below 5.0
    assert out[n] == pytest.approx(0.0)
