"""Reusable research statistics primitives — dependency-free.

Small, pure infrastructure shared by every research model (regime models, the
analogue engine, the conditional probability engine, and future ones). Imports
only the standard library and numpy; it must NEVER import from ``mip.models``
or any data layer, so it can sit at the bottom of the research stack.

Contents are deliberately generic:
- ``overlap_inflation`` / ``cross_regime_correlation``: the Bartlett-kernel
  geometry that stops overlapping forward-return windows from masquerading as
  independent observations.
- ``combine_evidence`` / ``CombinedEvidence``: correlated fixed-effect
  meta-analysis.
- ``score_from_z`` / ``confidence_from_evidence``: the shared 0-100 evidence
  score and the volume x agreement confidence.
- ``WeightedSample``: a values+weights container with weighted moments and Kish
  effective size — every statistic in the research layer is built on it so that
  future match weighting is a new weighting function, never a statistics
  rewrite. Version 1 callers pass uniform weights.
- ``EffectiveSample``: combines the Kish (weight) effective size with the
  Bartlett (temporal overlap) deflation into one honest effective-N.

Extracted from ``mip.models.base`` (which now re-exports these for its existing
consumers) so the primitives live once, at the research layer, reusable by
models that never needed the regime-study machinery around them.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from statistics import NormalDist

import numpy as np

_NORMAL = NormalDist()
Z_CLIP = 4.0
_SESSIONS_TO_DAYS = 7.0 / 5.0  # trading sessions -> calendar days for the kernel


# -- overlap geometry (Bartlett kernel over event dates) -----------------------


def _gram(a: np.ndarray, b: np.ndarray, horizon_days: float) -> float:
    """Σ_ij max(0, 1 - |a_i - b_j| / horizon_days): total kernel mass between
    two event-date sets (ordinals). The Bartlett kernel is the correlation of
    two overlapping sums of iid daily innovations."""
    gaps = np.abs(np.subtract.outer(a, b))
    return float(np.clip(1.0 - gaps / horizon_days, 0.0, None).sum())


def _ordinals(dates: Sequence[date]) -> np.ndarray:
    return np.array([d.toordinal() for d in dates], dtype=float)


def overlap_inflation(dates: Sequence[date], horizon_sessions: int) -> float:
    """Variance inflation factor for the mean of forward returns whose windows
    overlap: Var(mean) = iid variance × Σ_ij K / n. 1.0 = events fully
    independent; approaches n when all windows coincide. Sessions are converted
    to calendar days at 7/5 for the kernel width."""
    if len(dates) <= 1:
        return 1.0
    ords = _ordinals(dates)
    return _gram(ords, ords, horizon_sessions * _SESSIONS_TO_DAYS) / len(dates)


def cross_regime_correlation(
    dates_a: Sequence[date], dates_b: Sequence[date], horizon_sessions: int
) -> float:
    """Correlation between two studies' mean-return estimators induced by
    shared or nearby event windows: a normalized Gram entry, <= 1 by
    Cauchy-Schwarz (the Bartlett kernel is positive semidefinite)."""
    if not len(dates_a) or not len(dates_b):
        return 0.0
    horizon_days = horizon_sessions * _SESSIONS_TO_DAYS
    a, b = _ordinals(dates_a), _ordinals(dates_b)
    return _gram(a, b, horizon_days) / math.sqrt(
        _gram(a, a, horizon_days) * _gram(b, b, horizon_days)
    )


# -- fixed-effect meta-analysis ------------------------------------------------


@dataclass(frozen=True)
class CombinedEvidence:
    effect: float  # inverse-variance-weighted effect estimate
    se: float
    z: float  # effect / se, clipped to ±Z_CLIP
    agreement: float  # precision-weighted share of studies agreeing in sign
    z_raw: float  # effect / se before clipping (diagnostics)


def combine_evidence(
    effects: list[float],
    ses: list[float],
    correlation: Sequence[Sequence[float]] | None = None,
) -> CombinedEvidence | None:
    """Fixed-effect meta-analysis: weight = 1/se². `correlation` is the
    cross-study correlation matrix of the estimators (None = identity =
    independent studies); the combined variance is the full quadratic form
    w'Cw/(Σw)², so correlated studies do not fake precision. z is clipped to
    ±Z_CLIP as a reporting bound (z_raw keeps the unclipped value)."""
    if len(effects) != len(ses):
        raise ValueError("effects and ses must have equal length")
    kept = [i for i, s in enumerate(ses) if s > 0]
    if not kept:
        return None
    effect_values = [effects[i] for i in kept]
    se_values = [ses[i] for i in kept]
    weights = [1.0 / s**2 for s in se_values]
    total = sum(weights)
    effect = sum(w * e for w, e in zip(weights, effect_values, strict=True)) / total
    if correlation is None:
        variance = 1.0 / total
    else:
        variance = (
            sum(
                weights[i]
                * weights[j]
                * float(correlation[kept[i]][kept[j]])
                * se_values[i]
                * se_values[j]
                for i in range(len(kept))
                for j in range(len(kept))
            )
            / total**2
        )
    se = math.sqrt(variance)
    z_raw = effect / se
    z = max(-Z_CLIP, min(Z_CLIP, z_raw))
    sign = 1.0 if effect >= 0 else -1.0
    agreement = (
        sum(w for w, e in zip(weights, effect_values, strict=True) if math.copysign(1, e) == sign)
        / total
    )
    return CombinedEvidence(effect=effect, se=se, z=z, agreement=agreement, z_raw=z_raw)


def score_from_z(z: float) -> float:
    """0-100 via the normal CDF: 50 = no edge, 84 ≈ one sigma positive."""
    return 100.0 * _NORMAL.cdf(z)


def confidence_from_evidence(max_n_eff: float, agreement: float, prior_events: float) -> float:
    """Confidence 0-1 = evidence volume × cross-study consistency.
    The volume term n/(n+prior) is Bayesian shrinkage toward 'no evidence';
    `prior_events` says how many effective events it takes to earn 0.5.
    max (not sum) of per-study n_eff avoids double-counting overlapping
    studies of the same days."""
    volume = max_n_eff / (max_n_eff + prior_events)
    return max(0.0, min(1.0, volume * agreement))


# -- weighted sample (the base every research statistic is built on) -----------


@dataclass(frozen=True)
class WeightedSample:
    """Values with per-observation weights. Version-1 research callers pass
    uniform weights; future match weighting (sector/industry/factor/size
    similarity) supplies a weight vector instead, and every statistic below
    keeps working unchanged. Weighted moments and the Kish effective size are
    the platform's existing doctrine (see models.base.recency_weighted_stats)."""

    values: np.ndarray
    weights: np.ndarray

    def __post_init__(self) -> None:
        if self.values.shape != self.weights.shape:
            raise ValueError("values and weights must have the same shape")

    @classmethod
    def uniform(cls, values: Sequence[float] | np.ndarray) -> "WeightedSample":
        arr = np.asarray(values, dtype=float)
        return cls(values=arr, weights=np.ones_like(arr))

    def __len__(self) -> int:
        return int(self.values.size)

    @property
    def total_weight(self) -> float:
        return float(self.weights.sum())

    def kish_size(self) -> float:
        """Effective sample size under the weights: (Σw)² / Σw². Equals n for
        uniform weights; shrinks as weight concentrates."""
        denom = float((self.weights**2).sum())
        return float(self.total_weight**2 / denom) if denom > 0 else 0.0

    def mean(self) -> float | None:
        if len(self) == 0 or self.total_weight == 0:
            return None
        return float((self.weights * self.values).sum() / self.total_weight)

    def std(self) -> float | None:
        """Weighted standard deviation, bias-corrected by the Kish effective
        size (matches recency_weighted_stats: variance × n_eff/(n_eff-1))."""
        mean = self.mean()
        n_eff = self.kish_size()
        if mean is None or n_eff <= 1.0:
            return None
        var = float((self.weights * (self.values - mean) ** 2).sum() / self.total_weight)
        return math.sqrt(var * (n_eff / (n_eff - 1.0)))

    def probability(self, mask: np.ndarray) -> float | None:
        """Weighted fraction of observations satisfying a boolean mask."""
        if len(self) == 0 or self.total_weight == 0:
            return None
        return float((self.weights * mask).sum() / self.total_weight)

    def quantile(self, q: float) -> float | None:
        """Weight-aware quantile using Hazen plotting positions
        ``(cumsum(w) - w/2) / Σw``. Reduces to the ordinary sample median at
        q=0.5 for uniform weights; tail quantiles differ slightly from numpy's
        type-7 interpolation by design, to stay weight-consistent."""
        if len(self) == 0 or self.total_weight == 0:
            return None
        order = np.argsort(self.values)
        v = self.values[order]
        w = self.weights[order]
        positions = (np.cumsum(w) - 0.5 * w) / self.total_weight
        return float(np.interp(q, positions, v))


