"""Conditional Probability Engine — the Outcome + Probability layer.

Consumes ``HistoricalMatchSet``s from the cross-sectional matcher and produces,
per horizon, the conditional forward-outcome distributions (absolute,
SPY-relative, sector-relative), path risk, and the PRIMARY effect
(conditional mean − unconditional baseline mean) with an effective-sample
standard error. It walks the disclosed, versioned fallback ladder and emits
per-condition leave-one-out ``ConditionContribution`` diagnostics.

Everything statistical lives here in the research layer (the payoff of 6a): the
model layer above only maps ``effect``/``effect_se``/``effective`` onto the
NormalizedEvidence contract. Nothing here computes a score, a label, or touches
the decision pipeline. Point-in-time correctness is inherited from the matcher
and the port (all prices truncated at ``as_of``); this module adds no data
access of its own beyond the shared port.
"""

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from mip.core.exceptions import ConfigurationError
from mip.research.analogues import HORIZONS  # single source of the horizon vocabulary
from mip.research.conditions import (
    TEMPLATE_SET_VERSION,
    Condition,
    EvaluateOn,
    ResolutionContext,
    build_condition_templates,
    resolve_active,
)
from mip.research.matching import CandidateData, CrossSectionalMatcher, DbCandidateData
from mip.research.matchset import HistoricalMatchSet
from mip.research.outcomes import (
    IndependenceProfile,
    OutcomeDistribution,
    build_distribution,
    exceedance_probability,
    independence_profile,
    path_excursions,
)
from mip.research.statistics import EffectiveSample, WeightedSample

# Company-domain group: valuation conditions strengthen the company domain in
# the ladder (kept a distinct declared family for explainability).
FAMILY_GROUPS: dict[str, tuple[str, ...]] = {
    "market": ("market",),
    "sector": ("sector",),
    "company": ("company", "valuation"),
    "catalyst": ("catalyst",),
}

# Fallback ladder in required-family terms (mirrors conditions.FALLBACK_LADDER
# but expressed against the groups above). Descended in order; the first rung
# whose conditional match set clears the support thresholds is used.
LADDER: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("market+sector+company+catalyst", ("market", "sector", "company", "catalyst")),
    ("market+sector+company", ("market", "sector", "company")),
    ("market+company+catalyst", ("market", "company", "catalyst")),
    ("market+company", ("market", "company")),
    ("market+sector", ("market", "sector")),
    ("market", ("market",)),
)


@dataclass(frozen=True)
class ConditionalConfig:
    """Support thresholds (the ladder-descent gate) and reporting knobs. All
    declared before validation; none tuned on test data."""

    min_raw_matches: int = 40
    min_episodes: int = 12
    min_distinct_years: int = 3
    max_symbol_concentration: float = 0.5
    max_year_concentration: float = 0.6
    positive_threshold: float = 0.05
    negative_threshold: float = -0.05
    min_own_history: int = 252
    focus_horizon: str = "1m"
    # Leave-one-condition-out contributions are DIAGNOSTIC only (context, never
    # the score) and cost one extra full match per condition, so they are off in
    # the decision hot path and turned on for CLI/report deep dives.
    compute_contributions: bool = False


@dataclass(frozen=True)
class ConditionContribution:
    """Diagnostic-only leave-one-out contribution of one condition. NOT
    additional evidence: the decision engine still consumes exactly one effect
    per horizon. Deltas are marginal (conditions interact) — they do not sum to
    the effect, and must never be presented as an exact decomposition."""

    condition: str
    family: str
    delta_effect: float | None  # effect(full) - effect(without this condition)
    delta_effective: float | None  # effective sample change when removed
    n_with: int
    n_without: int

    def to_dict(self) -> dict:
        return {
            "condition": self.condition,
            "family": self.family,
            "delta_effect": self.delta_effect,
            "delta_effective": self.delta_effective,
            "n_with": self.n_with,
            "n_without": self.n_without,
        }


