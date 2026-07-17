"""Earnings Behavior Intelligence Model.

Question answered: given everything known immediately AFTER an earnings
event — the surprise, the initial reaction, the trend and volatility the
stock carried into the report, and the market environment — how has this
stock historically behaved over each forward horizon?

The model measures post-earnings behavior; it never predicts earnings and
never uses information unavailable at the evaluation date. Every regime is
anchored to the post-report window (days_since_earnings <= EVENT_WINDOW
calendar days), so historical studies collapse to one episode per earnings
event — genuine event studies over the stock's own reporting history.
Whether beats continue or fade, and whether misses recover or keep selling,
is decided per stock by its own evidence, never by heuristics.

Data notes (documented, not hidden):
- Guidance does not exist in the platform schema: the guidance family is an
  explicit empty placeholder until a provider supplies it (honest absence,
  never a guess).
- Implied volatility does not exist: realized vol_21d percentiles stand in.
- Gaps use the daily raw open vs the prior raw close (gap_1d); BMO/AMC
  timing means the initial reaction is captured within the anchor window
  rather than at one exact session.
- Outside the post-report window the model is deliberately neutral: its
  question is only defined immediately after a report.

Aggregation is the shared hardened framework (models.base): one active
regime per family (most specific first), Bartlett-kernel within-study SE
inflation, correlated cross-regime combination (every family conditions on
the SAME report days, so cross-study correlation is high and is measured,
never assumed away), agreement-based confidence, saturation diagnostics.
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
EVENT_WINDOW_DAYS = 14.0  # calendar days after a report that count as "post-earnings"
MIN_PERCENTILE_OBS = 252  # a year of stored history before a percentile is meaningful

FAMILIES = (
    "surprise",
    "guidance",  # placeholder: no guidance data exists in the platform yet
    "reaction",
    "trend_into_report",
    "volatility",
    "market_env",
)


@dataclass(frozen=True)
class EarningsRegime:
    """One candidate condition. `family` scopes the no-double-counting rule:
    at most one regime per family may be active at a time."""

    family: str
    label: str  # stable, short: 'large beat'
    description: str  # prose with the actual threshold values
    feature: str  # primary feature, for RegimeEvidence
    filters: tuple[ResearchFilter, ...]


def regime_candidates(
    symbol: str,
    etf: str | None,
    quantile,  # Callable[[str, float], float | None]: the stock's own percentile value
) -> dict[str, list[EarningsRegime]]:
    """All candidate regimes keyed by family, MOST SPECIFIC FIRST within
    each family. Every candidate carries the post-report anchor
    (days_since_earnings <= EVENT_WINDOW_DAYS); surprise-sign conditions
    need no percentile history, magnitude conditions do. The guidance
    family is deliberately empty until guidance data exists."""
    families: dict[str, list[EarningsRegime]] = {name: [] for name in FAMILIES}
    anchor = ResearchFilter("days_since_earnings", "<=", EVENT_WINDOW_DAYS)
    beat = ResearchFilter("eps_surprise", ">", 0.0)
    miss = ResearchFilter("eps_surprise", "<", 0.0)

    def add(family: str, label: str, description: str, feature: str, *filters) -> None:
        if all(f is not None for f in filters):
            families[family].append(
                EarningsRegime(family, label, description, feature, (anchor, *filters))
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

    # -- 1. earnings surprise ---------------------------------------------------
    add(
        "surprise",
        "large beat",
        f"{symbol} reported an EPS beat in its own top quintile of surprises "
        f"(≥ {fmt('eps_surprise', 0.8)})",
        "eps_surprise",
        ge("eps_surprise", 0.8),
        beat,
    )
    add(
        "surprise",
        "large miss",
        f"{symbol} reported an EPS miss in its own bottom quintile of surprises "
        f"(≤ {fmt('eps_surprise', 0.2)})",
        "eps_surprise",
        le("eps_surprise", 0.2),
        miss,
    )
    add(
        "surprise",
        "moderate beat",
        f"{symbol} reported EPS above estimates",
        "eps_surprise",
        beat,
    )
    add(
        "surprise",
        "moderate miss",
        f"{symbol} reported EPS below estimates",
        "eps_surprise",
        miss,
    )
    add(
        "surprise",
        "inline report",
        f"{symbol} reported EPS near estimates (its own middle surprise band)",
        "eps_surprise",
        ge("eps_surprise", 0.3),
        le("eps_surprise", 0.7),
    )

    # -- 2. guidance: no data exists — framework placeholder, honest absence -----

    # -- 3. initial market reaction ------------------------------------------------
    add(
        "reaction",
        "gap up on report",
        f"{symbol} gapped up into its own top decile of overnight gaps "
        f"(≥ {fmt('gap_1d', 0.9)}) after reporting",
        "gap_1d",
        ge("gap_1d", 0.9),
    )
    add(
        "reaction",
        "gap down on report",
        f"{symbol} gapped down into its own bottom decile of overnight gaps "
        f"(≤ {fmt('gap_1d', 0.1)}) after reporting",
        "gap_1d",
        le("gap_1d", 0.1),
    )
    add(
        "reaction",
        "rally after report",
        f"{symbol}'s 5-session return after reporting sat in its own top quintile "
        f"(≥ {fmt('ret_5d', 0.8)})",
        "ret_5d",
        ge("ret_5d", 0.8),
    )
    add(
        "reaction",
        "selloff after report",
        f"{symbol}'s 5-session return after reporting sat in its own bottom quintile "
        f"(≤ {fmt('ret_5d', 0.2)})",
        "ret_5d",
        le("ret_5d", 0.2),
    )
    add(
        "reaction",
        "flat after report",
        f"{symbol}'s 5-session return after reporting sat in its own middle band",
        "ret_5d",
        ge("ret_5d", 0.4),
        le("ret_5d", 0.6),
    )

    # -- 4. trend entering earnings ---------------------------------------------------
    add(
        "trend_into_report",
        "reported near 52w highs",
        f"{symbol} was closer to its 52-week high than 80% of its own history " "around the report",
        "dist_52w_high",
        ge("dist_52w_high", 0.8),
    )
    add(
        "trend_into_report",
        "reported near 52w lows",
        f"{symbol} was deeper below its 52-week high than 80% of its own history "
        "around the report",
        "dist_52w_high",
        le("dist_52w_high", 0.2),
    )
    add(
        "trend_into_report",
        "extended trend into report",
        f"{symbol} carried a 63-session return in its own top quintile "
        f"(≥ {fmt('ret_63d', 0.8)}) into the report",
        "ret_63d",
        ge("ret_63d", 0.8),
    )
    add(
        "trend_into_report",
        "weak trend into report",
        f"{symbol} carried a 63-session return in its own bottom quintile "
        f"(≤ {fmt('ret_63d', 0.2)}) into the report",
        "ret_63d",
        le("ret_63d", 0.2),
    )

    # -- 5. volatility (realized; implied does not exist in the platform) ---------------
    add(
        "volatility",
        "high volatility report",
        f"{symbol}'s realized 21-session volatility sat in its own top quintile "
        "around the report",
        "vol_21d",
        ge("vol_21d", 0.8),
    )
    add(
        "volatility",
        "low volatility report",
        f"{symbol}'s realized 21-session volatility sat in its own bottom quintile "
        "around the report",
        "vol_21d",
        le("vol_21d", 0.2),
    )

    # -- 6. market environment (reuses rates/sector/market regime features) --------------
    if etf is not None:
        add(
            "market_env",
            f"beat, {etf} leading",
            f"{symbol} beat estimates while its sector ETF {etf} led SPY over 63 sessions",
            "eps_surprise",
            beat,
            ResearchFilter("rel_ret_spy_63d", ">", 0.0, symbol=etf),
        )
    add(
        "market_env",
        "beat in bull market",
        f"{symbol} beat estimates while SPY traded above its 200-session average",
        "eps_surprise",
        beat,
        ResearchFilter("regime_bull", "==", 1.0),
    )
    add(
        "market_env",
        "miss in bull market",
        f"{symbol} missed estimates while SPY traded above its 200-session average",
        "eps_surprise",
        miss,
        ResearchFilter("regime_bull", "==", 1.0),
    )
    add(
        "market_env",
        "beat, rising rates",
        f"{symbol} beat estimates while the 10Y yield had risen more than 25 bps "
        "over 63 sessions",
        "eps_surprise",
        beat,
        ResearchFilter("regime_rising_rates", "==", 1.0),
    )
    add(
        "market_env",
        "miss in high-vol market",
        f"{symbol} missed estimates during a high-volatility market (VIX above 25)",
        "eps_surprise",
        miss,
        ResearchFilter("regime_high_vol", "==", 1.0),
    )
    return families


class EarningsBehaviorModel(IntelligenceModel):
    name = "earnings_behavior"
    version = 1

    def __init__(
        self,
        session: Session,
        half_life_years: float = 10.0,  # recency: older reports count less
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
        active, resolved_as_of, days_since = self._detect(symbol, etf, as_of)

        if days_since is None:
            resolved = resolved_as_of or as_of or self._latest_feature_date(symbol) or date.today()
            explanation = (
                f"No reported earnings history is stored for {symbol} — post-earnings "
                "behavior cannot be measured. Neutral by construction."
            )
            return [
                self._neutral_score(symbol, resolved, label, sessions, (), explanation)
                for label, sessions in HORIZONS.items()
            ]
        if resolved_as_of is None:  # history exists, but not at/before this as_of
            assert as_of is not None
            explanation = (
                f"No earnings features are stored at or before {as_of.isoformat()} for "
                f"{symbol} — insufficient data. Neutral by construction."
            )
            return [
                self._neutral_score(symbol, as_of, label, sessions, (), explanation)
                for label, sessions in HORIZONS.items()
            ]
        if days_since > EVENT_WINDOW_DAYS:
            explanation = (
                f"{symbol} last reported {days_since:.0f} calendar days ago — outside the "
                f"{EVENT_WINDOW_DAYS:.0f}-day post-earnings window this model measures. "
                "The model answers only what has historically followed reports; "
                "neutral between them by construction."
            )
            return [
                self._neutral_score(symbol, resolved_as_of, label, sessions, (), explanation)
                for label, sessions in HORIZONS.items()
            ]
        if not active:
            explanation = (
                f"{symbol} reported within the last {EVENT_WINDOW_DAYS:.0f} days but no "
                "earnings regime is active: the surprise, reaction, trend, and "
                "volatility readings are all inside their own historical thresholds."
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
    ) -> tuple[list[EarningsRegime], date | None, float | None]:
        """Active regimes plus (resolved as_of, current days-since-earnings).
        days_since None = no reported-earnings history stored at all."""
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

        days_since = latest("days_since_earnings", None)
        active = select_active(regime_candidates(symbol, etf, quantile), latest)
        return active, (as_of or (newest[0] if newest else None)), days_since

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
                f"Earnings regimes are active ({', '.join(active_labels)}) but {symbol} "
                f"has fewer than {self.min_events} resolved comparable earnings events "
                "at this horizon — no score can be supported by evidence."
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
        direction = "continued higher" if lead.excess > 0 else "underperformed"
        return (
            f"{symbol} has historically {direction} in this setup: across {lead.n} "
            f"comparable earnings events (≈{lead.n_eff:.0f} independent-equivalent) "
            f"where {lead.description}, the following {horizon_label} return averaged "
            f"{lead.mean * 100:+.1f}% vs a {lead.baseline_mean * 100:+.1f}% unconditional "
            f"baseline — an excess of {lead.excess * 100:+.1f}pp with a "
            f"{lead.hit_rate * 100:.0f}% hit rate. Combined across {len(evidence)} active "
            f"earnings regimes, the evidence-weighted edge is {effect * 100:+.1f}pp "
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
