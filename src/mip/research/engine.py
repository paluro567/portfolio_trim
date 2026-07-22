"""The Historical Research Engine: conditional forward-return studies.

Reads ONLY PostgreSQL — feature stores + daily_prices — never providers
(architecture: research is the PIT gatekeeper). Point-in-time safety is
inherited from the feature store: a feature row exists at feature_date
only if its inputs were public by then (publication lags applied at build
time, Phase 5). The engine therefore never touches obs_date-keyed data.

Sample semantics:
- A day is ELIGIBLE when the target has a price and every filter feature
  has a stored value (absent = not evaluable = excluded, never zero).
- mode=events collapses consecutive matching days to the first day of
  each episode (independent samples); mode=all keeps every matching day
  (overlapping forward windows — larger n, autocorrelated).
- Forward returns use adjusted close, horizon counted in trading sessions,
  and may resolve past the query window's end.
"""

from dataclasses import dataclass
from datetime import date

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from mip.core.exceptions import ConfigurationError
from mip.domain.enums import FeatureScope
from mip.domain.models import DailyPrice, Instrument
from mip.repositories.features import FeatureRepository
from mip.research.metrics import ResearchMetric, summarize
from mip.research.query import OPERATORS, ResearchFilter, ResearchQuery, SampleMode


@dataclass(frozen=True)
class ResearchResult:
    query: ResearchQuery
    event_dates: tuple[date, ...]
    eligible_days: int
    metrics: dict[int, ResearchMetric]  # conditional, keyed by horizon
    baseline: dict[int, ResearchMetric]  # unconditional over all eligible days
    forward_returns: pd.DataFrame  # index=event date, one fwd_{h}d column per horizon

    def to_dict(self) -> dict:
        return {
            "query": {
                "symbol": self.query.symbol,
                "filters": [f.describe() for f in self.query.filters],
                "window": {
                    "start": (
                        self.query.window.start.isoformat() if self.query.window.start else None
                    ),
                    "end": self.query.window.end.isoformat() if self.query.window.end else None,
                },
                "horizons": list(self.query.horizons),
                "mode": self.query.mode.value,
            },
            "eligible_days": self.eligible_days,
            "sample_size": len(self.event_dates),
            "event_dates": [d.isoformat() for d in self.event_dates],
            "metrics": {h: m.to_dict() for h, m in self.metrics.items()},
            "baseline": {h: m.to_dict() for h, m in self.baseline.items()},
        }


def collapse_to_events(matching: pd.Series) -> pd.DatetimeIndex:
    """First day of each matching episode: a matching day whose previous
    ELIGIBLE day (previous row) did not match."""
    starts = matching & ~matching.shift(1, fill_value=False)
    return pd.DatetimeIndex(matching.index[starts])


def forward_returns(
    prices: pd.Series, events: pd.DatetimeIndex, horizons: tuple[int, ...]
) -> pd.DataFrame:
    """adj_close[t+h]/adj_close[t] - 1 per event, horizon in sessions.
    Events too close to the end of history get NaN (dropped per-horizon
    by summarize — sample sizes shrink honestly at long horizons)."""
    positions = prices.index.get_indexer(events)
    frame = pd.DataFrame(index=events)
    values = prices.to_numpy()
    for horizon in horizons:
        column = []
        for pos in positions:
            target = pos + horizon
            column.append(
                values[target] / values[pos] - 1.0 if target < len(values) else float("nan")
            )
        frame[f"fwd_{horizon}d"] = column
    return frame


class ResearchEngine:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._features = FeatureRepository(session)

    def run(self, query: ResearchQuery) -> ResearchResult:
        prices = self._load_adj_close(query.symbol)
        if query.window.end is not None:
            # PIT alignment: forward outcomes may use only prices observable
            # by the window end — evaluate(as_of=T) must equal what live
            # inference produced on T (windows crossing T yield NaN and
            # shrink samples honestly, exactly as they do live).
            prices = prices.loc[: pd.Timestamp(query.window.end)]
        if prices.empty:
            raise ConfigurationError(f"no prices stored for {query.symbol!r}")

        # eligible = price days inside the window where every filter is evaluable
        eligible = prices.index
        window = query.window
        if window.start is not None:
            eligible = eligible[eligible >= pd.Timestamp(window.start)]
        if window.end is not None:
            eligible = eligible[eligible <= pd.Timestamp(window.end)]

        evaluable = pd.Series(True, index=eligible)
        matching = pd.Series(True, index=eligible)
        for research_filter in query.filters:
            series = self._filter_series(research_filter, query.symbol).reindex(eligible)
            compare = OPERATORS[research_filter.op]
            evaluable &= series.notna()
            matching &= compare(series, research_filter.value)
        # a day where any filter is not evaluable is excluded entirely:
        # it is neither a sample nor a baseline day (absent, never zero)
        eligible = eligible[evaluable.to_numpy()]
        matching = matching[evaluable.to_numpy()]

        if query.mode is SampleMode.EVENTS:
            events = collapse_to_events(matching)
        else:
            events = pd.DatetimeIndex(matching.index[matching])

        event_frame = forward_returns(prices, events, query.horizons)
        baseline_frame = forward_returns(prices, pd.DatetimeIndex(eligible), query.horizons)

        return ResearchResult(
            query=query,
            event_dates=tuple(ts.date() for ts in events),
            eligible_days=len(eligible),
            metrics={h: summarize(h, event_frame[f"fwd_{h}d"]) for h in query.horizons},
            baseline={h: summarize(h, baseline_frame[f"fwd_{h}d"]) for h in query.horizons},
            forward_returns=event_frame,
        )

    # -- data access (feature stores + daily_prices ONLY) ------------------

    def _load_adj_close(self, symbol: str) -> pd.Series:
        instrument_id = self._instrument_id(symbol)
        rows = self._session.execute(
            select(DailyPrice.price_date, DailyPrice.adj_close)
            .where(
                DailyPrice.instrument_id == instrument_id,
                DailyPrice.adj_close.is_not(None),
            )
            .order_by(DailyPrice.price_date)
        ).all()
        if not rows:
            return pd.Series(dtype=float)
        index = pd.DatetimeIndex(pd.to_datetime([r[0] for r in rows]))
        return pd.Series([float(r[1]) for r in rows], index=index)

    def _filter_series(self, research_filter: ResearchFilter, target_symbol: str) -> pd.Series:
        definition = self._features.get_definition(research_filter.feature)
        if definition is None:
            raise ConfigurationError(
                f"unknown feature {research_filter.feature!r}; see: mip research describe"
            )
        if definition.scope is FeatureScope.MARKET:
            return self._features.get_market_series(definition.id)
        symbol = research_filter.symbol or target_symbol
        return self._features.get_instrument_series(definition.id, self._instrument_id(symbol))

    def _instrument_id(self, symbol: str) -> int:
        instrument_id = self._session.scalar(
            select(Instrument.id).where(Instrument.symbol == symbol)
        )
        if instrument_id is None:
            raise ConfigurationError(f"unknown symbol {symbol!r}")
        return instrument_id
