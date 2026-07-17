"""Macro Regime Intelligence Model.

Question answered: given today's overall macroeconomic environment — the
INTERACTION of inflation, policy, the yield curve, growth, and risk
appetite, not any single variable — how has this stock historically
behaved over each forward horizon?

The model never forecasts macro data: it detects which completed,
then-knowable macro environment is in force today (every macro feature
already carries its publication lag — D13) and asks the Research Engine
what this stock did in every comparable historical environment. Whether a
given environment is favorable is decided per stock by its own evidence,
never by economic opinion.

Thresholds are each macro feature's own percentiles (≥ MIN_PERCENTILE_OBS
stored sessions) or natural boundaries (curve slope below zero = inverted;
signed changes for easing/tightening and steepening/flattening). All
conditions are MARKET-scope, so the regime state is shared across the
universe — differentiation comes entirely from how each stock historically
responded, which is the model's purpose.

Documented limitations: GDP is quarterly with a ~120-day publication lag
(included in the growth family, inherently stale); consumer sentiment
(UMCSENT) plus VIX stand in for "sentiment"; monthly series enter daily
features as duration-weighted steps.

Aggregation is the shared hardened framework (models.base): one active
regime per family (most specific first), Bartlett-kernel within-study SE
inflation, correlated cross-regime combination (macro environments persist
for months, so the same episodes appear across families and the measured
cross-correlation is high — priced in, never assumed away), agreement-based
confidence, saturation diagnostics.
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
MIN_PERCENTILE_OBS = 252  # a year of stored history before a percentile is meaningful

# The features whose stored depth decides "insufficient macro history".
CORE_FEATURES = ("cpi_yoy", "fedfunds_level", "curve_slope_10y2y", "vix_pctile_252d")

FAMILIES = (
    "inflation",
    "policy",
    "yield_curve",
    "growth",
    "risk_appetite",
    "composite",
)


@dataclass(frozen=True)
class MacroRegime:
    """One candidate condition. `family` scopes the no-double-counting rule:
    at most one regime per family may be active at a time."""

    family: str
    label: str  # stable, short: 'disinflation + easing'
    description: str  # prose with the actual threshold values
    feature: str  # primary feature, for RegimeEvidence
    filters: tuple[ResearchFilter, ...]


def regime_candidates(quantile) -> dict[str, list[MacroRegime]]:
    """All candidate regimes keyed by family, MOST SPECIFIC FIRST within
    each family. `quantile(feature, p)` returns the p-quantile of a MARKET
    feature's stored history (None = insufficient history); candidates with
    any unavailable threshold are omitted. Sign/boundary conditions need no
    percentile history."""
    families: dict[str, list[MacroRegime]] = {name: [] for name in FAMILIES}

    def add(family: str, label: str, description: str, feature: str, *filters) -> None:
        if all(f is not None for f in filters):
            families[family].append(
                MacroRegime(family, label, description, feature, tuple(filters))
            )

    def ge(feature: str, p: float):
        value = quantile(feature, p)
        return None if value is None else ResearchFilter(feature, ">=", value)

    def le(feature: str, p: float):
        value = quantile(feature, p)
        return None if value is None else ResearchFilter(feature, "<=", value)

    def fmt(feature: str, p: float, pct: bool = True) -> str:
        value = quantile(feature, p)
        if value is None:
            return "n/a"
        return f"{value:+.1%}" if pct else f"{value:+.2f}"

    # boundary conditions (no fitted constants)
    inverted = ResearchFilter("curve_slope_10y2y", "<", 0.0)
    accel_up = ResearchFilter("cpi_yoy_accel", ">", 0.0)
    accel_down = ResearchFilter("cpi_yoy_accel", "<", 0.0)
    ff_rising = ResearchFilter("fedfunds_chg_6m", ">", 0.0)
    ff_falling = ResearchFilter("fedfunds_chg_6m", "<", 0.0)
    bull = ResearchFilter("regime_bull", "==", 1.0)
    not_bull = ResearchFilter("regime_bull", "==", 0.0)
    unrate_rising = ResearchFilter("unrate_chg_6m", ">", 0.0)
    unrate_easing = ResearchFilter("unrate_chg_6m", "<=", 0.0)

    # -- 1. inflation -----------------------------------------------------------
    add(
        "inflation",
        "hot inflation, rising",
        f"CPI inflation sat above its own 70th percentile ({fmt('cpi_yoy', 0.7)}) "
        "and was still accelerating",
        "cpi_yoy",
        ge("cpi_yoy", 0.7),
        accel_up,
    )
    add(
        "inflation",
        "disinflation from high",
        f"CPI inflation was above its median ({fmt('cpi_yoy', 0.5)}) but decelerating",
        "cpi_yoy",
        ge("cpi_yoy", 0.5),
        accel_down,
    )
    add(
        "inflation",
        "inflation accelerating",
        "the change in CPI YoY vs 3 months earlier sat in its own top quintile",
        "cpi_yoy_accel",
        ge("cpi_yoy_accel", 0.8),
    )
    add(
        "inflation",
        "inflation decelerating",
        "the change in CPI YoY vs 3 months earlier sat in its own bottom quintile",
        "cpi_yoy_accel",
        le("cpi_yoy_accel", 0.2),
    )

    # -- 2. policy ---------------------------------------------------------------
    add(
        "policy",
        "tightening cycle",
        "the Fed Funds rate had risen over the prior 6 months into its own top "
        "quintile of 6-month changes",
        "fedfunds_chg_6m",
        ge("fedfunds_chg_6m", 0.8),
        ff_rising,
    )
    add(
        "policy",
        "easing cycle",
        "the Fed Funds rate had fallen over the prior 6 months into its own bottom "
        "quintile of 6-month changes",
        "fedfunds_chg_6m",
        le("fedfunds_chg_6m", 0.2),
        ff_falling,
    )
    add(
        "policy",
        "restrictive policy",
        f"the Fed Funds rate sat above its own 80th percentile "
        f"({fmt('fedfunds_level', 0.8, pct=False)}%)",
        "fedfunds_level",
        ge("fedfunds_level", 0.8),
    )
    add(
        "policy",
        "accommodative policy",
        f"the Fed Funds rate sat below its own 20th percentile "
        f"({fmt('fedfunds_level', 0.2, pct=False)}%)",
        "fedfunds_level",
        le("fedfunds_level", 0.2),
    )

    # -- 3. yield curve --------------------------------------------------------------
    add(
        "yield_curve",
        "inversion normalizing",
        "the 10y-2y curve was inverted but re-steepening over 63 sessions",
        "curve_slope_10y2y",
        inverted,
        ResearchFilter("curve_slope_10y2y_chg_63d", ">", 0.0),
    )
    add(
        "yield_curve",
        "inversion deepening",
        "the 10y-2y curve was inverted and still flattening over 63 sessions",
        "curve_slope_10y2y",
        inverted,
        ResearchFilter("curve_slope_10y2y_chg_63d", "<", 0.0),
    )
    add(
        "yield_curve",
        "curve steepening",
        "the 63-session change in the 10y-2y slope sat in its own top quintile",
        "curve_slope_10y2y_chg_63d",
        ge("curve_slope_10y2y_chg_63d", 0.8),
    )
    add(
        "yield_curve",
        "curve flattening",
        "the 63-session change in the 10y-2y slope sat in its own bottom quintile",
        "curve_slope_10y2y_chg_63d",
        le("curve_slope_10y2y_chg_63d", 0.2),
    )

    # -- 4. growth ----------------------------------------------------------------------
    add(
        "growth",
        "employment weakening",
        "the unemployment rate had risen over 6 months into its own top quintile " "of changes",
        "unrate_chg_6m",
        ge("unrate_chg_6m", 0.8),
        unrate_rising,
    )
    add(
        "growth",
        "employment strengthening",
        "the unemployment rate had fallen over 6 months into its own bottom " "quintile of changes",
        "unrate_chg_6m",
        le("unrate_chg_6m", 0.2),
    )
    add(
        "growth",
        "broad expansion",
        f"payroll growth ({fmt('payems_yoy', 0.6)}) and retail-sales growth were "
        "both above their own 60th percentiles",
        "payems_yoy",
        ge("payems_yoy", 0.6),
        ge("rsafs_yoy", 0.6),
    )
    add(
        "growth",
        "GDP accelerating",
        "real GDP YoY growth sat above its own 70th percentile (quarterly, lagged)",
        "gdpc1_yoy",
        ge("gdpc1_yoy", 0.7),
    )
    add(
        "growth",
        "GDP slowing",
        "real GDP YoY growth sat below its own 30th percentile (quarterly, lagged)",
        "gdpc1_yoy",
        le("gdpc1_yoy", 0.3),
    )
    add(
        "growth",
        "housing strengthening",
        "housing-starts YoY growth sat above its own 80th percentile",
        "houst_yoy",
        ge("houst_yoy", 0.8),
    )
    add(
        "growth",
        "housing weakening",
        "housing-starts YoY growth sat below its own 20th percentile",
        "houst_yoy",
        le("houst_yoy", 0.2),
    )

    # -- 5. risk appetite ------------------------------------------------------------------
    add(
        "risk_appetite",
        "risk-off spike",
        "the VIX sat above its 80th trailing percentile and was still rising " "over 21 sessions",
        "vix_pctile_252d",
        ResearchFilter("vix_pctile_252d", ">=", 0.8),
        ResearchFilter("vix_chg_21d", ">", 0.0),
    )
    add(
        "risk_appetite",
        "calm risk-on",
        "the VIX sat below its 20th trailing percentile during a bull market",
        "vix_pctile_252d",
        ResearchFilter("vix_pctile_252d", "<=", 0.2),
        bull,
    )
    add(
        "risk_appetite",
        "volatility crushing",
        "the 21-session VIX change sat in its own bottom quintile (fear draining)",
        "vix_chg_21d",
        le("vix_chg_21d", 0.2),
    )
    add(
        "risk_appetite",
        "volatility building",
        "the 21-session VIX change sat in its own top quintile (fear building)",
        "vix_chg_21d",
        ge("vix_chg_21d", 0.8),
    )
    add(
        "risk_appetite",
        "consumer sentiment improving",
        "consumer sentiment had risen over 6 months into its own top quintile",
        "umcsent_chg_6m",
        ge("umcsent_chg_6m", 0.8),
    )
    add(
        "risk_appetite",
        "consumer sentiment deteriorating",
        "consumer sentiment had fallen over 6 months into its own bottom quintile",
        "umcsent_chg_6m",
        le("umcsent_chg_6m", 0.2),
    )

    # -- 6. composite macro states (most conditions first) ------------------------------------
    add(
        "composite",
        "recession-like",
        "the curve was inverted while unemployment rose and the VIX sat above "
        "its 60th trailing percentile",
        "curve_slope_10y2y",
        inverted,
        unrate_rising,
        ResearchFilter("vix_pctile_252d", ">=", 0.6),
    )
    add(
        "composite",
        "soft landing",
        "CPI inflation decelerated while unemployment held steady or fell during " "a bull market",
        "cpi_yoy_accel",
        accel_down,
        unrate_easing,
        bull,
    )
    add(
        "composite",
        "risk-off environment",
        "SPY traded below its 200-session average with the VIX above its 70th "
        "trailing percentile",
        "vix_pctile_252d",
        not_bull,
        ResearchFilter("vix_pctile_252d", ">=", 0.7),
    )
    add(
        "composite",
        "risk-on environment",
        "SPY traded above its 200-session average with the VIX below its 30th "
        "trailing percentile",
        "vix_pctile_252d",
        bull,
        ResearchFilter("vix_pctile_252d", "<=", 0.3),
    )
    add(
        "composite",
        "disinflation + easing",
        "CPI inflation decelerated while the Fed Funds rate fell over 6 months",
        "cpi_yoy_accel",
        accel_down,
        ff_falling,
    )
    add(
        "composite",
        "inflation + restrictive",
        f"CPI inflation sat above its 70th percentile ({fmt('cpi_yoy', 0.7)}) "
        "with the Fed Funds rate above its 70th percentile",
        "cpi_yoy",
        ge("cpi_yoy", 0.7),
        ge("fedfunds_level", 0.7),
    )
    add(
        "composite",
        "disinflation + restrictive",
        "CPI inflation decelerated while the Fed Funds rate sat above its 70th " "percentile",
        "cpi_yoy_accel",
        accel_down,
        ge("fedfunds_level", 0.7),
    )
    add(
        "composite",
        "inflation + easing",
        "CPI inflation accelerated while the Fed Funds rate fell over 6 months",
        "cpi_yoy_accel",
        accel_up,
        ff_falling,
    )
    add(
        "composite",
        "expansion",
        "payroll growth was positive during a bull market",
        "payems_yoy",
        ResearchFilter("payems_yoy", ">", 0.0),
        bull,
    )
    add(
        "composite",
        "slowdown",
        "retail-sales growth sat below its 30th percentile while unemployment rose",
        "rsafs_yoy",
        le("rsafs_yoy", 0.3),
        unrate_rising,
    )
    return families


class MacroRegimeModel(IntelligenceModel):
    name = "macro_regime"
    version = 1

    def __init__(
        self,
        session: Session,
        half_life_years: float = 10.0,  # recency: older environments count less
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
        self._instrument_id(symbol)  # unknown symbols fail loudly
        active, resolved_as_of, spans = self._detect(as_of)

        if not any(spans.get(name, 0) >= self.min_history for name in CORE_FEATURES):
            resolved = resolved_as_of or as_of or self._latest_feature_date(symbol) or date.today()
            depth = ", ".join(f"{name}: {spans.get(name, 0)}" for name in CORE_FEATURES)
            explanation = (
                f"Insufficient macro history: no core macro feature has the "
                f"{self.min_history} stored sessions a percentile needs ({depth}). "
                "Neutral by construction."
            )
            return [
                self._neutral_score(symbol, resolved, label, sessions, (), explanation)
                for label, sessions in HORIZONS.items()
            ]
        if resolved_as_of is None:  # history exists, but not at/before this as_of
            assert as_of is not None
            explanation = (
                f"No macro features are stored at or before {as_of.isoformat()} — "
                "insufficient data to detect a macro regime. Neutral by construction."
            )
            return [
                self._neutral_score(symbol, as_of, label, sessions, (), explanation)
                for label, sessions in HORIZONS.items()
            ]
        if not active:
            explanation = (
                "No macro regime is currently active: inflation, policy, curve, "
                "growth, and risk readings are all inside their own historical "
                "thresholds. History offers no macro-driven edge either way."
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

    def _detect(self, as_of: date | None) -> tuple[list[MacroRegime], date | None, dict[str, int]]:
        """Active macro regimes (market-wide, symbol-independent) plus
        (resolved as_of, stored-history spans of the core features)."""
        cache: dict[str, pd.Series] = {}
        newest: list[date] = []  # mutable cell for the closures
        spans: dict[str, int] = {}

        def load(feature: str) -> pd.Series:
            if feature in cache:
                return cache[feature]
            definition = self._features.get_definition(feature)
            if definition is None:
                raise ConfigurationError(
                    f"feature {feature!r} is not registered; run: mip features build --all"
                )
            if definition.scope is not FeatureScope.MARKET:
                raise ConfigurationError(
                    f"macro regime conditions must be market-scope; {feature!r} is not"
                )
            series = self._features.get_market_series(definition.id)
            if as_of is not None and not series.empty:
                series = series[series.index <= pd.Timestamp(as_of)]
            if not series.empty:
                last = series.index[-1].date()
                if not newest or last > newest[0]:
                    newest[:] = [last]
            cache[feature] = series
            return series

        def latest(feature: str, _symbol: str | None) -> float | None:
            series = load(feature)
            return float(series.iloc[-1]) if not series.empty else None

        def quantile(feature: str, p: float) -> float | None:
            series = load(feature)
            spans[feature] = len(series)
            if len(series) < self.min_history:
                return None
            return float(series.quantile(p))

        for name in CORE_FEATURES:  # always measured, for honest reporting
            quantile(name, 0.5)
        active = select_active(regime_candidates(quantile), latest)
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
                f"Macro regimes are active ({', '.join(active_labels)}) but {symbol} "
                f"has fewer than {self.min_events} resolved comparable macro "
                "environments at this horizon — no score can be supported by evidence."
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
        return (
            f"{symbol} has historically {direction} in this macro environment: across "
            f"{lead.n} comparable macro episodes (≈{lead.n_eff:.0f} independent-"
            f"equivalent) where {lead.description}, the following {horizon_label} "
            f"return averaged {lead.mean * 100:+.1f}% vs a {lead.baseline_mean * 100:+.1f}% "
            f"unconditional baseline — an excess of {lead.excess * 100:+.1f}pp with a "
            f"{lead.hit_rate * 100:.0f}% hit rate. Combined across {len(evidence)} active "
            f"macro regimes, the evidence-weighted edge is {effect * 100:+.1f}pp "
            f"per {horizon_label}."
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
