"""Interest Rate Sensitivity Model.

Question answered: given how Treasury yields have moved RECENTLY, what has
historically happened to this symbol next?

1. Detect active regimes: for each series (2Y, 10Y) and rolling window
   (5/21/63/126 sessions), read the latest stored yield change and keep
   the MOST SPECIFIC satisfied threshold (±10/25/50 bps) — nested
   thresholds are not stacked as separate evidence.
2. For each active regime, ask the Research Engine how the symbol
   performed after every comparable historical episode (mode=events,
   window ending at as_of — no future events, PIT inherited from the
   feature store).
3. Per horizon, summarize each study with recency weighting, take the
   EXCESS over the unconditional baseline as the effect, combine studies
   by inverse variance, and map to score/confidence (see models.base).
"""

from dataclasses import dataclass
from datetime import date

import pandas as pd
from sqlalchemy.orm import Session

from mip.core.exceptions import ConfigurationError
from mip.models.base import (
    IntelligenceModel,
    ModelScore,
    RegimeEvidence,
    combine_evidence,
    confidence_from_evidence,
    recency_weighted_stats,
    score_from_z,
)
from mip.repositories.features import FeatureRepository
from mip.research import (
    ResearchEngine,
    ResearchFilter,
    ResearchQuery,
    ResearchWindow,
    SampleMode,
)

SERIES = {"2Y": "dgs2_chg_{window}d", "10Y": "dgs10_chg_{window}d"}
WINDOWS = (5, 21, 63, 126)
THRESHOLDS_BPS = (50, 25, 10)  # most specific first
HORIZONS: dict[str, int] = {"1w": 5, "2w": 10, "1m": 21, "3m": 63, "6m": 126, "1y": 252}


@dataclass(frozen=True)
class RateRegime:
    series: str  # '2Y' | '10Y'
    window: int  # sessions
    threshold_bps: int  # signed: +50 rising, -25 falling
    feature: str  # 'dgs10_chg_21d'

    @property
    def label(self) -> str:
        return f"{self.series} {self.threshold_bps:+d}bps/{self.window}d"

    @property
    def description(self) -> str:
        verb = "rose" if self.threshold_bps > 0 else "fell"
        return (
            f"the {self.series} Treasury yield {verb} more than "
            f"{abs(self.threshold_bps)} bps over {self.window} sessions"
        )

    @property
    def research_filter(self) -> ResearchFilter:
        pp = self.threshold_bps / 100.0  # store keeps percentage points
        if self.threshold_bps > 0:
            return ResearchFilter(self.feature, ">=", pp)
        return ResearchFilter(self.feature, "<=", pp)


def all_regimes() -> list[RateRegime]:
    regimes = []
    for series, template in SERIES.items():
        for window in WINDOWS:
            feature = template.format(window=window)
            for bps in THRESHOLDS_BPS:
                regimes.append(RateRegime(series, window, +bps, feature))
                regimes.append(RateRegime(series, window, -bps, feature))
    return regimes


