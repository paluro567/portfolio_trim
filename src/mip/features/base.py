"""Feature framework core: spec, context, calculator ABC, PIT helpers.

Point-in-time rule (D13): calculators never see raw obs_date-keyed macro
data. Every macro frame in the context carries `available_from`
(obs_date + publication_lag_days) and align_availability() is the ONLY
sanctioned way to project it onto feature dates. Fundamentals are usable
from their as_of_date (fetch date); reported earnings from their event
date; announced earnings from when the announcement was observed.
"""

import abc
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from mip.domain.enums import FeatureScope


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    version: int
    scope: FeatureScope
    description: str  # human-readable: future explanation text (D7)
    params: dict[str, object] = field(default_factory=dict)
    uses_adjusted_prices: bool | None = None
    lookback_sessions: int = 0  # extra history the calculator needs
    depends_on: tuple[str, ...] = ()  # names of upstream features


@dataclass
class FeatureContext:
    """Everything a calculator may read. Series/frames are float-typed and
    date-indexed (ascending); they include the lookback buffer."""

    dates: pd.DatetimeIndex  # trading days incl. buffer
    prices: pd.DataFrame | None = None  # instrument scope only
    benchmarks: dict[str, pd.DataFrame] = field(default_factory=dict)
    sector_etf: str | None = None
    macro: dict[str, pd.DataFrame] = field(default_factory=dict)
    # macro[code]: columns [value, available_from], indexed by obs_date
    fundamentals: pd.DataFrame | None = None  # indexed by as_of_date
    earnings_reported: pd.DataFrame | None = None  # [earnings_date, eps_actual]
    earnings_announced: pd.DataFrame | None = None  # [known_from, earnings_date]
    features: dict[str, pd.Series] = field(default_factory=dict)  # upstream outputs


class FeatureCalculator(abc.ABC):
    """One feature. Pure: compute() reads only the context and returns a
    float Series indexed by date. NaN = not computable (row is absent from
    the store, never zero)."""

    def __init__(self, spec: FeatureSpec) -> None:
        self.spec = spec

    @abc.abstractmethod
    def compute(self, ctx: FeatureContext) -> pd.Series: ...


def align_availability(frame: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.Series:
    """As-of join under publication lag: for each feature date, the latest
    value whose available_from has elapsed. THE gate against macro
    look-ahead — nothing else may project obs-keyed data onto dates."""
    if frame.empty:
        return pd.Series(float("nan"), index=dates)
    right = (
        frame[["available_from", "value"]]
        .dropna(subset=["available_from"])
        .sort_values("available_from")
    )
    right["available_from"] = pd.to_datetime(right["available_from"])
    left = pd.DataFrame({"feature_date": pd.to_datetime(dates)})
    merged = pd.merge_asof(left, right, left_on="feature_date", right_on="available_from")
    return pd.Series(merged["value"].values, index=dates, dtype=float)


def sessions_return(series: pd.Series, window: int) -> pd.Series:
    return series / series.shift(window) - 1.0


def ffill_asof(values: pd.Series, dates: pd.DatetimeIndex) -> pd.Series:
    """Latest value at or before each feature date (as-of forward fill).
    For data that is public from its own index date: fundamental snapshots
    (as_of_date) and reported earnings events (event date)."""
    if values.dropna().empty:
        return pd.Series(float("nan"), index=dates)
    frame = values.dropna().sort_index()
    right = pd.DataFrame({"as_of": pd.to_datetime(frame.index), "value": frame.values})
    left = pd.DataFrame({"feature_date": pd.to_datetime(dates)})
    merged = pd.merge_asof(left, right, left_on="feature_date", right_on="as_of")
    return pd.Series(merged["value"].values, index=dates, dtype=float)


def as_of_date_index(values: list[date]) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(pd.to_datetime(values))
