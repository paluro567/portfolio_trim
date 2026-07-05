"""Earnings-proximity features.

PIT rules: a REPORTED event is public knowledge from its event date, so
days_since is safe over full history. An ANNOUNCED future date is only
knowable from when we observed the announcement (append-only history), so
days_until is sparse before observation history began — honest, not
fudged (§6.3)."""

import numpy as np
import pandas as pd

from mip.domain.enums import FeatureScope
from mip.features.base import FeatureCalculator, FeatureContext, FeatureSpec


class DaysSinceEarnings(FeatureCalculator):
    def __init__(self) -> None:
        super().__init__(
            FeatureSpec(
                name="days_since_earnings",
                version=1,
                scope=FeatureScope.INSTRUMENT,
                description="Calendar days since the last reported earnings event",
                params={"source": "reported_events"},
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        reported = ctx.earnings_reported
        if reported is None or reported.empty:
            return pd.Series(float("nan"), index=ctx.dates)
        events = pd.DatetimeIndex(pd.to_datetime(sorted(reported["earnings_date"].unique())))
        positions = events.searchsorted(ctx.dates, side="right") - 1
        values = [
            (ctx.dates[i] - events[positions[i]]).days if positions[i] >= 0 else float("nan")
            for i in range(len(ctx.dates))
        ]
        return pd.Series(values, index=ctx.dates, dtype=float)


class DaysUntilEarnings(FeatureCalculator):
    def __init__(self) -> None:
        super().__init__(
            FeatureSpec(
                name="days_until_earnings",
                version=1,
                scope=FeatureScope.INSTRUMENT,
                description=(
                    "Calendar days until the next announced earnings date, using only "
                    "announcements observed on or before the feature date"
                ),
                params={"source": "announced_observations"},
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        announced = ctx.earnings_announced
        if announced is None or announced.empty:
            return pd.Series(float("nan"), index=ctx.dates)
        known_from = pd.to_datetime(announced["known_from"]).values
        event_dates = pd.to_datetime(announced["earnings_date"]).values

        values: list[float] = []
        for d in ctx.dates:
            visible = event_dates[
                (known_from <= d.to_datetime64()) & (event_dates > d.to_datetime64())
            ]
            values.append(
                float((pd.Timestamp(visible.min()) - d).days) if len(visible) else float("nan")
            )
        return pd.Series(values, index=ctx.dates, dtype=float)


class EarningsRecency(FeatureCalculator):
    def __init__(self, half_life_days: int = 21) -> None:
        super().__init__(
            FeatureSpec(
                name="earnings_recency",
                version=1,
                scope=FeatureScope.INSTRUMENT,
                description=(
                    "Exponential decay of time since the last reported earnings "
                    "event (1.0 on the event day)"
                ),
                params={"half_life_days": half_life_days},
                depends_on=("days_since_earnings",),
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        days_since = ctx.features["days_since_earnings"]
        half_life = float(self.spec.params["half_life_days"])
        return pd.Series(np.exp(-np.log(2) * days_since / half_life), index=days_since.index)