@dataclass(frozen=True)
class HorizonOutcome:
    """Full conditional-vs-baseline outcome summary for one horizon."""

    horizon: str
    sessions: int
    independence: IndependenceProfile
    effective: EffectiveSample
    absolute: OutcomeDistribution
    spy_relative: OutcomeDistribution | None
    sector_relative: OutcomeDistribution | None
    baseline_absolute: OutcomeDistribution
    baseline_spy_relative: OutcomeDistribution | None
    effect: float | None  # conditional mean − baseline mean (PRIMARY statistic)
    effect_se: float | None
    p_exceed_up: float | None
    p_exceed_down: float | None
    median_mdd: float | None
    median_mae: float | None
    median_mfe: float | None
    delta_p_positive: float | None
    delta_p_beat_spy: float | None
    first_date: date | None
    last_date: date | None

    def to_dict(self) -> dict:
        return {
            "horizon": self.horizon,
            "sessions": self.sessions,
            "independence": self.independence.to_dict(),
            "effective": self.effective.to_dict(),
            "absolute": self.absolute.to_dict(),
            "spy_relative": self.spy_relative.to_dict() if self.spy_relative else None,
            "sector_relative": self.sector_relative.to_dict() if self.sector_relative else None,
            "baseline_absolute": self.baseline_absolute.to_dict(),
            "baseline_spy_relative": (
                self.baseline_spy_relative.to_dict() if self.baseline_spy_relative else None
            ),
            "effect": self.effect,
            "effect_se": self.effect_se,
            "p_exceed_up": self.p_exceed_up,
            "p_exceed_down": self.p_exceed_down,
            "median_mdd": self.median_mdd,
            "median_mae": self.median_mae,
            "median_mfe": self.median_mfe,
            "delta_p_positive": self.delta_p_positive,
            "delta_p_beat_spy": self.delta_p_beat_spy,
            "first_date": self.first_date.isoformat() if self.first_date else None,
            "last_date": self.last_date.isoformat() if self.last_date else None,
        }


@dataclass(frozen=True)
class ConditionalResult:
    """The engine's output for one symbol: the resolved conjunction, the
    fallback level used and what was dropped, per-horizon outcomes, and the
    per-condition diagnostics. ``insufficient`` set (with empty outcomes) when
    even market-only lacks support."""

    symbol: str
    as_of: date
    template_set_version: str
    engine_version: int
    active_conditions: tuple[Condition, ...]
    fallback_level: str
    dropped_conditions: tuple[str, ...]
    outcomes: dict[str, HorizonOutcome]
    contributions: dict[str, tuple[ConditionContribution, ...]]  # keyed by horizon
    insufficient: str | None = None

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "as_of": self.as_of.isoformat(),
            "template_set_version": self.template_set_version,
            "engine_version": self.engine_version,
            "active_conditions": [c.to_dict() for c in self.active_conditions],
            "fallback_level": self.fallback_level,
            "dropped_conditions": list(self.dropped_conditions),
            "outcomes": {h: o.to_dict() for h, o in self.outcomes.items()},
            "contributions": {h: [c.to_dict() for c in cs] for h, cs in self.contributions.items()},
            "insufficient": self.insufficient,
        }


ENGINE_VERSION = 1


def _shared_port(session: Session, min_own_history: int) -> DbCandidateData:
    """One DbCandidateData per SQLAlchemy session, cached on ``session.info``.
    The cross-sectional matcher loads the whole universe's prices and features;
    sharing the port lets every target symbol in a decision/report run reuse
    that bulk-loaded, PIT-cached data instead of reloading it per symbol. Data
    is read-only within a run, and the cache dies with the session."""
    port = session.info.get("cpe_candidate_data")
    if port is None:
        port = DbCandidateData(session, min_own_history=min_own_history)
        session.info["cpe_candidate_data"] = port
    return port