# -- effective sample (Kish weight deflation + Bartlett overlap deflation) ------


@dataclass(frozen=True)
class EffectiveSample:
    """One honest effective-N for a pooled sample: the weight (Kish) effective
    size deflated by the fraction of observations that are temporally
    independent (distinct calendar episodes / raw). ``effective`` is what every
    uncertainty calculation (standard errors, Wilson intervals, confidence) must
    use — never the raw match count.

    Episode-based (O(n log n)) rather than the Bartlett pairwise kernel (O(n²)):
    a pooled cross-sectional sample can hold hundreds of thousands of
    observations, for which the pairwise kernel is intractable. Same/near dates —
    including the same calendar day across different pooled symbols — collapse
    into one episode and so do not count as independent experiments
    (conservative: distinct symbols on one day are treated as one draw)."""

    raw: int
    kish: float
    independent_fraction: float  # distinct calendar episodes / raw
    effective: float

    def to_dict(self) -> dict:
        return {
            "raw": self.raw,
            "kish": self.kish,
            "independent_fraction": self.independent_fraction,
            "effective": self.effective,
        }


def effective_sample(sample: WeightedSample, n_episodes: int) -> EffectiveSample:
    """Effective-N = Kish effective size × (independent episodes / raw). For
    uniform weights this is exactly the distinct-episode count; weighting
    deflates it further. ``n_episodes`` is the number of distinct calendar
    episodes among the observation dates (computed by the outcome layer, which
    owns the date grouping)."""
    kish = sample.kish_size()
    raw = len(sample)
    fraction = (n_episodes / raw) if raw > 0 else 0.0
    return EffectiveSample(
        raw=raw, kish=kish, independent_fraction=fraction, effective=kish * fraction
    )
