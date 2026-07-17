"""Valuation Intelligence Model.

Question answered: given where the stock's valuation sits RELATIVE TO ITS
OWN point-in-time history — and how that valuation interacts with growth,
quality, and the rate environment — what has historically happened next?

Thresholds are the stock's own empirical percentiles (deciles) of its
STORED valuation-feature history at/before as_of. Fundamentals features are
PIT-honest by construction (usable only from each snapshot's as_of_date
forward, never backfilled — D13/§7.4), so this model inherits that
discipline: no valuation percentile exists until MIN_PERCENTILE_OBS
sessions of genuine snapshot-derived history have accumulated, and until
then the model returns an explicit "insufficient historical valuation
evidence" neutral rather than a fabricated score. No generic rules like
"high P/E is bearish" are encoded: expensive-with-strong-growth and
expensive-with-weak-growth are DIFFERENT regimes and the stock's own
history decides which way each cuts.

Aggregation is the shared hardened framework (models.base): one active
regime per family (most specific first), Bartlett-kernel within-study SE
inflation, correlated cross-regime combination (the same expensive days
seen through growth/quality/rates lenses are never counted as independent
confirmations), agreement-based confidence, saturation diagnostics.
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

HORIZONS: dict[str, int] = {"1w": 5, "2w": 10, "1m": 21, "3m": 63, "6m": 126, "1y": 252}
MIN_PERCENTILE_OBS = 252  # a year of stored valuation history per percentile

# The multiples whose stored history depth decides "insufficient evidence".
CORE_MULTIPLES = ("pe_trailing", "pe_forward", "price_to_sales")

FAMILIES = (
    "abs_valuation",
    "growth_adjusted",
    "valuation_change",
    "quality",
    "rates_env",
)


@dataclass(frozen=True)
class ValuationRegime:
    """One candidate condition. `family` scopes the no-double-counting rule:
    at most one regime per family may be active at a time."""

    family: str
    label: str  # stable, short: 'trailing P/E ≥ p90'
    description: str  # prose with the actual threshold values
    feature: str  # primary feature, for RegimeEvidence
    filters: tuple[ResearchFilter, ...]


def regime_candidates(
    symbol: str,
    quantile,  # Callable[[str, float], float | None]: the stock's own percentile value
) -> dict[str, list[ValuationRegime]]:
    """All candidate regimes keyed by family, MOST SPECIFIC FIRST within
    each family. `quantile(feature, p)` returns the stock's own p-quantile
    of a feature's stored history (None = insufficient history); candidates
    with any unavailable threshold are omitted — with no snapshot depth the
    grammar is empty and the model reports insufficiency honestly."""
    families: dict[str, list[ValuationRegime]] = {name: [] for name in FAMILIES}

    def add(family: str, label: str, description: str, feature: str, *filters) -> None:
        if all(f is not None for f in filters):
            families[family].append(
                ValuationRegime(family, label, description, feature, tuple(filters))
            )

    def ge(feature: str, p: float):
        value = quantile(feature, p)
        return None if value is None else ResearchFilter(feature, ">=", value)

    def le(feature: str, p: float):
        value = quantile(feature, p)
        return None if value is None else ResearchFilter(feature, "<=", value)

    def fmt(feature: str, p: float) -> str:
        value = quantile(feature, p)
        return f"{value:.2f}" if value is not None else "n/a"

    # -- 1. absolute historical valuation --------------------------------------
    add(
        "abs_valuation",
        "expensive on P/E and P/S",
        f"{symbol} traded above its own 80th percentile on BOTH trailing P/E "
        f"(≥ {fmt('pe_trailing', 0.8)}) and price-to-sales (≥ {fmt('price_to_sales', 0.8)})",
        "pe_trailing",
        ge("pe_trailing", 0.8),
        ge("price_to_sales", 0.8),
    )
    add(
        "abs_valuation",
        "trailing P/E ≥ p90",
        f"{symbol}'s trailing P/E was in its own top decile (≥ {fmt('pe_trailing', 0.9)})",
        "pe_trailing",
        ge("pe_trailing", 0.9),
    )
    add(
        "abs_valuation",
        "forward P/E ≥ p90",
        f"{symbol}'s forward P/E was in its own top decile (≥ {fmt('pe_forward', 0.9)})",
        "pe_forward",
        ge("pe_forward", 0.9),
    )
    add(
        "abs_valuation",
        "P/S ≥ p90",
        f"{symbol}'s price-to-sales was in its own top decile (≥ {fmt('price_to_sales', 0.9)})",
        "price_to_sales",
        ge("price_to_sales", 0.9),
    )
    add(
        "abs_valuation",
        "trailing P/E ≤ p10",
        f"{symbol}'s trailing P/E was in its own bottom decile (≤ {fmt('pe_trailing', 0.1)})",
        "pe_trailing",
        le("pe_trailing", 0.1),
    )
    add(
        "abs_valuation",
        "P/S ≤ p10",
        f"{symbol}'s price-to-sales was in its own bottom decile "
        f"(≤ {fmt('price_to_sales', 0.1)})",
        "price_to_sales",
        le("price_to_sales", 0.1),
    )

    # -- 2. growth-adjusted valuation --------------------------------------------
    add(
        "growth_adjusted",
        "expensive, strong growth",
        f"{symbol} traded above its 80th P/E percentile (≥ {fmt('pe_trailing', 0.8)}) "
        "while revenue growth sat above its own 70th percentile",
        "pe_trailing",
        ge("pe_trailing", 0.8),
        ge("revenue_growth_yoy", 0.7),
    )
    add(
        "growth_adjusted",
        "expensive, weak growth",
        f"{symbol} traded above its 80th P/E percentile (≥ {fmt('pe_trailing', 0.8)}) "
        "while revenue growth sat below its own 30th percentile",
        "pe_trailing",
        ge("pe_trailing", 0.8),
        le("revenue_growth_yoy", 0.3),
    )
    add(
        "growth_adjusted",
        "expansion without growth",
        f"{symbol}'s trailing P/E expanded into its top quintile of 63-session "
        "changes while reported EPS growth sat at or below its median",
        "pe_trailing_chg_63d",
        ge("pe_trailing_chg_63d", 0.8),
        le("eps_growth_yoy", 0.5),
    )
    add(
        "growth_adjusted",
        "cheap, improving growth",
        f"{symbol} traded below its 20th P/E percentile (≤ {fmt('pe_trailing', 0.2)}) "
        "while revenue growth sat above its own 60th percentile",
        "pe_trailing",
        le("pe_trailing", 0.2),
        ge("revenue_growth_yoy", 0.6),
    )
    add(
        "growth_adjusted",
        "cheap, weak growth",
        f"{symbol} traded below its 20th P/E percentile (≤ {fmt('pe_trailing', 0.2)}) "
        "while revenue growth sat below its own 30th percentile",
        "pe_trailing",
        le("pe_trailing", 0.2),
        le("revenue_growth_yoy", 0.3),
    )

    # -- 3. valuation change ---------------------------------------------------------
    add(
        "valuation_change",
        "price up, fwd P/E expanding",
        f"{symbol}'s price rose over 63 sessions while its forward P/E expanded "
        "into its top quintile of 63-session changes (estimates not keeping up)",
        "pe_forward_chg_63d",
        ResearchFilter("ret_63d", ">", 0.0),
        ge("pe_forward_chg_63d", 0.8),
    )
    add(
        "valuation_change",
        "price down, multiple normalizing",
        f"{symbol}'s price fell over 63 sessions while its trailing P/E compressed "
        "into its bottom quintile of 63-session changes",
        "pe_trailing_chg_63d",
        ResearchFilter("ret_63d", "<", 0.0),
        le("pe_trailing_chg_63d", 0.2),
    )
    add(
        "valuation_change",
        "multiple expansion",
        f"{symbol}'s trailing P/E 63-session change sat in its own top quintile",
        "pe_trailing_chg_63d",
        ge("pe_trailing_chg_63d", 0.8),
    )
    add(
        "valuation_change",
        "multiple compression",
        f"{symbol}'s trailing P/E 63-session change sat in its own bottom quintile",
        "pe_trailing_chg_63d",
        le("pe_trailing_chg_63d", 0.2),
    )

    # -- 4. valuation versus quality -----------------------------------------------------
    add(
        "quality",
        "expensive, strong margins",
        f"{symbol} traded above its 80th P/E percentile while its profit margin "
        "sat above its own 70th percentile",
        "profit_margin",
        ge("pe_trailing", 0.8),
        ge("profit_margin", 0.7),
    )
    add(
        "quality",
        "expensive, weak margins",
        f"{symbol} traded above its 80th P/E percentile while its profit margin "
        "sat below its own 30th percentile",
        "profit_margin",
        ge("pe_trailing", 0.8),
        le("profit_margin", 0.3),
    )
    add(
        "quality",
        "cheap, strong margins",
        f"{symbol} traded below its 20th P/E percentile while its profit margin "
        "sat above its own 60th percentile",
        "profit_margin",
        le("pe_trailing", 0.2),
        ge("profit_margin", 0.6),
    )
    add(
        "quality",
        "cheap, weak margins",
        f"{symbol} traded below its 20th P/E percentile while its profit margin "
        "sat below its own 30th percentile",
        "profit_margin",
        le("pe_trailing", 0.2),
        le("profit_margin", 0.3),
    )

    # -- 5. valuation versus rates --------------------------------------------------------
    add(
        "rates_env",
        "expensive, rising rates",
        f"{symbol} traded above its 80th P/E percentile while the 10Y yield had "
        "risen more than 25 bps over 63 sessions",
        "pe_trailing",
        ge("pe_trailing", 0.8),
        ResearchFilter("regime_rising_rates", "==", 1.0),
    )
    add(
        "rates_env",
        "expensive, falling rates",
        f"{symbol} traded above its 80th P/E percentile while the 10Y yield had "
        "fallen more than 25 bps over 63 sessions",
        "pe_trailing",
        ge("pe_trailing", 0.8),
        ResearchFilter("regime_falling_rates", "==", 1.0),
    )
    add(
        "rates_env",
        "cheap, rising rates",
        f"{symbol} traded below its 20th P/E percentile during restrictive "
        "(rising-rate) conditions",
        "pe_trailing",
        le("pe_trailing", 0.2),
        ResearchFilter("regime_rising_rates", "==", 1.0),
    )
    return families


def verdict(lead: RegimeEvidence) -> str:
    """Explanation archetype from the lead regime's label + evidence sign:
    the model distinguishes expensive-but-justified, expensive-vulnerable,
    cheap-improving, and value-trap histories in plain words."""
    label, favorable = lead.label, lead.excess > 0
    expensive = label.startswith(("expensive", "price up")) or "≥ p9" in label
    cheap = label.startswith("cheap") or "≤ p1" in label
    if expensive:
        if not favorable:
            return "Expensive and historically vulnerable"
        if "growth" in label:
            return "Expensive but historically justified by growth"
        if "margins" in label:
            return "Expensive but historically justified by quality"
        return "Expensive but historically resilient"
    if cheap:
        if favorable:
            if "improving" in label or "strong" in label:
                return "Cheap with improving fundamentals"
            return "Historically favorable at this depressed valuation"
        if "weak" in label:
            return "Cheap because fundamentals are deteriorating (value-trap history)"
        return "Historically unfavorable despite the depressed valuation"
    return "Historically favorable setup" if favorable else "Historically unfavorable setup"


class ValuationModel(IntelligenceModel):
    name = "valuation"
    version = 1

    def __init__(
        self,
        session: Session,
        half_life_years: float = 10.0,  # recency: older evidence counts less
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
        active, resolved_as_of, spans = self._detect(symbol, as_of)

        if not any(spans.get(name, 0) >= self.min_history for name in CORE_MULTIPLES):
            resolved = resolved_as_of or as_of or self._latest_feature_date(symbol) or date.today()
            depth = ", ".join(f"{name}: {spans.get(name, 0)} sessions" for name in CORE_MULTIPLES)
            explanation = (
                f"Insufficient historical valuation evidence for {symbol}: no valuation "
                f"multiple has the {self.min_history} stored point-in-time sessions a "
                f"percentile needs ({depth}). Fundamentals snapshots are collected "
                "forward-only (never backfilled), so real valuation scoring requires "
                "about a year of accumulated daily snapshots. Neutral by construction."
            )
            return [
                self._neutral_score(symbol, resolved, label, sessions, (), explanation)
                for label, sessions in HORIZONS.items()
            ]
        if resolved_as_of is None:  # depth exists, but not at/before this as_of
            assert as_of is not None
            explanation = (
                f"No valuation features are stored at or before {as_of.isoformat()} for "
                f"{symbol} — insufficient data to detect a valuation regime. "
                "Neutral by construction."
            )
            return [
                self._neutral_score(symbol, as_of, label, sessions, (), explanation)
                for label, sessions in HORIZONS.items()
            ]
        if not active:
            explanation = (
                f"No valuation regime is currently active: {symbol}'s multiples, "
                "growth-adjusted readings, and rate-conditioned valuations are all "
                "inside their own historical percentile thresholds. History offers "
                "no valuation-driven edge either way."
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

    # -- regime detection ----------------------------------------------------

    def _detect(
        self, symbol: str, as_of: date | None
    ) -> tuple[list[ValuationRegime], date | None, dict[str, int]]:
        """Active regimes plus (resolved as_of, stored-history spans of the
        core multiples). Percentile thresholds come from the stock's own
        PIT feature history at/before as_of; a multiple with fewer than
        min_history sessions yields no thresholds — never a guess."""
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

        for name in CORE_MULTIPLES:  # always measured, for honest reporting
            quantile(name, 0.5)
        active = select_active(regime_candidates(symbol, quantile), latest)
        return active, (as_of or (newest[0] if newest else None)), spans

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
                f"Valuation regimes are active ({', '.join(active_labels)}) but {symbol} "
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
        # Narrate the most significant study that AGREES with the combined
        # direction, preferring growth/quality-qualified regimes — they carry
        # the expensive-but-justified / value-trap distinction the plain
        # percentile regimes cannot express.
        agreeing = [e for e in evidence if (e.excess > 0) == (effect > 0)] or list(evidence)
        qualified = [e for e in agreeing if "growth" in e.label or "margins" in e.label]
        lead = max(qualified or agreeing, key=lambda e: abs(e.excess / e.se))
        return (
            f"{verdict(lead)}: across {lead.n} historical episodes "
            f"(≈{lead.n_eff:.0f} independent-equivalent) where {lead.description}, "
            f"{symbol}'s following {horizon_label} return averaged "
            f"{lead.mean * 100:+.1f}% vs a {lead.baseline_mean * 100:+.1f}% unconditional "
            f"baseline — an excess of {lead.excess * 100:+.1f}pp. Combined across "
            f"{len(evidence)} active valuation regimes, the evidence-weighted edge is "
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
