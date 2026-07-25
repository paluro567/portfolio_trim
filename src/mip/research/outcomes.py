"""Outcome distributions and independence accounting for pooled research.

Pure computation — no I/O, no ``mip.models`` imports. Builds on
``mip.research.statistics`` (WeightedSample / EffectiveSample), so with 6a in
place the whole Probability-Engine computation (point statistics AND
effective-sample uncertainty) lives cohesively in the research layer; the model
layer above only maps the result onto the evidence contract.

Every distribution is built from a ``WeightedSample`` and an ``EffectiveSample``
so that future match weighting changes only the weights, never these functions.
The same ``OutcomeDistribution`` serves absolute, SPY-relative, and
sector-relative measures (the "positive" probability of the SPY-relative
distribution is exactly P(beat SPY)).

Statistical choices (declared, consistent with the platform):
- Probability intervals use the WILSON score interval on the EFFECTIVE sample
  size, not the raw match count — overlapping/adjacent observations are not
  independent, and using raw n is precisely the precision overstatement the
  analogue RCA (RC1) flagged.
- Path excursions reuse the analogue engine's construction so both engines
  report comparable path risk.
- Concentration is the Herfindahl-Hirschman index over bucket labels in
  ``[1/k, 1]`` — 1.0 means one bucket (symbol/year/episode) dominates.
"""

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np

from mip.research.statistics import EffectiveSample, WeightedSample, effective_sample

Z_95 = 1.959963984540054  # NormalDist().inv_cdf(0.975); scipy stays out of the tree


# -- probability intervals -----------------------------------------------------


def wilson_interval(p_hat: float, n_eff: float, z: float = Z_95) -> tuple[float, float]:
    """Wilson score interval for a proportion, evaluated on the EFFECTIVE
    sample size. Returns ``(low, high)`` clipped to ``[0, 1]``. Degenerate
    ``n_eff <= 0`` yields the maximally uninformative ``(0, 1)``."""
    if n_eff <= 0.0:
        return 0.0, 1.0
    p = min(1.0, max(0.0, p_hat))
    denom = 1.0 + z * z / n_eff
    center = (p + z * z / (2.0 * n_eff)) / denom
    half = (z / denom) * math.sqrt(p * (1.0 - p) / n_eff + z * z / (4.0 * n_eff * n_eff))
    return max(0.0, center - half), min(1.0, center + half)


# -- path excursions -----------------------------------------------------------


def path_excursions(price_window: np.ndarray) -> tuple[float, float, float]:
    """``(max_drawdown, max_adverse_excursion, max_favourable_excursion)`` for
    one entry, from an adjusted-price window whose first element is the entry
    bar and the rest is the forward path through the horizon. Identical
    construction to the analogue engine. Returns ``(0, 0, 0)`` for a window too
    short to have a forward path."""
    if price_window.size < 2 or price_window[0] == 0.0:
        return 0.0, 0.0, 0.0
    path = price_window / price_window[0]
    mae = float(path[1:].min() - 1.0)
    mfe = float(path[1:].max() - 1.0)
    mdd = float((price_window / np.maximum.accumulate(price_window) - 1.0).min())
    return mdd, mae, mfe


# -- outcome distribution ------------------------------------------------------


@dataclass(frozen=True)
class OutcomeDistribution:
    """Summary of one pooled set of forward outcomes (one horizon, one measure)
    with effective-sample-aware uncertainty on its positive-probability."""

    measure: str  # 'absolute' | 'spy_relative' | 'sector_relative'
    effective: EffectiveSample
    n: int
    mean: float | None
    median: float | None
    dispersion: float | None  # weighted std, Kish bias-corrected
    p_positive: float | None
    p_positive_ci: tuple[float, float] | None
    p10: float | None
    p25: float | None
    p75: float | None
    p90: float | None

    def to_dict(self) -> dict:
        return {
            "measure": self.measure,
            "effective": self.effective.to_dict(),
            "n": self.n,
            "mean": self.mean,
            "median": self.median,
            "dispersion": self.dispersion,
            "p_positive": self.p_positive,
            "p_positive_ci": list(self.p_positive_ci) if self.p_positive_ci else None,
            "p10": self.p10,
            "p25": self.p25,
            "p75": self.p75,
            "p90": self.p90,
        }


def _empty_distribution(measure: str, effective: EffectiveSample) -> OutcomeDistribution:
    return OutcomeDistribution(
        measure, effective, 0, None, None, None, None, None, None, None, None, None
    )