class InterestRateModel(IntelligenceModel):
    name = "interest_rate_sensitivity"
    version = 1

    def __init__(
        self,
        session: Session,
        half_life_years: float = 10.0,  # recency: pre-2016 evidence counts less
        min_events: int = 5,  # studies thinner than this are ignored
        prior_events: float = 30.0,  # effective events needed for confidence 0.5
    ) -> None:
        self._session = session
        self._features = FeatureRepository(session)
        self._engine = ResearchEngine(session)
        self.half_life_years = half_life_years
        self.min_events = min_events
        self.prior_events = prior_events

    # -- public ------------------------------------------------------------

    def evaluate(self, symbol: str, as_of: date | None = None) -> list[ModelScore]:
        series_values, resolved_as_of = self._latest_changes(as_of)
        active = self._active_regimes(series_values)

        if not active:
            return [
                self._neutral_score(symbol, resolved_as_of, label, sessions, active=())
                for label, sessions in HORIZONS.items()
            ]

        studies = {
            regime: self._engine.run(
                ResearchQuery(
                    symbol=symbol,
                    filters=(regime.research_filter,),
                    window=ResearchWindow(end=resolved_as_of),
                    horizons=tuple(HORIZONS.values()),
                    mode=SampleMode.EVENTS,
                )
            )
            for regime in active
        }
        active_labels = tuple(r.label for r in active)
        return [
            self._score_horizon(symbol, resolved_as_of, label, sessions, studies, active_labels)
            for label, sessions in HORIZONS.items()
        ]

    # -- regime detection ----------------------------------------------------

    def _latest_changes(self, as_of: date | None) -> tuple[dict[RateRegime, float], date]:
        """Latest stored value per (series, window) feature at/before as_of;
        resolved as_of = the newest feature date actually used."""
        values: dict[tuple[str, int], float] = {}
        newest: date | None = None
        for series, template in SERIES.items():
            for window in WINDOWS:
                feature_name = template.format(window=window)
                definition = self._features.get_definition(feature_name)
                if definition is None:
                    raise ConfigurationError(
                        f"feature {feature_name!r} is not registered; "
                        "run: mip features build --all"
                    )
                stored = self._features.get_market_series(definition.id)
                if as_of is not None:
                    stored = stored[stored.index <= pd.Timestamp(as_of)]
                if stored.empty:
                    continue
                values[(series, window)] = float(stored.iloc[-1])
                last = stored.index[-1].date()
                newest = last if newest is None or last > newest else newest
        if newest is None:
            raise ConfigurationError(
                "no rate-change features stored; run: mip features build --all"
            )
        return values, (as_of or newest)

    def _active_regimes(self, values: dict[tuple[str, int], float]) -> list[RateRegime]:
        active = []
        for series, template in SERIES.items():
            for window in WINDOWS:
                change = values.get((series, window))
                if change is None:
                    continue
                feature = template.format(window=window)
                for bps in THRESHOLDS_BPS:  # most specific first, keep one
                    if change >= bps / 100.0:
                        active.append(RateRegime(series, window, +bps, feature))
                        break
                    if change <= -bps / 100.0:
                        active.append(RateRegime(series, window, -bps, feature))
                        break
        return active

    # -- scoring ------------------------------------------------------------------

    def _score_horizon(
        self,
        symbol: str,
        as_of: date,
        horizon_label: str,
        sessions: int,
        studies: dict,
        active_labels: tuple[str, ...],
    ) -> ModelScore:
        column = f"fwd_{sessions}d"
        evidence: list[RegimeEvidence] = []
        event_dates: set[date] = set()

        for regime, result in studies.items():
            stats = recency_weighted_stats(
                result.forward_returns[column], as_of, self.half_life_years
            )
            if stats is None or stats.n < self.min_events:
                continue
            baseline = result.baseline[sessions].mean
            if baseline is None:
                continue
            evidence.append(
                RegimeEvidence(
                    label=regime.label,
                    description=regime.description,
                    feature=regime.feature,
                    n=stats.n,
                    n_eff=stats.n_eff,
                    mean=stats.mean,
                    hit_rate=stats.hit_rate,
                    baseline_mean=baseline,
                    excess=stats.mean - baseline,
                    se=stats.se,
                    first_event=stats.first_event,
                    last_event=stats.last_event,
                )
            )
            resolved = result.forward_returns[column].dropna()
            event_dates.update(ts.date() for ts in resolved.index)

        if not evidence:
            return self._neutral_score(
                symbol, as_of, horizon_label, sessions, active_labels, thin_history=True
            )

        combined = combine_evidence([e.excess for e in evidence], [e.se for e in evidence])
        assert combined is not None  # evidence is non-empty with se > 0
        weights = [1.0 / e.se**2 for e in evidence]
        total_weight = sum(weights)
        expected = sum(w * e.mean for w, e in zip(weights, evidence, strict=True)) / total_weight
        hit_rate = (
            sum(w * e.hit_rate for w, e in zip(weights, evidence, strict=True)) / total_weight
        )
        confidence = confidence_from_evidence(
            max(e.n_eff for e in evidence), combined.agreement, self.prior_events
        )

        supporting = tuple(
            sorted([e for e in evidence if e.excess > 0], key=lambda e: -e.excess / e.se)[:3]
        )
        negative = tuple(
            sorted([e for e in evidence if e.excess < 0], key=lambda e: e.excess / e.se)[:3]
        )

        return ModelScore(
            model=self.name,
            model_version=self.version,
            symbol=symbol,
            as_of=as_of,
            horizon=horizon_label,
            horizon_sessions=sessions,
            score=score_from_z(combined.z),
            confidence=confidence,
            expected_return=expected,
            historical_hit_rate=hit_rate,
            sample_size=len(event_dates),
            strongest_supporting_regimes=supporting,
            strongest_negative_regimes=negative,
            explanation=self._explanation(symbol, horizon_label, evidence, combined.effect),
            active_regimes=active_labels,
        )

    def _explanation(
        self, symbol: str, horizon_label: str, evidence: list[RegimeEvidence], effect: float
    ) -> str:
        lead = max(evidence, key=lambda e: abs(e.excess / e.se))
        direction = "outperformed" if lead.excess > 0 else "underperformed"
        negative_rate = 1.0 - lead.hit_rate
        return (
            f"During the {lead.n} past environments where {lead.description}, "
            f"{symbol} averaged {lead.mean * 100:+.1f}% over the following {horizon_label} "
            f"(recency-weighted) vs an unconditional {lead.baseline_mean * 100:+.1f}% — it "
            f"{direction} its baseline by {lead.excess * 100:+.1f}pp with a "
            f"{negative_rate * 100:.0f}% negative hit rate. Combined across "
            f"{len(evidence)} active rate regimes, the evidence-weighted edge is "
            f"{effect * 100:+.1f}pp per {horizon_label}."
        )

    def _neutral_score(
        self,
        symbol: str,
        as_of: date,
        horizon_label: str,
        sessions: int,
        active: tuple[str, ...],
        thin_history: bool = False,
    ) -> ModelScore:
        if thin_history:
            explanation = (
                f"Rate regimes are active ({', '.join(active)}) but {symbol} has fewer "
                f"than {self.min_events} resolved historical episodes per regime at this "
                "horizon — no score can be supported by evidence."
            )
        else:
            explanation = (
                "No interest-rate regime is currently active: the latest 2Y and 10Y "
                "changes are inside ±10 bps on every window (5/21/63/126 sessions). "
                "History offers no rate-driven edge either way."
            )
        return ModelScore(
            model=self.name,
            model_version=self.version,
            symbol=symbol,
            as_of=as_of,
            horizon=horizon_label,
            horizon_sessions=sessions,
            score=50.0,
            confidence=0.0,
            expected_return=None,
            historical_hit_rate=None,
            sample_size=0,
            strongest_supporting_regimes=(),
            strongest_negative_regimes=(),
            explanation=explanation,
            active_regimes=active,
        )
