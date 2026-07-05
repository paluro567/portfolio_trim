"""Fundamental features. Snapshots are PIT-honest: a value is usable from
its as_of_date (our fetch date) forward — never backfilled (§7.4)."""

import numpy as np
import pandas as pd

from mip.domain.enums import FeatureScope
from mip.features.base import FeatureCalculator, FeatureContext, FeatureSpec, ffill_asof


class FundamentalField(FeatureCalculator):
    def __init__(self, name: str, field: str, description: str, log10: bool = False) -> None:
        super().__init__(
            FeatureSpec(
                name=name,
                version=1,
                scope=FeatureScope.INSTRUMENT,
                description=description,
                params={"field": field, "log10": log10},
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        if ctx.fundamentals is None or ctx.fundamentals.empty:
            return pd.Series(float("nan"), index=ctx.dates)
        values = ctx.fundamentals[str(self.spec.params["field"])]
        aligned = ffill_asof(values, ctx.dates)
        if self.spec.params["log10"]:
            aligned = aligned.where(aligned > 0)
            return pd.Series(np.log10(aligned), index=ctx.dates)
        return aligned


class PriceToSales(FeatureCalculator):
    def __init__(self) -> None:
        super().__init__(
            FeatureSpec(
                name="price_to_sales",
                version=1,
                scope=FeatureScope.INSTRUMENT,
                description="Market cap / trailing-twelve-month revenue (per snapshot)",
                params={"fields": ["market_cap", "revenue_ttm"]},
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        if ctx.fundamentals is None or ctx.fundamentals.empty:
            return pd.Series(float("nan"), index=ctx.dates)
        revenue = ctx.fundamentals["revenue_ttm"].where(ctx.fundamentals["revenue_ttm"] > 0)
        ratio = ctx.fundamentals["market_cap"] / revenue
        return ffill_asof(ratio, ctx.dates)


class RevenueGrowthYoY(FeatureCalculator):
    """TTM revenue vs the snapshot ~1 year earlier. Absent until a year of
    snapshot history exists (PIT-honest: no backfilled fundamentals)."""

    def __init__(self) -> None:
        super().__init__(
            FeatureSpec(
                name="revenue_growth_yoy",
                version=1,
                scope=FeatureScope.INSTRUMENT,
                description="TTM revenue vs the snapshot taken ~1 year earlier",
                params={"field": "revenue_ttm", "min_gap_days": 350},
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        if ctx.fundamentals is None or ctx.fundamentals.empty:
            return pd.Series(float("nan"), index=ctx.dates)
        revenue = ctx.fundamentals["revenue_ttm"].dropna().sort_index()
        min_gap = pd.Timedelta(days=int(self.spec.params["min_gap_days"]))
        growth: dict[object, float] = {}
        index = pd.to_datetime(revenue.index)
        for position, as_of in enumerate(index):
            earlier = index[index <= as_of - min_gap]
            if len(earlier) == 0:
                continue
            base = revenue.iloc[index.get_loc(earlier[-1])]
            if base and base > 0:
                growth[as_of] = revenue.iloc[position] / base - 1.0
        if not growth:
            return pd.Series(float("nan"), index=ctx.dates)
        return ffill_asof(pd.Series(growth), ctx.dates)


class EpsGrowthYoY(FeatureCalculator):
    """Latest reported EPS vs the report 4 quarters earlier. Reported
    events are public from their event date (PIT-safe)."""

    def __init__(self) -> None:
        super().__init__(
            FeatureSpec(
                name="eps_growth_yoy",
                version=1,
                scope=FeatureScope.INSTRUMENT,
                description="Latest reported EPS vs the report four quarters earlier",
                params={"quarters_back": 4},
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        reported = ctx.earnings_reported
        if reported is None or reported.empty:
            return pd.Series(float("nan"), index=ctx.dates)
        events = reported.dropna(subset=["eps_actual"]).sort_values("earnings_date")
        back = int(self.spec.params["quarters_back"])
        growth: dict[object, float] = {}
        actuals = events["eps_actual"].tolist()
        dates = list(pd.to_datetime(events["earnings_date"]))
        for i in range(back, len(actuals)):
            base = actuals[i - back]
            if base and base > 0:  # sign flips make ratios meaningless
                growth[dates[i]] = actuals[i] / base - 1.0
        if not growth:
            return pd.Series(float("nan"), index=ctx.dates)
        return ffill_asof(pd.Series(growth), ctx.dates)
