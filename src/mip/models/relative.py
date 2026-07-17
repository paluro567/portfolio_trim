"""Relative Strength Intelligence Model.

Question answered: how strong is THIS STOCK relative to everything around
it — the market, its sector, its own leadership history — and has similar
leadership historically persisted or reversed over each forward horizon?

Distinct from Sector Rotation by construction: that model asks how the
SECTOR is behaving (conditions on the ETF, fixed rotation thresholds);
this model asks how the STOCK is leading or lagging, with thresholds drawn
from the stock's own percentile history, plus persistence structure
(leadership intact / cracking / weakness reversing) and alpha acceleration
that the sector model has no analogue for. Whether leadership persists or
mean-reverts is decided per stock by its own evidence, never by
technical-analysis heuristics.

Families: market leadership (vs SPY), sector leadership (vs the FK-mapped
sector ETF; skipped cleanly when unmapped), industry leadership (an HONEST
PLACEHOLDER — the frozen schema has no industry→ETF mapping, so the family
is always empty until an architecture amendment adds one), leadership
persistence across 5/21/63/126-session windows, leadership breadth (stock
leadership crossed with sector/market strength), and relative momentum
(21-session alpha acceleration). No new features were required: raw
relative-return percentiles over four windows already span the grammar
(rolling alpha/beta and information-ratio variants were considered and
rejected as estimation noise at this universe size).

Aggregation is the shared hardened framework (models.base): one active
regime per family (most specific first), Bartlett-kernel within-study SE
inflation, correlated cross-regime combination, agreement-based confidence,
saturation diagnostics.
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
MIN_PERCENTILE_OBS = 252  # a year of stored history before a percentile is meaningful

# The features whose stored depth decides "insufficient history".
CORE_FEATURES = ("rel_ret_spy_21d", "rel_ret_spy_63d", "rel_ret_spy_126d")

FAMILIES = (
    "market_leadership",
    "sector_leadership",  # skipped cleanly when no sector-ETF mapping exists
    "industry_leadership",  # placeholder: frozen schema has no industry->ETF map
    "persistence",
    "breadth",
    "relative_momentum",
)


@dataclass(frozen=True)
class StrengthRegime:
    """One candidate condition. `family` scopes the no-double-counting rule:
    at most one regime per family may be active at a time."""

    family: str
    label: str  # stable, short: 'persistent alpha'
    description: str  # prose with the actual threshold values
    feature: str  # primary feature, for RegimeEvidence
    filters: tuple[ResearchFilter, ...]


def regime_candidates(
    symbol: str,
    etf: str | None,
    quantile,  # Callable[[str, float], float | None]: the stock's own percentile value
) -> dict[str, list[StrengthRegime]]:
    """All candidate regimes keyed by family, MOST SPECIFIC FIRST within
    each family. `quantile(feature, p)` returns the stock's own p-quantile
    of a feature's history (None = insufficient history); candidates with
    any unavailable threshold are omitted. Sector-dependent families exist
    only when a sector ETF is mapped; industry leadership is always empty
    until the architecture gains an industry->ETF mapping."""
    families: dict[str, list[StrengthRegime]] = {name: [] for name in FAMILIES}
    if etf is None:
        del families["sector_leadership"]

    def add(family: str, label: str, description: str, feature: str, *filters) -> None:
        if all(f is not None for f in filters):
            families[family].append(
                StrengthRegime(family, label, description, feature, tuple(filters))
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

    # -- 1. market leadership (vs SPY) ------------------------------------------
    add(
        "market_leadership",
        "persistent alpha",
        f"{symbol} led SPY across 21-, 63-, and 126-session windows, all above "
        f"their own 70th percentiles ({fmt('rel_ret_spy_63d', 0.7)} at 63d)",
        "rel_ret_spy_63d",
        ge("rel_ret_spy_21d", 0.7),
        ge("rel_ret_spy_63d", 0.7),
        ge("rel_ret_spy_126d", 0.7),
    )
    add(
        "market_leadership",
        "persistent underperformance",
        f"{symbol} lagged SPY across 21-, 63-, and 126-session windows, all below "
        "their own 30th percentiles",
        "rel_ret_spy_63d",
        le("rel_ret_spy_21d", 0.3),
        le("rel_ret_spy_63d", 0.3),
        le("rel_ret_spy_126d", 0.3),
    )
    add(
        "market_leadership",
        "strong market leader",
        f"{symbol}'s 63-session lead over SPY sat in its own top decile "
        f"(≥ {fmt('rel_ret_spy_63d', 0.9)})",
        "rel_ret_spy_63d",
        ge("rel_ret_spy_63d", 0.9),
    )
    add(
        "market_leadership",
        "strong market laggard",
        f"{symbol}'s 63-session shortfall vs SPY sat in its own bottom decile "
        f"(≤ {fmt('rel_ret_spy_63d', 0.1)})",
        "rel_ret_spy_63d",
        le("rel_ret_spy_63d", 0.1),
    )
    add(
        "market_leadership",
        "market leader",
        f"{symbol}'s 63-session return vs SPY was above its own 70th percentile",
        "rel_ret_spy_63d",
        ge("rel_ret_spy_63d", 0.7),
    )
    add(
        "market_leadership",
        "market laggard",
        f"{symbol}'s 63-session return vs SPY was below its own 30th percentile",
        "rel_ret_spy_63d",
        le("rel_ret_spy_63d", 0.3),
    )

    # -- 2. sector leadership (vs the FK-mapped sector ETF) ------------------------
    if etf is not None:
        add(
            "sector_leadership",
            f"strong leader vs {etf}",
            f"{symbol}'s 63-session lead over its sector ETF {etf} sat in its own "
            f"top decile (≥ {fmt('rel_ret_sector_63d', 0.9)})",
            "rel_ret_sector_63d",
            ge("rel_ret_sector_63d", 0.9),
        )
        add(
            "sector_leadership",
            f"strong laggard vs {etf}",
            f"{symbol}'s 63-session shortfall vs its sector ETF {etf} sat in its "
            "own bottom decile",
            "rel_ret_sector_63d",
            le("rel_ret_sector_63d", 0.1),
        )
        add(
            "sector_leadership",
            f"leader vs {etf}",
            f"{symbol}'s 63-session return vs {etf} was above its own 70th percentile",
            "rel_ret_sector_63d",
            ge("rel_ret_sector_63d", 0.7),
        )
        add(
            "sector_leadership",
            f"laggard vs {etf}",
            f"{symbol}'s 63-session return vs {etf} was below its own 30th percentile",
            "rel_ret_sector_63d",
            le("rel_ret_sector_63d", 0.3),
        )

    # -- 3. industry leadership: no industry->ETF mapping exists in the frozen
    # schema — the family stays empty (honest absence) until an amendment.

    # -- 4. leadership persistence (multi-window structure) --------------------------
    add(
        "persistence",
        "leadership intact",
        f"{symbol} led SPY over 126 sessions (≥ {fmt('rel_ret_spy_126d', 0.7)}) "
        "and was still leading over the last 5 sessions",
        "rel_ret_spy_126d",
        ge("rel_ret_spy_126d", 0.7),
        ge("rel_ret_spy_5d", 0.6),
    )
    add(
        "persistence",
        "leadership cracking",
        f"{symbol} led SPY over 126 sessions (≥ {fmt('rel_ret_spy_126d', 0.7)}) "
        "but its 5-session relative return fell into its bottom quintile",
        "rel_ret_spy_5d",
        ge("rel_ret_spy_126d", 0.7),
        le("rel_ret_spy_5d", 0.2),
    )
    add(
        "persistence",
        "weakness reversing",
        f"{symbol} lagged SPY over 126 sessions (≤ {fmt('rel_ret_spy_126d', 0.3)}) "
        "while its 5-session relative return jumped into its top quintile",
        "rel_ret_spy_5d",
        le("rel_ret_spy_126d", 0.3),
        ge("rel_ret_spy_5d", 0.8),
    )
    add(
        "persistence",
        "weakness persisting",
        f"{symbol} lagged SPY over 126 sessions (≤ {fmt('rel_ret_spy_126d', 0.3)}) "
        "and over the last 5 sessions as well",
        "rel_ret_spy_126d",
        le("rel_ret_spy_126d", 0.3),
        le("rel_ret_spy_5d", 0.4),
    )

    # -- 5. leadership breadth (stock vs sector/market strength) ----------------------
    if etf is not None:
        add(
            "breadth",
            "solo leadership (sector weak)",
            f"{symbol} led SPY (63-session relative return above its 70th "
            f"percentile) while its sector ETF {etf} trailed SPY",
            "rel_ret_spy_63d",
            ge("rel_ret_spy_63d", 0.7),
            ResearchFilter("rel_ret_spy_63d", "<", 0.0, symbol=etf),
        )
        add(
            "breadth",
            "left behind (sector strong)",
            f"{symbol} lagged SPY (63-session relative return below its 30th "
            f"percentile) while its sector ETF {etf} led SPY",
            "rel_ret_spy_63d",
            le("rel_ret_spy_63d", 0.3),
            ResearchFilter("rel_ret_spy_63d", ">", 0.0, symbol=etf),
        )
        add(
            "breadth",
            "confirmed leadership",
            f"{symbol} led SPY while its sector ETF {etf} also led SPY "
            "(leadership with breadth)",
            "rel_ret_spy_63d",
            ge("rel_ret_spy_63d", 0.7),
            ResearchFilter("rel_ret_spy_63d", ">", 0.0, symbol=etf),
        )
    add(
        "breadth",
        "leader in weak market",
        f"{symbol} led SPY (63-session relative return above its 70th percentile) "
        "while SPY itself traded below its 200-session average (narrow leadership)",
        "rel_ret_spy_63d",
        ge("rel_ret_spy_63d", 0.7),
        ResearchFilter("regime_bull", "==", 0.0),
    )

    # -- 6. relative momentum (alpha acceleration) --------------------------------------
    add(
        "relative_momentum",
        "strong but fading",
        f"{symbol} led SPY over 63 sessions (≥ {fmt('rel_ret_spy_63d', 0.7)}) while "
        "its 21-session alpha change fell into its bottom quintile (exhaustion setup)",
        "rel_ret_spy_accel_21d",
        ge("rel_ret_spy_63d", 0.7),
        le("rel_ret_spy_accel_21d", 0.2),
    )
    add(
        "relative_momentum",
        "weak but recovering",
        f"{symbol} lagged SPY over 63 sessions (≤ {fmt('rel_ret_spy_63d', 0.3)}) while "
        "its 21-session alpha change jumped into its top quintile (emerging leadership)",
        "rel_ret_spy_accel_21d",
        le("rel_ret_spy_63d", 0.3),
        ge("rel_ret_spy_accel_21d", 0.8),
    )
    add(
        "relative_momentum",
        "alpha accelerating",
        f"{symbol}'s 21-session alpha change sat in its own top quintile "
        f"(≥ {fmt('rel_ret_spy_accel_21d', 0.8)})",
        "rel_ret_spy_accel_21d",
        ge("rel_ret_spy_accel_21d", 0.8),
    )
    add(
        "relative_momentum",
        "alpha deteriorating",
        f"{symbol}'s 21-session alpha change sat in its own bottom quintile "
        f"(≤ {fmt('rel_ret_spy_accel_21d', 0.2)})",
        "rel_ret_spy_accel_21d",
        le("rel_ret_spy_accel_21d", 0.2),
    )
    return families


class RelativeStrengthModel(IntelligenceModel):
    name = "relative_strength"
    version = 1

    def __init__(
        self,
        session: Session,
        half_life_years: float = 10.0,  # recency: older leadership counts less
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
        etf = self._sector_etf(symbol)
        active, resolved_as_of, spans = self._detect(symbol, etf, as_of)

        if not any(spans.get(name, 0) >= self.min_history for name in CORE_FEATURES):
            resolved = resolved_as_of or as_of or self._latest_feature_date(symbol) or date.today()
            depth = ", ".join(f"{name}: {spans.get(name, 0)}" for name in CORE_FEATURES)
            explanation = (
                f"Insufficient relative-return history for {symbol}: no leadership "
                f"feature has the {self.min_history} stored sessions a percentile "
                f"needs ({depth}). Neutral by construction."
            )
            return [
                self._neutral_score(symbol, resolved, label, sessions, (), explanation)
                for label, sessions in HORIZONS.items()
            ]
        if resolved_as_of is None:  # history exists, but not at/before this as_of
            assert as_of is not None
            explanation = (
                f"No relative-strength features are stored at or before "
                f"{as_of.isoformat()} for {symbol} — insufficient data. "
                "Neutral by construction."
            )
            return [
                self._neutral_score(symbol, as_of, label, sessions, (), explanation)
                for label, sessions in HORIZONS.items()
            ]
        if not active:
            explanation = (
                f"No relative-strength regime is currently active: {symbol}'s "
                "leadership, persistence, breadth, and alpha-momentum readings are "
                "all inside their own historical percentile thresholds. History "
                "offers no leadership-driven edge either way."
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

    def _latest_feature_date(self, symbol: str) -> date | None:
        definition = self._features.get_definition("ret_21d")
        if definition is None:
            return None
        series = self._features.get_instrument_series(definition.id, self._instrument_id(symbol))
        return series.index[-1].date() if not series.empty else None

    # -- regime detection ----------------------------------------------------

    def _detect(
        self, symbol: str, etf: str | None, as_of: date | None
    ) -> tuple[list[StrengthRegime], date | None, dict[str, int]]:
        """Active regimes plus (resolved as_of, stored spans of the core
        leadership features)."""
        cache: dict[tuple[str, str | None], pd.Series] = {}
        newest: list[date] = []  # mutable cell for the closures
        spans: dict[str, int] = {}

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
            spans[feature] = len(series)
            if len(series) < self.min_history:
                return None
            return float(series.quantile(p))

        for name in CORE_FEATURES:  # always measured, for honest reporting
            quantile(name, 0.5)
        active = select_active(regime_candidates(symbol, etf, quantile), latest)
        return active, (as_of or (newest[0] if newest else None)), spans

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
                f"Relative-strength regimes are active ({', '.join(active_labels)}) "
                f"but {symbol} has fewer than {self.min_events} resolved comparable "
                "leadership environments at this horizon — no score can be supported "
                "by evidence."
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
        direction = (
            "leadership like this has persisted"
            if lead.excess > 0
            else "leadership like this has faded"
        )
        return (
            f"For {symbol}, {direction}: across {lead.n} comparable leadership "
            f"environments (≈{lead.n_eff:.0f} independent-equivalent) where "
            f"{lead.description}, the following {horizon_label} return averaged "
            f"{lead.mean * 100:+.1f}% vs a {lead.baseline_mean * 100:+.1f}% unconditional "
            f"baseline — an excess of {lead.excess * 100:+.1f}pp with a "
            f"{lead.hit_rate * 100:.0f}% hit rate. Combined across {len(evidence)} active "
            f"relative-strength regimes, the evidence-weighted edge is "
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