class ConditionalEngine:
    """Drives resolution → matching → outcome/probability for one symbol.
    Reads only through the CandidateData port (bulk-cached per run)."""

    def __init__(
        self,
        session: Session,
        config: ConditionalConfig | None = None,
        data: CandidateData | None = None,
    ) -> None:
        self._config = config or ConditionalConfig()
        self._data = data or _shared_port(session, self._config.min_own_history)
        self._matcher = CrossSectionalMatcher(self._data)
        self._templates = build_condition_templates()
        self._fwd_cache: dict[tuple[str, int], pd.Series] = {}

    # -- public ------------------------------------------------------------

    def evaluate(self, symbol: str, as_of: date | None = None) -> ConditionalResult:
        symbol = symbol.strip().upper()
        resolved_as_of = self._resolve_as_of(symbol, as_of)
        ctx = self._resolution_context(symbol, resolved_as_of)
        active_by_family = resolve_active(self._templates, ctx)
        active_conditions = tuple(c for cs in active_by_family.values() for c in cs)
        universe = self._data.universe()

        chosen = self._descend_ladder(active_by_family, universe, resolved_as_of)
        if chosen is None:
            return ConditionalResult(
                symbol=symbol,
                as_of=resolved_as_of,
                template_set_version=TEMPLATE_SET_VERSION,
                engine_version=ENGINE_VERSION,
                active_conditions=active_conditions,
                fallback_level="insufficient",
                dropped_conditions=(),
                outcomes={},
                contributions={},
                insufficient="no rung of the fallback ladder cleared the support thresholds",
            )
        level, conditions, result, dropped = chosen
        outcomes: dict[str, HorizonOutcome] = {}
        contributions: dict[str, tuple[ConditionContribution, ...]] = {}
        for label, sessions in HORIZONS.items():
            outcomes[label] = self._horizon_outcome(
                result.conditional, result.baseline, sessions, resolved_as_of
            )
        focus = self._config.focus_horizon
        if self._config.compute_contributions:
            contributions[focus] = self._contributions(
                conditions, universe, resolved_as_of, HORIZONS[focus], outcomes[focus].effect
            )
        return ConditionalResult(
            symbol=symbol,
            as_of=resolved_as_of,
            template_set_version=TEMPLATE_SET_VERSION,
            engine_version=ENGINE_VERSION,
            active_conditions=active_conditions,
            fallback_level=level,
            dropped_conditions=dropped,
            outcomes=outcomes,
            contributions=contributions,
        )

    # -- resolution --------------------------------------------------------

    def _resolve_as_of(self, symbol: str, as_of: date | None) -> date:
        prices = self._data.adj_close(symbol, as_of or date(2999, 1, 1))
        if prices.empty:
            raise ConfigurationError(f"no prices stored for {symbol!r}")
        return prices.index[-1].date()

    def _resolution_context(self, symbol: str, as_of: date) -> ResolutionContext:
        def value(feature: str, evaluate_on: EvaluateOn) -> float | None:
            series = self._data.feature_series(feature, evaluate_on, symbol, as_of)
            return float(series.iloc[-1]) if not series.empty else None

        def quantile(feature: str, evaluate_on: EvaluateOn, p: float) -> float | None:
            series = self._data.feature_series(feature, evaluate_on, symbol, as_of)
            if len(series) < self._config.min_own_history:
                return None
            return float(series.quantile(p))

        return ResolutionContext(
            target=symbol,
            as_of=as_of,
            sector_etf=self._data.sector_etf(symbol),
            value=value,
            quantile=quantile,
        )

    # -- ladder ------------------------------------------------------------

    def _gather(
        self, active_by_family: dict[str, list[Condition]], families: tuple[str, ...]
    ) -> tuple[Condition, ...] | None:
        """Conditions for one ladder rung, or None if a required family group
        has no active condition (that rung cannot form)."""
        conditions: list[Condition] = []
        for required in families:
            group = FAMILY_GROUPS[required]
            present = [c for fam in group for c in active_by_family.get(fam, [])]
            if not present:
                return None
            conditions.extend(present)
        return tuple(conditions)

    def _descend_ladder(
        self,
        active_by_family: dict[str, list[Condition]],
        universe: list[str],
        as_of: date,
    ):
        focus_sessions = HORIZONS[self._config.focus_horizon]
        all_active = {c.name for cs in active_by_family.values() for c in cs}
        for level, families in LADDER:
            conditions = self._gather(active_by_family, families)
            if conditions is None:
                continue
            result = self._matcher.match(conditions, universe, as_of, level)
            profile = independence_profile(
                result.conditional.symbols, result.conditional.dates, focus_sessions
            )
            if self._supported(profile):
                used = {c.name for c in conditions}
                dropped = tuple(sorted(all_active - used))
                return level, conditions, result, dropped
        return None

    def _supported(self, profile: IndependenceProfile) -> bool:
        cfg = self._config
        return (
            profile.raw_matches >= cfg.min_raw_matches
            and profile.distinct_calendar_episodes >= cfg.min_episodes
            and profile.distinct_years >= cfg.min_distinct_years
            and profile.symbol_concentration <= cfg.max_symbol_concentration
            and profile.year_concentration <= cfg.max_year_concentration
        )

    # -- outcomes ----------------------------------------------------------

    def _forward_series(self, symbol: str, sessions: int, as_of: date) -> pd.Series:
        key = (symbol, sessions)
        if key not in self._fwd_cache:
            prices = self._data.adj_close(symbol, as_of)
            values = prices.to_numpy()
            fwd = np.full(len(values), np.nan)
            if len(values) > sessions:
                fwd[:-sessions] = values[sessions:] / values[:-sessions] - 1.0
            self._fwd_cache[key] = pd.Series(fwd, index=prices.index)
        return self._fwd_cache[key]

    def _pooled_returns(
        self, match_set: HistoricalMatchSet, sessions: int, as_of: date, want_path: bool
    ) -> dict:
        """Pool per-symbol forward returns aligned to matched dates. Returns
        arrays for absolute / SPY-relative / sector-relative returns plus, when
        requested, path excursions — all masked to observable (non-NaN) events,
        with aligned symbols/dates."""
        by_symbol: dict[str, list[date]] = {}
        for obs in match_set.observations:
            by_symbol.setdefault(obs.symbol, []).append(obs.date)
        abs_parts: list[np.ndarray] = []
        spy_parts: list[np.ndarray] = []
        sec_parts: list[np.ndarray] = []
        symbols: list[str] = []
        dates: list[date] = []
        mdd: list[float] = []
        mae: list[float] = []
        mfe: list[float] = []
        spy_fwd = self._forward_series("SPY", sessions, as_of)
        for symbol, sym_dates in by_symbol.items():
            idx = pd.DatetimeIndex(sorted(pd.Timestamp(d) for d in sym_dates))
            own = self._forward_series(symbol, sessions, as_of).reindex(idx).to_numpy()
            valid = ~np.isnan(own)
            if not valid.any():
                continue
            vidx = idx[valid]
            own_v = own[valid]
            spy_v = spy_fwd.reindex(vidx).to_numpy()
            etf = self._data.sector_etf(symbol)
            sec_v = (
                self._forward_series(etf, sessions, as_of).reindex(vidx).to_numpy()
                if etf
                else np.full(len(vidx), np.nan)
            )
            abs_parts.append(own_v)
            spy_parts.append(own_v - spy_v)  # NaN where SPY forward is unavailable
            sec_parts.append(own_v - sec_v)
            symbols.extend([symbol] * len(vidx))
            dates.extend(ts.date() for ts in vidx)
            if want_path:
                prices = self._data.adj_close(symbol, as_of)
                price_values = prices.to_numpy()
                pos_map = {ts: i for i, ts in enumerate(prices.index)}
                for ts in vidx:
                    pos = pos_map.get(ts)
                    if pos is not None:
                        d, a, f = path_excursions(price_values[pos : pos + sessions + 1])
                        mdd.append(d)
                        mae.append(a)
                        mfe.append(f)
        empty = np.array([], dtype=float)
        return {
            "absolute": np.concatenate(abs_parts) if abs_parts else empty,
            "spy_relative": np.concatenate(spy_parts) if spy_parts else empty,
            "sector_relative": np.concatenate(sec_parts) if sec_parts else empty,
            "symbols": symbols,
            "dates": dates,
            "mdd": np.array(mdd),
            "mae": np.array(mae),
            "mfe": np.array(mfe),
        }

    def _distribution(self, measure: str, values: np.ndarray, dates, sessions: int):
        valid = ~np.isnan(values)
        sample = WeightedSample.uniform(values[valid])
        kept_dates = [d for d, ok in zip(dates, valid, strict=True) if ok]
        return build_distribution(measure, sample, kept_dates, sessions), sample, kept_dates

    def _horizon_outcome(
        self,
        conditional: HistoricalMatchSet,
        baseline: HistoricalMatchSet,
        sessions: int,
        as_of: date,
    ) -> HorizonOutcome:
        cond = self._pooled_returns(conditional, sessions, as_of, want_path=True)
        base = self._pooled_returns(baseline, sessions, as_of, want_path=False)

        absolute, abs_sample, abs_dates = self._distribution(
            "absolute", cond["absolute"], cond["dates"], sessions
        )
        spy_rel = self._distribution("spy_relative", cond["spy_relative"], cond["dates"], sessions)[
            0
        ]
        sector_rel = self._distribution(
            "sector_relative", cond["sector_relative"], cond["dates"], sessions
        )[0]
        baseline_abs = self._distribution("absolute", base["absolute"], base["dates"], sessions)[0]
        baseline_spy = self._distribution(
            "spy_relative", base["spy_relative"], base["dates"], sessions
        )[0]

        independence = independence_profile(cond["symbols"], abs_dates, sessions)
        effective = absolute.effective
        effect = (
            absolute.mean - baseline_abs.mean
            if None not in (absolute.mean, baseline_abs.mean)
            else None
        )
        effect_se = (
            absolute.dispersion / np.sqrt(effective.effective)
            if absolute.dispersion is not None and effective.effective > 0
            else None
        )
        p_up = exceedance_probability(abs_sample, self._config.positive_threshold, above=True)
        p_down = exceedance_probability(abs_sample, self._config.negative_threshold, above=False)
        return HorizonOutcome(
            horizon=_label_for(sessions),
            sessions=sessions,
            independence=independence,
            effective=effective,
            absolute=absolute,
            spy_relative=spy_rel,
            sector_relative=sector_rel,
            baseline_absolute=baseline_abs,
            baseline_spy_relative=baseline_spy,
            effect=effect,
            effect_se=(float(effect_se) if effect_se is not None else None),
            p_exceed_up=p_up,
            p_exceed_down=p_down,
            median_mdd=float(np.median(cond["mdd"])) if cond["mdd"].size else None,
            median_mae=float(np.median(cond["mae"])) if cond["mae"].size else None,
            median_mfe=float(np.median(cond["mfe"])) if cond["mfe"].size else None,
            delta_p_positive=(
                absolute.p_positive - baseline_abs.p_positive
                if None not in (absolute.p_positive, baseline_abs.p_positive)
                else None
            ),
            delta_p_beat_spy=(
                spy_rel.p_positive - baseline_spy.p_positive
                if None not in (spy_rel.p_positive, baseline_spy.p_positive)
                else None
            ),
            first_date=min(abs_dates) if abs_dates else None,
            last_date=max(abs_dates) if abs_dates else None,
        )

    # -- leave-one-condition-out diagnostics -------------------------------

    def _contributions(
        self,
        conditions: tuple[Condition, ...],
        universe: list[str],
        as_of: date,
        sessions: int,
        full_effect: float | None,
    ) -> tuple[ConditionContribution, ...]:
        if len(conditions) <= 1 or full_effect is None:
            return ()
        full_n = len(self._matcher.match(conditions, universe, as_of, "full").conditional)
        contributions: list[ConditionContribution] = []
        for condition in conditions:
            reduced = tuple(c for c in conditions if c.name != condition.name)
            result = self._matcher.match(reduced, universe, as_of, "loo")
            outcome = self._horizon_outcome(result.conditional, result.baseline, sessions, as_of)
            delta_effect = full_effect - outcome.effect if outcome.effect is not None else None
            contributions.append(
                ConditionContribution(
                    condition=condition.name,
                    family=condition.family,
                    delta_effect=delta_effect,
                    delta_effective=None,  # reserved; filled by a later phase
                    n_with=full_n,
                    n_without=len(result.conditional),
                )
            )
        contributions.sort(key=lambda c: -(abs(c.delta_effect) if c.delta_effect else 0.0))
        return tuple(contributions)


def _label_for(sessions: int) -> str:
    for label, s in HORIZONS.items():
        if s == sessions:
            return label
    return f"{sessions}d"
