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
  effect is positive. z is clipped to ±4 as a reporting bound.

Overlap correction (hardening pass): forward-return windows overlap, so
neither events within a study nor studies of the same days are independent.
Under the approximation that daily innovations are serially uncorrelated,
two h-session forward returns starting g days apart correlate by the
Bartlett kernel max(0, 1 - g/h). That one kernel yields, with no free
parameters:
- a WITHIN-study variance inflation factor (overlap_inflation): the mean of
  n overlapping windows carries only ~n/inflation independent observations,
  so se scales by sqrt(inflation) and n_eff shrinks by 1/inflation;
- a CROSS-study correlation matrix (cross_regime_correlation, a normalized
  Gram matrix — PSD, entries <= 1) used in the combined variance
  w'Cw/(Σw)², so overlapping regimes cannot masquerade as independent
  confirmations. Identity correlation reproduces the uncorrected math.
"""

import abc
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from statistics import NormalDist

import numpy as np
import pandas as pd

from mip.research.query import OPERATORS

_NORMAL = NormalDist()
Z_CLIP = 4.0
_SESSIONS_TO_DAYS = 7.0 / 5.0  # trading sessions -> calendar days for the kernel


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


# -- overlap geometry (Bartlett kernel over event dates) -----------------------


def _gram(a: np.ndarray, b: np.ndarray, horizon_days: float) -> float:
    """Σ_ij max(0, 1 - |a_i - b_j| / horizon_days): total kernel mass
    between two event-date sets (ordinals). The Bartlett kernel is the
    correlation of two overlapping sums of iid daily innovations."""
    gaps = np.abs(np.subtract.outer(a, b))
    return float(np.clip(1.0 - gaps / horizon_days, 0.0, None).sum())


def _ordinals(dates: Sequence[date]) -> np.ndarray:
    return np.array([d.toordinal() for d in dates], dtype=float)


def overlap_inflation(dates: Sequence[date], horizon_sessions: int) -> float:
    """Variance inflation factor for the mean of forward returns whose
    windows overlap: Var(mean) = iid variance × Σ_ij K / n. 1.0 = events
    fully independent; approaches n when all windows coincide. Sessions are
    converted to calendar days at 7/5 for the kernel width."""
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
    w'Cw/(Σw)², so correlated studies do not fake precision. z is clipped
    to ±Z_CLIP as a reporting bound (z_raw keeps the unclipped value)."""
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


def select_active(families: dict, latest: Callable[[str, str | None], float | None]) -> list:
    """First active candidate per family, most specific first — the shared
    no-double-counting rule: nested/overlapping conditions in one family are
    never stacked as separate evidence. Duck-typed: candidates expose
    `.filters` (ResearchFilter). `latest(feature, symbol|None)` supplies
    current values; a candidate with any unavailable value is not active."""
    active = []
    for candidates in families.values():
        for regime in candidates:
            satisfied = True
            for research_filter in regime.filters:
                value = latest(research_filter.feature, research_filter.symbol)
                if value is None or not OPERATORS[research_filter.op](value, research_filter.value):
                    satisfied = False
                    break
            if satisfied:
                active.append(regime)
                break
    return active


def collect_regime_evidence(
    studies: dict,
    sessions: int,
    as_of: date,
    half_life_years: float,
    min_events: int,
) -> tuple[list[RegimeEvidence], list[list[date]], set[date]]:
    """One horizon's evidence from research studies (regime -> ResearchResult,
    duck-typed: regimes expose label/description/feature). Applies the
    min-sample filter and the WITHIN-study overlap adjustment: se scales by
    sqrt(inflation), n_eff becomes independent-equivalent events. Returns
    (evidence, per-study event dates, union of event dates)."""
    column = f"fwd_{sessions}d"
    evidence: list[RegimeEvidence] = []
    study_dates: list[list[date]] = []
    event_dates: set[date] = set()
    for regime, result in studies.items():
        stats = recency_weighted_stats(result.forward_returns[column], as_of, half_life_years)
        if stats is None or stats.n < min_events:
            continue
        baseline = result.baseline[sessions].mean
        if baseline is None:
            continue
        dates = [ts.date() for ts in result.forward_returns[column].dropna().index]
        inflation = overlap_inflation(dates, sessions)
        evidence.append(
            RegimeEvidence(
                label=regime.label,
                description=regime.description,
                feature=regime.feature,
                n=stats.n,
                n_eff=stats.n_eff / inflation,  # independent-equivalent events
                mean=stats.mean,
                hit_rate=stats.hit_rate,
                baseline_mean=baseline,
                excess=stats.mean - baseline,
                se=stats.se * math.sqrt(inflation),  # overlapping windows
                first_event=stats.first_event,
                last_event=stats.last_event,
            )
        )
        study_dates.append(dates)
        event_dates.update(dates)
    return evidence, study_dates, event_dates


