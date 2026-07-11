"""Intelligence model framework: the common interface every model
implements, plus shared evidence statistics.

Architecture rule (Phase 9 shape, pulled forward): models consume ONLY the
feature store and the Historical Research Engine — never providers, never
raw tables. Scores are computed on demand; the reserved model-output
tables arrive when persistence is needed.

Scoring is evidence-derived, not weight-invented:
- Within a study, events are recency-weighted (exponential decay with a
  declared half-life) and summarized by weighted mean / Kish effective
  sample size / standard error / hit rate.
- Across studies, estimates are combined by inverse-variance weighting
  (fixed-effect meta-analysis) — weights ARE the statistical precision.
- The combined standardized effect z maps to a 0-100 score via the normal
  CDF: score = 100·Φ(z), i.e. the evidence-implied probability that the
  effect is positive. z is clipped to ±4 because overlapping regimes are
  correlated and unclipped z would overstate certainty.
"""

import abc
import math
from dataclasses import dataclass, field
from datetime import date
from statistics import NormalDist

import pandas as pd

_NORMAL = NormalDist()
Z_CLIP = 4.0


@dataclass(frozen=True)
class WeightedStats:
    """Recency-weighted summary of one study's forward returns."""

    n: int  # raw event count
    n_eff: float  # Kish effective sample size under the weights
    mean: float
    se: float  # standard error of the weighted mean
    hit_rate: float
    first_event: date
    last_event: date


def recency_weighted_stats(
    returns: pd.Series, as_of: date, half_life_years: float
) -> WeightedStats | None:
    """Weighted stats over a date-indexed return series; weight halves
    every `half_life_years` before `as_of`. Needs n >= 2 (no dispersion
    estimate otherwise)."""
    clean = returns.dropna().astype(float)
    if len(clean) < 2:
        return None
    ages_years = (pd.Timestamp(as_of) - clean.index).days / 365.25
    weights = pd.Series(0.5 ** (ages_years / half_life_years), index=clean.index)

    total = float(weights.sum())
    mean = float((weights * clean).sum() / total)
    n_eff = float(total**2 / (weights**2).sum())
    if n_eff <= 1.0:
        return None
    variance = float((weights * (clean - mean) ** 2).sum() / total) * (n_eff / (n_eff - 1.0))
    return WeightedStats(
        n=len(clean),
        n_eff=n_eff,
        mean=mean,
        se=math.sqrt(variance / n_eff),
        hit_rate=float((weights * (clean > 0)).sum() / total),
        first_event=clean.index.min().date(),
        last_event=clean.index.max().date(),
    )


@dataclass(frozen=True)
class CombinedEvidence:
    effect: float  # inverse-variance-weighted effect estimate
    se: float
    z: float  # effect / se, clipped to ±Z_CLIP
    agreement: float  # precision-weighted share of studies agreeing in sign


def combine_evidence(effects: list[float], ses: list[float]) -> CombinedEvidence | None:
    """Fixed-effect meta-analysis: weight = 1/se². Studies here overlap in
    time (correlated), so z is clipped and agreement is reported alongside."""
    pairs = [(e, s) for e, s in zip(effects, ses, strict=True) if s > 0]
    if not pairs:
        return None
    weights = [1.0 / s**2 for _, s in pairs]
    total = sum(weights)
    effect = sum(w * e for w, (e, _) in zip(weights, pairs, strict=True)) / total
    se = math.sqrt(1.0 / total)
    z = max(-Z_CLIP, min(Z_CLIP, effect / se))
    sign = 1.0 if effect >= 0 else -1.0
    agreement = (
        sum(w for w, (e, _) in zip(weights, pairs, strict=True) if math.copysign(1, e) == sign)
        / total
    )
    return CombinedEvidence(effect=effect, se=se, z=z, agreement=agreement)


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


@dataclass(frozen=True)
class RegimeEvidence:
    """One study backing a score: a historical regime and what the symbol
    did inside it."""

    label: str  # '10Y +50bps/21d'
    description: str  # prose for explanations
    feature: str
    n: int
    n_eff: float
    mean: float  # recency-weighted conditional forward return
    hit_rate: float
    baseline_mean: float  # unconditional forward return, same horizon
    excess: float  # mean - baseline_mean
    se: float
    first_event: date
    last_event: date

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "n": self.n,
            "n_eff": round(self.n_eff, 1),
            "mean": self.mean,
            "hit_rate": self.hit_rate,
            "baseline_mean": self.baseline_mean,
            "excess": self.excess,
            "first_event": self.first_event.isoformat(),
            "last_event": self.last_event.isoformat(),
        }


@dataclass(frozen=True)
class ModelScore:
    """One model's verdict for one symbol at one horizon."""

    model: str
    model_version: int
    symbol: str
    as_of: date
    horizon: str  # '1m'
    horizon_sessions: int  # 21
    score: float  # 0-100; 50 = no historical edge
    confidence: float  # 0-1
    expected_return: float | None
    historical_hit_rate: float | None
    sample_size: int  # distinct event dates across the studies used
    strongest_supporting_regimes: tuple[RegimeEvidence, ...]
    strongest_negative_regimes: tuple[RegimeEvidence, ...]
    explanation: str
    active_regimes: tuple[str, ...] = field(default=())

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "model_version": self.model_version,
            "symbol": self.symbol,
            "as_of": self.as_of.isoformat(),
            "horizon": self.horizon,
            "horizon_sessions": self.horizon_sessions,
            "score": round(self.score, 1),
            "confidence": round(self.confidence, 3),
            "expected_return": self.expected_return,
            "historical_hit_rate": self.historical_hit_rate,
            "sample_size": self.sample_size,
            "active_regimes": list(self.active_regimes),
            "strongest_supporting_regimes": [
                r.to_dict() for r in self.strongest_supporting_regimes
            ],
            "strongest_negative_regimes": [r.to_dict() for r in self.strongest_negative_regimes],
            "explanation": self.explanation,
        }


class IntelligenceModel(abc.ABC):
    """Common surface for every intelligence model. A model evaluates one
    symbol into per-horizon ModelScores using platform data only."""

    name: str
    version: int

    @abc.abstractmethod
    def evaluate(self, symbol: str, as_of: date | None = None) -> list[ModelScore]: ...
