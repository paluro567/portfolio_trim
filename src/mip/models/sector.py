"""Sector Rotation Intelligence Model.

Question answered: given how the symbol's sector has been behaving RECENTLY
— versus SPY, versus its own trend, and versus the stock itself — what has
historically happened to this symbol next?

1. Resolve the sector ETF through the frozen FK path (instrument →
   sector/industry → sectors.etf_instrument_id → symbol; D11). No industry→
   ETF mapping exists in the schema, so evidence is sector-level only.
2. Detect active regimes from the latest stored feature values. Regimes are
   grouped into FAMILIES; within a family, candidates are ordered
   most-specific-first and only the FIRST active one is kept, so nested
   conditions (e.g. "sector up while SPY down" ⊂ "sector outperforming")
   are never stacked as separate evidence.
3. For each active regime, ask the Research Engine how the symbol performed
   after every comparable historical episode (mode=events, window ending at
   as_of — no future events, PIT inherited from the feature store).
4. Per horizon, summarize each study with recency weighting, take the EXCESS
   over the unconditional baseline as the effect, adjust standard errors for
   overlapping forward windows, and combine studies with their cross-regime
   correlation (see models.base — hardened aggregation). Confidence uses
   overlap-adjusted effective samples, so flickering regimes with hundreds
   of near-duplicate episodes cannot buy certainty.
"""

from dataclasses import dataclass
from datetime import date

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from mip.core.exceptions import ConfigurationError
from mip.domain.enums import FeatureScope
from mip.domain.models import Instrument
from mip.models.base import (
    IntelligenceModel,
    ModelScore,
    RegimeEvidence,
    aggregate_horizon_evidence,
    collect_regime_evidence,
    select_active,
)
from mip.repositories.features import FeatureRepository
from mip.research import (
    ResearchEngine,
    ResearchFilter,
    ResearchQuery,
    ResearchWindow,
    SampleMode,
)

WINDOWS = (5, 21, 63, 126)
HORIZONS: dict[str, int] = {"1w": 5, "2w": 10, "1m": 21, "3m": 63, "6m": 126, "1y": 252}

# (strong, mild) relative-return thresholds per window, scaled ~sqrt(w/21)
# from the monthly anchors (5%, 2%) — regime grammar constants, versioned
# with the model (like the rate model's ±10/25/50 bps ladder).
REL_THRESHOLDS: dict[int, tuple[float, float]] = {
    5: (0.025, 0.010),
    21: (0.050, 0.020),
    63: (0.085, 0.035),
    126: (0.120, 0.050),
}
ACCEL_WINDOW = 21
ACCEL_THRESHOLDS = (0.050, 0.020)  # (strong, mild) change in 21d relative return


@dataclass(frozen=True)
class SectorRegime:
    """One candidate condition. `family` scopes the no-double-counting rule:
    at most one regime per family may be active at a time."""

    family: str  # 'sector_env_21d' | 'stock_vs_sector_63d' | 'sector_momentum'
    label: str  # 'XLK +5% vs SPY/21d'
    description: str  # prose for explanations
    feature: str  # primary feature, for RegimeEvidence
    filters: tuple[ResearchFilter, ...]


def _pct(value: float) -> str:
    return f"{value * 100:g}%"


