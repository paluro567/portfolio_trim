"""Cross-sectional matcher and its data-access port.

The matcher discovers, across the whole instrument universe, the historical
``(symbol, date)`` observations at which a condition set held — market
conditions shared, sector/company/valuation/catalyst conditions judged against
each candidate's OWN data. Its single output is a ``HistoricalMatchSet`` (and
the paired unconditional baseline match set over the identical eligible
population). It performs NO outcome or probability computation.

Point-in-time: every series is truncated at ``as_of`` before use; own-history
percentile thresholds come from data ≤ as_of; forward outcomes (computed later,
in the outcome engine) are likewise truncated, so a match near ``as_of`` whose
horizon window would cross it simply drops out — the embargo, inherited by
construction.

Data access is confined to the ``CandidateData`` port (reservation 2): a future
evaluation target (industry ETF, peer basket) extends the port, never the
matcher. Feature series are bulk-loaded and cached once per run, so fallback
levels reuse them and the matcher never issues per-condition-per-date queries.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from mip.domain.enums import FeatureScope
from mip.domain.models import DailyPrice, Instrument
from mip.repositories.features import FeatureRepository
from mip.repositories.instruments import InstrumentRepository
from mip.research.conditions import Condition, EvaluateOn, resolve_threshold
from mip.research.engine import collapse_to_events
from mip.research.matchset import HistoricalMatchSet, observations_from
from mip.research.query import OPERATORS


class CandidateData(Protocol):
    """The matcher's only view of the database. All ``EvaluateOn`` target
    resolution happens here, so new targets extend this port, not the matcher.
    Every accessor is point-in-time: series are returned truncated at
    ``as_of``."""

    def universe(self) -> list[str]: ...

    def sector_etf(self, symbol: str) -> str | None: ...

    def feature_series(
        self, feature: str, evaluate_on: EvaluateOn, symbol: str, as_of: date
    ) -> pd.Series: ...

    def own_quantile(self, condition: Condition, symbol: str, as_of: date) -> float | None: ...

    def adj_close(self, symbol: str, as_of: date) -> pd.Series: ...


class DbCandidateData:
    """Concrete ``CandidateData`` over PostgreSQL. Caches each raw series once;
    truncation at ``as_of`` is applied per call so one cache serves every
    scoring date in a run that reuses the port."""

    def __init__(self, session: Session, min_own_history: int = 252) -> None:
        self._session = session
        self._features = FeatureRepository(session)
        self._instruments = InstrumentRepository(session)
        self._min_own_history = min_own_history
        self._series_cache: dict[tuple[str, str | None], pd.Series] = {}
        self._price_cache: dict[str, pd.Series] = {}
        self._etf_cache: dict[str, str | None] = {}
        self._instrument_id_cache: dict[str, int | None] = {}

    # -- identity ----------------------------------------------------------

    def universe(self) -> list[str]:
        return sorted(i.symbol for i in self._instruments.list_instruments())

    def sector_etf(self, symbol: str) -> str | None:
        if symbol not in self._etf_cache:
            instrument = self._instruments.get_by_symbol(symbol)
            self._etf_cache[symbol] = (
                self._instruments.sector_etf_symbol(instrument) if instrument else None
            )
        return self._etf_cache[symbol]

    def _instrument_id(self, symbol: str) -> int | None:
        if symbol not in self._instrument_id_cache:
            self._instrument_id_cache[symbol] = self._session.scalar(
                select(Instrument.id).where(Instrument.symbol == symbol)
            )
        return self._instrument_id_cache[symbol]

    # -- feature series ----------------------------------------------------

    def _raw_series(self, feature: str, symbol: str | None) -> pd.Series:
        key = (feature, symbol)
        if key not in self._series_cache:
            definition = self._features.get_definition(feature)
            if definition is None:
                self._series_cache[key] = pd.Series(dtype=float)
            elif definition.scope is FeatureScope.MARKET:
                self._series_cache[key] = self._features.get_market_series(definition.id)
            elif symbol is None:
                self._series_cache[key] = pd.Series(dtype=float)
            else:
                instrument_id = self._instrument_id(symbol)
                self._series_cache[key] = (
                    self._features.get_instrument_series(definition.id, instrument_id)
                    if instrument_id is not None
                    else pd.Series(dtype=float)
                )
        return self._series_cache[key]

    def _resolve_symbol(self, evaluate_on: EvaluateOn, symbol: str) -> str | None:
        """The instrument whose series a condition is read from — the one place
        EvaluateOn targets are mapped to concrete instruments."""
        if evaluate_on is EvaluateOn.MARKET:
            return None
        if evaluate_on is EvaluateOn.SELF:
            return symbol
        if evaluate_on is EvaluateOn.SECTOR_ETF:
            return self.sector_etf(symbol)
        raise ValueError(f"unhandled evaluate_on {evaluate_on!r}")

    def feature_series(
        self, feature: str, evaluate_on: EvaluateOn, symbol: str, as_of: date
    ) -> pd.Series:
        resolved = self._resolve_symbol(evaluate_on, symbol)
        if evaluate_on is not EvaluateOn.MARKET and resolved is None:
            return pd.Series(dtype=float)
        series = self._raw_series(feature, resolved)
        if series.empty:
            return series
        return series[series.index <= pd.Timestamp(as_of)]

    def own_quantile(self, condition: Condition, symbol: str, as_of: date) -> float | None:
        series = self.feature_series(
            condition.feature, EvaluateOn(condition.evaluate_on), symbol, as_of
        )
        min_history = condition.min_history or self._min_own_history
        if len(series) < min_history or condition.percentile is None:
            return None
        return float(series.quantile(condition.percentile))

    # -- prices ------------------------------------------------------------

    def adj_close(self, symbol: str, as_of: date) -> pd.Series:
        if symbol not in self._price_cache:
            instrument_id = self._instrument_id(symbol)
            if instrument_id is None:
                self._price_cache[symbol] = pd.Series(dtype=float)
            else:
                rows = self._session.execute(
                    select(DailyPrice.price_date, DailyPrice.adj_close)
                    .where(
                        DailyPrice.instrument_id == instrument_id,
                        DailyPrice.adj_close.is_not(None),
                    )
                    .order_by(DailyPrice.price_date)
                ).all()
                self._price_cache[symbol] = (
                    pd.Series(
                        [float(r[1]) for r in rows],
                        index=pd.DatetimeIndex(pd.to_datetime([r[0] for r in rows])),
                    )
                    if rows
                    else pd.Series(dtype=float)
                )
        series = self._price_cache[symbol]
        if series.empty:
            return series
        return series[series.index <= pd.Timestamp(as_of)]


@dataclass(frozen=True)
class MatchResult:
    """The matcher's output for one condition set: the conditional match set
    (episode-collapsed) and its unconditional baseline over the identical
    eligible population."""

    conditional: HistoricalMatchSet
    baseline: HistoricalMatchSet


class CrossSectionalMatcher:
    """Discovers pooled cross-sectional matches for a condition set. Stateless
    besides the injected data port; deterministic (sorted output)."""

    def __init__(self, data: CandidateData) -> None:
        self._data = data

    def match(
        self,
        conditions: tuple[Condition, ...],
        symbols: Sequence[str],
        as_of: date,
        label: str,
    ) -> MatchResult:
        conditional_pairs: list[tuple[str, date]] = []
        baseline_pairs: list[tuple[str, date]] = []
        for symbol in symbols:
            eligible, matching = self._symbol_masks(symbol, conditions, as_of)
            if eligible is None:
                continue
            baseline_pairs.extend((symbol, ts.date()) for ts in eligible)
            events = collapse_to_events(matching)
            conditional_pairs.extend((symbol, ts.date()) for ts in events)
        conditional = HistoricalMatchSet(
            label=label, conditions=conditions, observations=observations_from(conditional_pairs)
        )
        baseline = HistoricalMatchSet(
            label="baseline", conditions=(), observations=observations_from(baseline_pairs)
        )
        return MatchResult(conditional=conditional, baseline=baseline)

    def _symbol_masks(
        self, symbol: str, conditions: tuple[Condition, ...], as_of: date
    ) -> tuple[pd.DatetimeIndex | None, pd.Series]:
        """Eligible dates (all condition features evaluable) and the matching
        boolean over them (conjunction satisfied). Returns (None, empty) when
        the symbol cannot evaluate a required condition — excluded entirely,
        never zero-filled."""
        prices = self._data.adj_close(symbol, as_of)
        if prices.empty:
            return None, pd.Series(dtype=bool)
        index = prices.index
        evaluable = pd.Series(True, index=index)
        matching = pd.Series(True, index=index)

        def own_quantile(condition: Condition, sym: str) -> float | None:
            return self._data.own_quantile(condition, sym, as_of)

        for condition in conditions:
            threshold = resolve_threshold(condition, symbol, own_quantile)
            if threshold is None:
                return None, pd.Series(dtype=bool)
            series = self._data.feature_series(
                condition.feature, EvaluateOn(condition.evaluate_on), symbol, as_of
            ).reindex(index)
            evaluable &= series.notna()
            matching &= OPERATORS[condition.op](series, threshold)
        mask = evaluable.to_numpy()
        return index[mask], matching[mask]