def build_distribution(
    measure: str,
    sample: WeightedSample,
    dates: Sequence[date],
    horizon_sessions: int,
) -> OutcomeDistribution:
    """Summarise a weighted sample of forward outcomes for one horizon. ``dates``
    are the observation dates aligned to ``sample.values`` (grouped into calendar
    episodes for the effective sample); the positive-probability interval is a
    Wilson interval on the effective sample size."""
    n_episodes = len(set(calendar_episodes(dates, horizon_sessions)))
    effective = effective_sample(sample, n_episodes)
    n = len(sample)
    if n == 0:
        return _empty_distribution(measure, effective)
    p_positive = sample.probability(sample.values > 0.0)
    ci = wilson_interval(p_positive, effective.effective) if p_positive is not None else None
    return OutcomeDistribution(
        measure=measure,
        effective=effective,
        n=n,
        mean=sample.mean(),
        median=sample.quantile(0.5),
        dispersion=sample.std(),
        p_positive=p_positive,
        p_positive_ci=ci,
        p10=sample.quantile(0.10),
        p25=sample.quantile(0.25),
        p75=sample.quantile(0.75),
        p90=sample.quantile(0.90),
    )


def exceedance_probability(sample: WeightedSample, threshold: float, above: bool) -> float | None:
    """Weighted P(value > threshold) if ``above`` else P(value < threshold).
    None on an empty sample."""
    if len(sample) == 0:
        return None
    mask = sample.values > threshold if above else sample.values < threshold
    return sample.probability(mask)


# -- independence / concentration accounting -----------------------------------


def herfindahl(labels: Sequence) -> float:
    """HHI over bucket labels: ``Σ (count/total)²`` in ``[1/k, 1]``. 1.0 = one
    bucket holds everything (maximal concentration); 0.0 for an empty input."""
    total = len(labels)
    if total == 0:
        return 0.0
    counts = Counter(labels)
    return float(sum((c / total) ** 2 for c in counts.values()))


def distinct_years(dates: Sequence[date]) -> int:
    return len({d.year for d in dates})


@dataclass(frozen=True)
class IndependenceProfile:
    """How independent a pooled cross-sectional sample really is — the
    machinery the analogue RCA showed a single-symbol raw count lacks."""

    raw_matches: int
    distinct_symbols: int
    distinct_years: int
    distinct_calendar_episodes: int  # date clusters within the horizon window
    year_concentration: float  # HHI over match years
    symbol_concentration: float  # HHI over match symbols
    episode_concentration: float  # HHI over calendar-episode ids

    def to_dict(self) -> dict:
        return {
            "raw_matches": self.raw_matches,
            "distinct_symbols": self.distinct_symbols,
            "distinct_years": self.distinct_years,
            "distinct_calendar_episodes": self.distinct_calendar_episodes,
            "year_concentration": self.year_concentration,
            "symbol_concentration": self.symbol_concentration,
            "episode_concentration": self.episode_concentration,
        }


def calendar_episodes(dates: Sequence[date], horizon_sessions: int) -> list[int]:
    """Assign each date to a calendar-episode id: a new episode starts when a
    date is more than ``horizon_sessions`` calendar days after the previous one.
    Pooled dates from different symbols on the same day fall in the same
    episode — the whole point, since same-day cross-symbol outcomes share the
    market move and are not independent experiments."""
    if not dates:
        return []
    order = sorted(range(len(dates)), key=lambda i: dates[i])
    span = horizon_sessions * 7.0 / 5.0  # sessions -> calendar days
    ids = [0] * len(dates)
    current = 0
    prev = dates[order[0]]
    for k, idx in enumerate(order):
        if k > 0:
            if (dates[idx] - prev).days > span:
                current += 1
            prev = dates[idx]
        ids[idx] = current
    return ids


def independence_profile(
    symbols: Sequence[str], dates: Sequence[date], horizon_sessions: int
) -> IndependenceProfile:
    """Full concentration/independence accounting for a pooled sample of
    ``(symbol, date)`` matches at one horizon."""
    episodes = calendar_episodes(dates, horizon_sessions)
    return IndependenceProfile(
        raw_matches=len(dates),
        distinct_symbols=len(set(symbols)),
        distinct_years=distinct_years(dates),
        distinct_calendar_episodes=len(set(episodes)),
        year_concentration=herfindahl([d.year for d in dates]),
        symbol_concentration=herfindahl(list(symbols)),
        episode_concentration=herfindahl(episodes),
    )