@dataclass(frozen=True)
class ScoreDiagnostics:
    """How a score was earned — volume, overlap, agreement, saturation."""

    active_regimes: int  # regimes detected as currently active
    evidence_studies: int  # studies that survived the min-sample filter
    max_n_eff: float  # largest overlap-adjusted effective sample size
    mean_cross_correlation: float  # avg pairwise event-overlap correlation
    agreement: float  # precision-weighted share agreeing in sign
    z_raw: float  # combined z before clipping
    z_clipped: float  # combined z after clipping (drives the score)
    saturated: bool  # |z_raw| exceeded the ±Z_CLIP reporting bound

    def to_dict(self) -> dict:
        return {
            "active_regimes": self.active_regimes,
            "evidence_studies": self.evidence_studies,
            "max_n_eff": round(self.max_n_eff, 1),
            "mean_cross_correlation": round(self.mean_cross_correlation, 3),
            "agreement": round(self.agreement, 3),
            "z_raw": round(self.z_raw, 2),
            "z_clipped": round(self.z_clipped, 2),
            "saturated": self.saturated,
        }


@dataclass(frozen=True)
class HorizonAggregate:
    """Output of the shared evidence aggregation for one horizon."""

    score: float
    confidence: float
    expected_return: float
    hit_rate: float
    effect: float  # combined excess-return effect
    supporting: tuple["RegimeEvidence", ...]
    negative: tuple["RegimeEvidence", ...]
    diagnostics: ScoreDiagnostics


def aggregate_horizon_evidence(
    evidence: Sequence["RegimeEvidence"],
    study_event_dates: Sequence[Sequence[date]],
    horizon_sessions: int,
    active_regimes: int,
    prior_events: float,
) -> HorizonAggregate:
    """Hardened combination shared by every model. The caller supplies
    evidence whose se/n_eff are ALREADY overlap-adjusted (overlap_inflation)
    plus each study's resolved event dates; this adds the cross-study
    correlation so the same market condition seen through several regimes
    is never counted as independent confirmation."""
    if not evidence or len(evidence) != len(study_event_dates):
        raise ValueError("evidence and study_event_dates must align and be non-empty")

    k = len(evidence)
    correlation = [[1.0] * k for _ in range(k)]
    off_diagonal: list[float] = []
    for i in range(k):
        for j in range(i + 1, k):
            rho = cross_regime_correlation(
                study_event_dates[i], study_event_dates[j], horizon_sessions
            )
            correlation[i][j] = correlation[j][i] = rho
            off_diagonal.append(rho)

    combined = combine_evidence([e.excess for e in evidence], [e.se for e in evidence], correlation)
    assert combined is not None  # evidence is non-empty with se > 0

    weights = [1.0 / e.se**2 for e in evidence]
    total_weight = sum(weights)
    expected = sum(w * e.mean for w, e in zip(weights, evidence, strict=True)) / total_weight
    hit_rate = sum(w * e.hit_rate for w, e in zip(weights, evidence, strict=True)) / total_weight
    confidence = confidence_from_evidence(
        max(e.n_eff for e in evidence), combined.agreement, prior_events
    )
    supporting = tuple(
        sorted([e for e in evidence if e.excess > 0], key=lambda e: -e.excess / e.se)[:3]
    )
    negative = tuple(
        sorted([e for e in evidence if e.excess < 0], key=lambda e: e.excess / e.se)[:3]
    )
    diagnostics = ScoreDiagnostics(
        active_regimes=active_regimes,
        evidence_studies=k,
        max_n_eff=max(e.n_eff for e in evidence),
        mean_cross_correlation=(sum(off_diagonal) / len(off_diagonal) if off_diagonal else 0.0),
        agreement=combined.agreement,
        z_raw=combined.z_raw,
        z_clipped=combined.z,
        saturated=abs(combined.z_raw) > Z_CLIP,
    )
    return HorizonAggregate(
        score=score_from_z(combined.z),
        confidence=confidence,
        expected_return=expected,
        hit_rate=hit_rate,
        effect=combined.effect,
        supporting=supporting,
        negative=negative,
        diagnostics=diagnostics,
    )


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
    diagnostics: ScoreDiagnostics | None = None  # None on neutral paths
    baseline_return: float | None = None  # precision-weighted unconditional mean
    excess_return: float | None = None  # expected_return - baseline_return
    context: dict | None = None  # structured model context (e.g. analogue detail)

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
            "diagnostics": self.diagnostics.to_dict() if self.diagnostics else None,
            "baseline_return": self.baseline_return,
            "excess_return": self.excess_return,
        }


class IntelligenceModel(abc.ABC):
    """Common surface for every intelligence model. A model evaluates one
    symbol into per-horizon ModelScores using platform data only."""

    name: str
    version: int

    @abc.abstractmethod
    def evaluate(self, symbol: str, as_of: date | None = None) -> list[ModelScore]: ...