def regime_candidates(etf: str, symbol: str) -> dict[str, list[SectorRegime]]:
    """All candidate regimes keyed by family, MOST SPECIFIC FIRST within
    each family (more conditions beat fewer; larger thresholds beat
    smaller). Detection keeps only the first active candidate per family."""
    families: dict[str, list[SectorRegime]] = {}

    for window in WINDOWS:
        strong, mild = REL_THRESHOLDS[window]
        rel = f"rel_ret_spy_{window}d"
        ret = f"ret_{window}d"

        families[f"sector_env_{window}d"] = [
            SectorRegime(
                family=f"sector_env_{window}d",
                label=f"{etf} up, SPY down/{window}d",
                description=f"{etf} rose while SPY fell over {window} sessions",
                feature=ret,
                filters=(
                    ResearchFilter(ret, ">", 0.0, symbol=etf),
                    ResearchFilter(ret, "<", 0.0, symbol="SPY"),
                ),
            ),
            SectorRegime(
                family=f"sector_env_{window}d",
                label=f"{etf} down, SPY up/{window}d",
                description=f"{etf} fell while SPY rose over {window} sessions",
                feature=ret,
                filters=(
                    ResearchFilter(ret, "<", 0.0, symbol=etf),
                    ResearchFilter(ret, ">", 0.0, symbol="SPY"),
                ),
            ),
            SectorRegime(
                family=f"sector_env_{window}d",
                label=f"{etf} +{_pct(mild)} vs SPY, high-vol/{window}d",
                description=(
                    f"{etf} beat SPY by more than {_pct(mild)} over {window} "
                    f"sessions during a high-volatility market"
                ),
                feature=rel,
                filters=(
                    ResearchFilter(rel, ">=", mild, symbol=etf),
                    ResearchFilter("regime_high_vol", "==", 1.0),
                ),
            ),
            SectorRegime(
                family=f"sector_env_{window}d",
                label=f"{etf} -{_pct(mild)} vs SPY, bull mkt/{window}d",
                description=(
                    f"{etf} trailed SPY by more than {_pct(mild)} over {window} "
                    f"sessions while the market was in a bull regime"
                ),
                feature=rel,
                filters=(
                    ResearchFilter(rel, "<=", -mild, symbol=etf),
                    ResearchFilter("regime_bull", "==", 1.0),
                ),
            ),
            SectorRegime(
                family=f"sector_env_{window}d",
                label=f"{etf} +{_pct(strong)} vs SPY/{window}d",
                description=f"{etf} beat SPY by more than {_pct(strong)} over {window} sessions",
                feature=rel,
                filters=(ResearchFilter(rel, ">=", strong, symbol=etf),),
            ),
            SectorRegime(
                family=f"sector_env_{window}d",
                label=f"{etf} +{_pct(mild)} vs SPY/{window}d",
                description=f"{etf} beat SPY by more than {_pct(mild)} over {window} sessions",
                feature=rel,
                filters=(ResearchFilter(rel, ">=", mild, symbol=etf),),
            ),
            SectorRegime(
                family=f"sector_env_{window}d",
                label=f"{etf} -{_pct(strong)} vs SPY/{window}d",
                description=(
                    f"{etf} trailed SPY by more than {_pct(strong)} over {window} sessions"
                ),
                feature=rel,
                filters=(ResearchFilter(rel, "<=", -strong, symbol=etf),),
            ),
            SectorRegime(
                family=f"sector_env_{window}d",
                label=f"{etf} -{_pct(mild)} vs SPY/{window}d",
                description=f"{etf} trailed SPY by more than {_pct(mild)} over {window} sessions",
                feature=rel,
                filters=(ResearchFilter(rel, "<=", -mild, symbol=etf),),
            ),
        ]

        rel_sector = f"rel_ret_sector_{window}d"
        families[f"stock_vs_sector_{window}d"] = [
            SectorRegime(
                family=f"stock_vs_sector_{window}d",
                label=f"{symbol} +{_pct(strong)} vs {etf}/{window}d",
                description=(
                    f"{symbol} beat its sector ETF {etf} by more than "
                    f"{_pct(strong)} over {window} sessions"
                ),
                feature=rel_sector,
                filters=(ResearchFilter(rel_sector, ">=", strong),),
            ),
            SectorRegime(
                family=f"stock_vs_sector_{window}d",
                label=f"{symbol} +{_pct(mild)} vs {etf}/{window}d",
                description=(
                    f"{symbol} beat its sector ETF {etf} by more than "
                    f"{_pct(mild)} over {window} sessions"
                ),
                feature=rel_sector,
                filters=(ResearchFilter(rel_sector, ">=", mild),),
            ),
            SectorRegime(
                family=f"stock_vs_sector_{window}d",
                label=f"{symbol} -{_pct(strong)} vs {etf}/{window}d",
                description=(
                    f"{symbol} trailed its sector ETF {etf} by more than "
                    f"{_pct(strong)} over {window} sessions"
                ),
                feature=rel_sector,
                filters=(ResearchFilter(rel_sector, "<=", -strong),),
            ),
            SectorRegime(
                family=f"stock_vs_sector_{window}d",
                label=f"{symbol} -{_pct(mild)} vs {etf}/{window}d",
                description=(
                    f"{symbol} trailed its sector ETF {etf} by more than "
                    f"{_pct(mild)} over {window} sessions"
                ),
                feature=rel_sector,
                filters=(ResearchFilter(rel_sector, "<=", -mild),),
            ),
        ]

    accel = f"rel_ret_spy_accel_{ACCEL_WINDOW}d"
    a_strong, a_mild = ACCEL_THRESHOLDS
    families["sector_momentum"] = [
        SectorRegime(
            family="sector_momentum",
            label=f"{etf} accel +{_pct(a_strong)}/{ACCEL_WINDOW}d",
            description=(
                f"{etf}'s {ACCEL_WINDOW}-session lead over SPY expanded by more "
                f"than {_pct(a_strong)} vs {ACCEL_WINDOW} sessions earlier"
            ),
            feature=accel,
            filters=(ResearchFilter(accel, ">=", a_strong, symbol=etf),),
        ),
        SectorRegime(
            family="sector_momentum",
            label=f"{etf} accel +{_pct(a_mild)}/{ACCEL_WINDOW}d",
            description=(
                f"{etf}'s {ACCEL_WINDOW}-session lead over SPY expanded by more "
                f"than {_pct(a_mild)} vs {ACCEL_WINDOW} sessions earlier"
            ),
            feature=accel,
            filters=(ResearchFilter(accel, ">=", a_mild, symbol=etf),),
        ),
        SectorRegime(
            family="sector_momentum",
            label=f"{etf} accel -{_pct(a_strong)}/{ACCEL_WINDOW}d",
            description=(
                f"{etf}'s {ACCEL_WINDOW}-session lead over SPY shrank by more "
                f"than {_pct(a_strong)} vs {ACCEL_WINDOW} sessions earlier"
            ),
            feature=accel,
            filters=(ResearchFilter(accel, "<=", -a_strong, symbol=etf),),
        ),
        SectorRegime(
            family="sector_momentum",
            label=f"{etf} accel -{_pct(a_mild)}/{ACCEL_WINDOW}d",
            description=(
                f"{etf}'s {ACCEL_WINDOW}-session lead over SPY shrank by more "
                f"than {_pct(a_mild)} vs {ACCEL_WINDOW} sessions earlier"
            ),
            feature=accel,
            filters=(ResearchFilter(accel, "<=", -a_mild, symbol=etf),),
        ),
    ]
    return families


