"""Momentum Exhaustion Intelligence Model.

Question answered: given how the stock's OWN momentum, trend, volatility,
and extension look today, has similar behavior in its own history usually
led to continuation or to underperformance over each forward horizon?

Thresholds are the stock's own empirical percentiles (deciles), computed
from its stored feature history at/before as_of — normalized conditions,
not technical-analysis constants. Each historical study filters on the
same concrete threshold, so activation and evidence answer one question:
"days at least as extreme as today." A condition whose feature has fewer
than MIN_PERCENTILE_OBS stored observations is unavailable and its
candidates cannot activate (absent, never zero). Structural conditions use
natural zero boundaries (above/below a moving average; sector-relative
lead/lag), which need no fitted constants.

Continuation vs exhaustion is decided by evidence, not opinion: the grammar
pairs the same momentum state with opposite qualifiers (expanding vs
subdued volatility, sector-confirmed vs sector-fading, spread widening vs
narrowing, near-high strength vs failed breakout) and history determines
which way each cuts for the specific stock. Positive-excess studies
surface as continuation evidence (strongest_supporting_regimes),
negative-excess as exhaustion evidence (strongest_negative_regimes).

Overlap handling is the shared hardened framework (models.base): one active
regime per family (most specific first), Bartlett-kernel within-study SE
inflation, correlated cross-regime combination, agreement-based confidence,
and saturation diagnostics on every score. Limitation (documented):
percentile thresholds are formed at as_of from the stock's full history to
date, so early-history events are classified by today's distribution — the
query is point-in-time legal, but not locally re-normalized per event date.
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
from mip.repositories.instruments import InstrumentRepository
from mip.research import (
    ResearchEngine,
    ResearchFilter,
    ResearchQuery,
    ResearchWindow,
    SampleMode,
)

HORIZONS: dict[str, int] = {"1w": 5, "2w": 10, "1m": 21, "3m": 63, "6m": 126, "1y": 252}
MIN_PERCENTILE_OBS = 252  # a year of history before a percentile is meaningful

# Quantile levels used by the grammar (deciles only — no fitted constants).
FAMILIES = (
    "abs_momentum",
    "extension",
    "momentum_accel",
    "vol_interaction",
    "rel_confirmation",  # skipped cleanly when no sector-ETF mapping exists
    "trend_structure",
)


@dataclass(frozen=True)
class MomentumRegime:
    """One candidate condition. `family` scopes the no-double-counting rule:
    at most one regime per family may be active at a time."""

    family: str
    label: str  # stable, short: '63d ret ≥ p90'
    description: str  # prose with the actual threshold values
    feature: str  # primary feature, for RegimeEvidence
    filters: tuple[ResearchFilter, ...]


def regime_candidates(
    symbol: str,
    etf: str | None,
    quantile,  # Callable[[str, float], float | None]: the stock's own percentile value
) -> dict[str, list[MomentumRegime]]:
    """All candidate regimes keyed by family, MOST SPECIFIC FIRST within
    each family. `quantile(feature, p)` returns the stock's own p-quantile
    of a feature's history (None = insufficient history); candidates with
    any unavailable threshold are omitted. The rel_confirmation family
    exists only when a sector ETF is mapped."""
    families: dict[str, list[MomentumRegime]] = {name: [] for name in FAMILIES}
    if etf is None:
        del families["rel_confirmation"]

    def add(family: str, label: str, description: str, feature: str, *filters) -> None:
        if all(f is not None for f in filters):
            families[family].append(
                MomentumRegime(family, label, description, feature, tuple(filters))
            )

    def ge(feature: str, p: float, symbol_override: str | None = None):
        value = quantile(feature, p)
        return None if value is None else ResearchFilter(feature, ">=", value, symbol_override)

    def le(feature: str, p: float):
        value = quantile(feature, p)
        return None if value is None else ResearchFilter(feature, "<=", value)

    def fmt(feature: str, p: float) -> str:
        value = quantile(feature, p)
        return f"{value:+.1%}" if value is not None else "n/a"

    # -- 1. absolute momentum ------------------------------------------------
    add(
        "abs_momentum",
        "broad momentum ≥ p70",
        f"{symbol}'s 21-, 63-, and 126-session returns were all above their own "
        f"70th percentiles ({fmt('ret_21d', 0.7)}/{fmt('ret_63d', 0.7)}/{fmt('ret_126d', 0.7)})",
        "ret_63d",
        ge("ret_21d", 0.7),
        ge("ret_63d", 0.7),
        ge("ret_126d", 0.7),
    )
    add(
        "abs_momentum",
        "63d ret ≥ p90",
        f"{symbol}'s 63-session return was in its own top decile (≥ {fmt('ret_63d', 0.9)})",
        "ret_63d",
        ge("ret_63d", 0.9),
    )
    add(
        "abs_momentum",
        "63d ret ≥ p70",
        f"{symbol}'s 63-session return was above its own 70th percentile "
        f"({fmt('ret_63d', 0.7)})",
        "ret_63d",
        ge("ret_63d", 0.7),
    )
    add(
        "abs_momentum",
        "63d ret ≤ p10",
        f"{symbol}'s 63-session return was in its own bottom decile (≤ {fmt('ret_63d', 0.1)})",
        "ret_63d",
        le("ret_63d", 0.1),
    )

    # -- 2. price extension ----------------------------------------------------
    add(
        "extension",
        "failed breakout",
        f"{symbol} was still near its 52-week high (top 40% of its own closeness) "
        "while its 21-session return fell into its bottom quintile "
        f"(≤ {fmt('ret_21d', 0.2)})",
        "dist_52w_high",
        ge("dist_52w_high", 0.6),
        le("ret_21d", 0.2),
    )
    add(
        "extension",
        "near 52w high, strong 63d",
        f"{symbol} was closer to its 52-week high than 90% of its own history "
        f"after a strong 63-session advance (≥ {fmt('ret_63d', 0.7)})",
        "dist_52w_high",
        ge("dist_52w_high", 0.9),
        ge("ret_63d", 0.7),
    )
    add(
        "extension",
        "extended > MA50 (p90)",
        f"{symbol} traded further above its 50-session MA than 90% of its own "
        f"history (≥ {fmt('price_to_ma50', 0.9)})",
        "price_to_ma50",
        ge("price_to_ma50", 0.9),
    )
    add(
        "extension",
        "extended > MA200 (p90)",
        f"{symbol} traded further above its 200-session MA than 90% of its own "
        f"history (≥ {fmt('price_to_ma200', 0.9)})",
        "price_to_ma200",
        ge("price_to_ma200", 0.9),
    )
    add(
        "extension",
        "deep drawdown (p10)",
        f"{symbol} traded deeper below its 52-week high than 90% of its own "
        f"history ({fmt('dist_52w_high', 0.1)} or lower)",
        "dist_52w_high",
        le("dist_52w_high", 0.1),
    )

    # -- 3. momentum acceleration / deceleration -----------------------------------
    add(
        "momentum_accel",
        "fading after advance",
        f"{symbol}'s 63-session return was above its 70th percentile "
        f"({fmt('ret_63d', 0.7)}) while its 21-session return dropped below its "
        f"40th percentile ({fmt('ret_21d', 0.4)})",
        "ret_21d",
        ge("ret_63d", 0.7),
        le("ret_21d", 0.4),
    )
    add(
        "momentum_accel",
        "momentum recovery",
        f"{symbol}'s 63-session return was in its bottom quintile "
        f"({fmt('ret_63d', 0.2)}) while its 21-session return climbed above its "
        f"60th percentile ({fmt('ret_21d', 0.6)})",
        "ret_21d",
        le("ret_63d", 0.2),
        ge("ret_21d", 0.6),
    )
    add(
        "momentum_accel",
        "short-term acceleration",
        f"{symbol}'s 21-session return was above its 80th percentile "
        f"({fmt('ret_21d', 0.8)}) while its 63-session return was still below its "
        "60th percentile",
        "ret_21d",
        ge("ret_21d", 0.8),
        le("ret_63d", 0.6),
    )

    # -- 4. volatility interaction ---------------------------------------------------
    add(
        "vol_interaction",
        "strong 63d, vol expanding",
        f"{symbol} posted a strong 63-session advance (≥ {fmt('ret_63d', 0.7)}) "
        "while its 21-vs-63-session volatility ratio was in its top quintile",
        "vol_ratio_21_63",
        ge("ret_63d", 0.7),
        ge("vol_ratio_21_63", 0.8),
    )
    add(
        "vol_interaction",
        "strong 63d, vol subdued",
        f"{symbol} posted a strong 63-session advance (≥ {fmt('ret_63d', 0.7)}) "
        "while its 21-vs-63-session volatility ratio stayed at or below its median",
        "vol_ratio_21_63",
        ge("ret_63d", 0.7),
        le("vol_ratio_21_63", 0.5),
    )
    add(
        "vol_interaction",
        "high ATR + extension",
        f"{symbol}'s 14-session ATR was in its top quintile while it traded far "
        "above its 50-session MA (top quintile)",
        "atr14_pct",
        ge("atr14_pct", 0.8),
        ge("price_to_ma50", 0.8),
    )
    add(
        "vol_interaction",
        "high-vol breakdown",
        f"{symbol}'s 21-session volatility was in its top quintile while its "
        f"21-session return fell into its bottom decile (≤ {fmt('ret_21d', 0.1)})",
        "vol_21d",
        ge("vol_21d", 0.8),
        le("ret_21d", 0.1),
    )

    # -- 5. relative momentum confirmation (sector FK required) ------------------------
    if etf is not None:
        add(
            "rel_confirmation",
            f"rising, fading vs {etf}",
            f"{symbol} posted a strong 63-session advance (≥ {fmt('ret_63d', 0.7)}) "
            f"while lagging its sector ETF {etf} over the last 21 sessions",
            "rel_ret_sector_21d",
            ge("ret_63d", 0.7),
            ResearchFilter("rel_ret_sector_21d", "<", 0.0),
        )
        add(
            "rel_confirmation",
            f"rising, confirmed vs {etf}",
            f"{symbol} posted a strong 63-session advance (≥ {fmt('ret_63d', 0.7)}) "
            f"while leading its sector ETF {etf} over 63 sessions",
            "rel_ret_sector_63d",
            ge("ret_63d", 0.7),
            ResearchFilter("rel_ret_sector_63d", ">", 0.0),
        )
        add(
            "rel_confirmation",
            f"lagging strong {etf}",
            f"{symbol} trailed its sector ETF {etf} over 63 sessions while {etf} " "itself led SPY",
            "rel_ret_sector_63d",
            ResearchFilter("rel_ret_sector_63d", "<", 0.0),
            ResearchFilter("rel_ret_spy_63d", ">", 0.0, symbol=etf),
        )

    # -- 6. trend structure ----------------------------------------------------------
    above_50 = ResearchFilter("price_to_ma50", ">=", 0.0)
    above_200 = ResearchFilter("price_to_ma200", ">=", 0.0)
    add(
        "trend_structure",
        "MA bull, spread widening",
        f"{symbol} traded above both its 50- and 200-session MAs with the MA "
        "spread widening vs 21 sessions earlier",
        "ma50_ma200_spread_chg_21d",
        above_50,
        above_200,
        ResearchFilter("ma50_ma200_spread_chg_21d", ">", 0.0),
    )
    add(
        "trend_structure",
        "MA bull, spread narrowing",
        f"{symbol} traded above both its 50- and 200-session MAs with the MA "
        "spread narrowing vs 21 sessions earlier",
        "ma50_ma200_spread_chg_21d",
        above_50,
        above_200,
        ResearchFilter("ma50_ma200_spread_chg_21d", "<", 0.0),
    )
    add(
        "trend_structure",
        "trend crack (<MA50)",
        f"{symbol} traded above its 200-session MA but below its 50-session MA",
        "price_to_ma50",
        above_200,
        ResearchFilter("price_to_ma50", "<", 0.0),
    )
    add(
        "trend_structure",
        "below both MAs",
        f"{symbol} traded below both its 50- and 200-session MAs",
        "price_to_ma200",
        ResearchFilter("price_to_ma50", "<", 0.0),
        ResearchFilter("price_to_ma200", "<", 0.0),
    )
    return families


class MomentumExhaustionModel(IntelligenceModel):
    name = "momentum_exhaustion"
    version = 1

    def __init__(
        self,
        session: Session,
        half_life_years: float = 10.0,  # recency: pre-2016 evidence counts less
        min_events: int = 5,  # studies thinner than this are ignored
        prior_events: float = 30.0,  # effective events needed for confidence 0.5
        min_history: int = MIN_PERCENTILE_OBS,
    ) -> None:
        self._session = session
        self._features = FeatureRepository(session)
        self._engine = ResearchEngine(session)
        self.half_life_years = half_life_years
        self.min_events = min_events
        self.prior_events = prior_events
        self.min_history = min_history

    # -- public ------------------------------------------------------------

    def evaluate(self, symbol: str, as_of: date | None = None) -> list[ModelScore]:
        etf = self._sector_etf(symbol)  # None = rel_confirmation family unavailable
        active, resolved_as_of = self._detect(symbol, etf, as_of)
        if resolved_as_of is None:  # features exist but none at/before as_of
            assert as_of is not None
            explanation = (
                f"No momentum features are stored at or before {as_of.isoformat()} for "
                f"{symbol} — insufficient data to detect a momentum regime. "
                "Neutral by construction."
            )
            return [
                self._neutral_score(symbol, as_of, label, sessions, (), explanation)
                for label, sessions in HORIZONS.items()
            ]
        if not active:
            explanation = (
                f"No momentum regime is currently active: {symbol}'s momentum, "
                "extension, volatility, and trend readings are all inside their own "
                "historical percentile thresholds. History offers no momentum-driven "
                "edge either way."
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

    # -- inputs ------------------------------------------------------------

    def _sector_etf(self, symbol: str) -> str | None:
        repo = InstrumentRepository(self._session)
        instrument = repo.get_by_symbol(symbol)
        if instrument is None:
            raise ConfigurationError(f"unknown symbol {symbol!r}")
        return repo.sector_etf_symbol(instrument)

    def _instrument_id(self, symbol: str) -> int:
        instrument_id = self._session.scalar(
            select(Instrument.id).where(Instrument.symbol == symbol)
        )
        if instrument_id is None:
            raise ConfigurationError(f"unknown symbol {symbol!r}")
        return instrument_id

    # -- regime detection ----------------------------------------------------

    def _detect(
        self, symbol: str, etf: str | None, as_of: date | None
    ) -> tuple[list[MomentumRegime], date | None]:
        """Active regimes from the latest stored values, with percentile
        thresholds computed from the stock's own history at/before as_of;
        resolved as_of = the newest feature date actually read, or None when
        features exist but hold no value at/before as_of."""
        cache: dict[tuple[str, str | None], pd.Series] = {}
        newest: list[date] = []  # mutable cell for the closures

        def load(feature: str, sym: str | None) -> pd.Series:
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
            if not series.empty:
                last = series.index[-1].date()
                if not newest or last > newest[0]:
                    newest[:] = [last]
            cache[key] = series
            return series

        def latest(feature: str, sym: str | None) -> float | None:
            series = load(feature, sym)
            return float(series.iloc[-1]) if not series.empty else None

        def quantile(feature: str, p: float) -> float | None:
            series = load(feature, None)  # percentiles are the STOCK's own
            if len(series) < self.min_history:
                return None
            return float(series.quantile(p))

        active = select_active(regime_candidates(symbol, etf, quantile), latest)
        if not newest:
            if as_of is None:  # nothing stored at all: a setup problem, not a data gap
                raise ConfigurationError(
                    f"no momentum features stored for {symbol!r}; " "run: mip features build --all"
                )
            return [], None
        return active, (as_of or newest[0])

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
                f"Momentum regimes are active ({', '.join(active_labels)}) but {symbol} "
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
            strongest_supporting_regimes=aggregate.supporting,  # continuation
            strongest_negative_regimes=aggregate.negative,  # exhaustion
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
        kind = "continuation" if lead.excess > 0 else "exhaustion"
        return (
            f"Across {lead.n} historical episodes (≈{lead.n_eff:.0f} independent-"
            f"equivalent) where {lead.description}, {symbol}'s following "
            f"{horizon_label} return averaged {lead.mean * 100:+.1f}% vs a "
            f"{lead.baseline_mean * 100:+.1f}% unconditional baseline — an excess of "
            f"{lead.excess * 100:+.1f}pp ({kind} evidence). Combined across "
            f"{len(evidence)} active momentum regimes, the evidence-weighted edge is "
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