class SectorRotationModel(IntelligenceModel):
    name = "sector_rotation"
    version = 2  # v2: overlap-adjusted evidence aggregation + diagnostics

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
        etf = self._sector_etf(symbol)
        if etf is None or etf == symbol:
            resolved = as_of or self._latest_feature_date(symbol) or date.today()
            explanation = (
                f"{symbol} has no sector→ETF mapping in the reference data "
                "(sectors.etf_instrument_id), so sector-rotation evidence "
                "cannot be evaluated. Neutral by construction."
            )
            return [
                self._neutral_score(symbol, resolved, label, sessions, (), explanation)
                for label, sessions in HORIZONS.items()
            ]

        active, resolved_as_of = self._detect(symbol, etf, as_of)
        if resolved_as_of is None:  # features exist but none at/before as_of
            assert as_of is not None
            explanation = (
                f"No sector-rotation features are stored at or before {as_of.isoformat()} "
                f"for {symbol}/{etf} — insufficient data to detect a sector regime. "
                "Neutral by construction."
            )
            return [
                self._neutral_score(symbol, as_of, label, sessions, (), explanation)
                for label, sessions in HORIZONS.items()
            ]
        if not active:
            explanation = (
                f"No sector-rotation regime is currently active: {etf}'s relative "
                f"returns vs SPY, {symbol}'s relative returns vs {etf}, and sector "
                "momentum are all inside their thresholds on every window "
                "(5/21/63/126 sessions). History offers no sector-driven edge "
                "either way."
            )
            return [
                self._neutral_score(symbol, resolved_as_of, label, sessions, (), explanation)
                for label, sessions in HORIZONS.items()
            ]

        studies = {
            regime: self._engine.run(
                ResearchQuery(
                    symbol=symbol,
                    filters=regime.filters,
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

    # -- sector ETF resolution (FK path only, D11) ---------------------------

    def _sector_etf(self, symbol: str) -> str | None:
        from mip.repositories.instruments import InstrumentRepository

        repo = InstrumentRepository(self._session)
        instrument = repo.get_by_symbol(symbol)
        if instrument is None:
            raise ConfigurationError(f"unknown symbol {symbol!r}")
        return repo.sector_etf_symbol(instrument)

    # -- regime detection ----------------------------------------------------

    def _detect(
        self, symbol: str, etf: str, as_of: date | None
    ) -> tuple[list[SectorRegime], date | None]:
        """Active regimes from the latest stored feature values at/before
        as_of; resolved as_of = the newest feature date actually read, or
        None when features exist but hold no value at/before as_of."""
        cache: dict[tuple[str, str | None], float | None] = {}
        newest: list[date] = []  # mutable cell for the closure

        def latest(feature: str, sym: str | None) -> float | None:
            key = (feature, sym)
            if key in cache:
                return cache[key]
            definition = self._features.get_definition(feature)
            if definition is None:
                raise ConfigurationError(
                    f"feature {feature!r} is not registered; run: mip features build --all"
                )
            if definition.scope is FeatureScope.MARKET:
                series = self._features.get_market_series(definition.id)
            else:
                series = self._features.get_instrument_series(
                    definition.id, self._instrument_id(sym or symbol)
                )
            if as_of is not None and not series.empty:
                series = series[series.index <= pd.Timestamp(as_of)]
            if series.empty:
                cache[key] = None
            else:
                cache[key] = float(series.iloc[-1])
                last = series.index[-1].date()
                if not newest or last > newest[0]:
                    newest[:] = [last]
            return cache[key]

        active = select_active(regime_candidates(etf, symbol), latest)
        if not newest:
            if as_of is None:  # nothing stored at all: a setup problem, not a data gap
                raise ConfigurationError(
                    f"no sector-rotation features stored for {symbol!r}/{etf!r}; "
                    "run: mip features build --all"
                )
            return [], None
        return active, (as_of or newest[0])

    def _instrument_id(self, symbol: str) -> int:
        instrument_id = self._session.scalar(
            select(Instrument.id).where(Instrument.symbol == symbol)
        )
        if instrument_id is None:
            raise ConfigurationError(f"unknown symbol {symbol!r}")
        return instrument_id

    def _latest_feature_date(self, symbol: str) -> date | None:
        definition = self._features.get_definition("ret_21d")
        if definition is None:
            return None
        series = self._features.get_instrument_series(definition.id, self._instrument_id(symbol))
        return series.index[-1].date() if not series.empty else None

    # -- scoring ------------------------------------------------------------

    def _score_horizon(
        self,
        symbol: str,
        as_of: date,
        horizon_label: str,
        sessions: int,
        studies: dict,
        active_labels: tuple[str, ...],
    ) -> ModelScore:
        evidence, study_dates, event_dates = collect_regime_evidence(
            studies, sessions, as_of, self.half_life_years, self.min_events
        )
        if not evidence:
            explanation = (
                f"Sector regimes are active ({', '.join(active_labels)}) but {symbol} "
                f"has fewer than {self.min_events} resolved historical episodes per "
                "regime at this horizon — no score can be supported by evidence."
            )
            return self._neutral_score(
                symbol, as_of, horizon_label, sessions, active_labels, explanation
            )

        aggregate = aggregate_horizon_evidence(
            evidence, study_dates, sessions, len(active_labels), self.prior_events
        )
        explanation = self._explanation(symbol, horizon_label, evidence, aggregate.effect)
        if aggregate.diagnostics.saturated:
            explanation += (
                f" Score saturated: the combined z-score is "
                f"{aggregate.diagnostics.z_raw:+.1f}, beyond the ±4 reporting bound."
            )

        return ModelScore(
            model=self.name,
            model_version=self.version,
            symbol=symbol,
            as_of=as_of,
            horizon=horizon_label,
            horizon_sessions=sessions,
            score=aggregate.score,
            confidence=aggregate.confidence,
            expected_return=aggregate.expected_return,
            historical_hit_rate=aggregate.hit_rate,
            sample_size=len(event_dates),
            strongest_supporting_regimes=aggregate.supporting,
            strongest_negative_regimes=aggregate.negative,
            explanation=explanation,
            active_regimes=active_labels,
            diagnostics=aggregate.diagnostics,
            baseline_return=aggregate.expected_return - aggregate.effect,
            excess_return=aggregate.effect,
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
            f"{len(evidence)} active sector regimes, the evidence-weighted edge is "
            f"{effect * 100:+.1f}pp per {horizon_label}."
        )

    def _neutral_score(
        self,
        symbol: str,
        as_of: date,
        horizon_label: str,
        sessions: int,
        active: tuple[str, ...],
        explanation: str,
    ) -> ModelScore:
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
