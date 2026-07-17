"""Macro features (market scope). All computations happen at observation
level, carry the availability date of the NEWEST observation involved,
and are projected onto feature dates only through align_availability()
— the publication-lag gate (D13)."""

import pandas as pd

from mip.domain.enums import FeatureScope
from mip.features.base import (
    FeatureCalculator,
    FeatureContext,
    FeatureSpec,
    align_availability,
)


class MacroLevel(FeatureCalculator):
    def __init__(self, name: str, code: str, description: str) -> None:
        super().__init__(
            FeatureSpec(
                name=name,
                version=1,
                scope=FeatureScope.MARKET,
                description=description,
                params={"macro_codes": [code]},
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        code = self.spec.params["macro_codes"][0]
        frame = ctx.macro.get(code)
        if frame is None or frame.empty:
            return pd.Series(float("nan"), index=ctx.dates)
        return align_availability(frame, ctx.dates)


class MacroChange(FeatureCalculator):
    """Change over N observations (for daily series, N business days)."""

    def __init__(self, name: str, code: str, window_obs: int, description: str) -> None:
        super().__init__(
            FeatureSpec(
                name=name,
                version=1,
                scope=FeatureScope.MARKET,
                description=description,
                params={"macro_codes": [code], "window_obs": window_obs},
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        code = self.spec.params["macro_codes"][0]
        frame = ctx.macro.get(code)
        if frame is None or frame.empty:
            return pd.Series(float("nan"), index=ctx.dates)
        frame = frame.copy()
        window = int(self.spec.params["window_obs"])
        frame["value"] = frame["value"] - frame["value"].shift(window)
        # availability = when the NEWER observation became public
        return align_availability(frame, ctx.dates)


class CurveSlope(FeatureCalculator):
    def __init__(self, name: str, long_code: str, short_code: str, description: str) -> None:
        super().__init__(
            FeatureSpec(
                name=name,
                version=1,
                scope=FeatureScope.MARKET,
                description=description,
                params={"macro_codes": [long_code, short_code]},
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        long_code, short_code = self.spec.params["macro_codes"]
        long_frame = ctx.macro.get(long_code)
        short_frame = ctx.macro.get(short_code)
        if long_frame is None or short_frame is None or long_frame.empty or short_frame.empty:
            return pd.Series(float("nan"), index=ctx.dates)
        merged = long_frame.join(short_frame, how="inner", lsuffix="_long", rsuffix="_short")
        result = pd.DataFrame(
            {
                "value": merged["value_long"] - merged["value_short"],
                # knowable only once BOTH legs are public
                "available_from": merged[["available_from_long", "available_from_short"]].max(
                    axis=1
                ),
            }
        )
        return align_availability(result, ctx.dates)


class YoYChange(FeatureCalculator):
    """Year-over-year % change of a monthly index (e.g. CPI trend)."""

    def __init__(self, name: str, code: str, description: str, accel_months: int = 0) -> None:
        super().__init__(
            FeatureSpec(
                name=name,
                version=1,
                scope=FeatureScope.MARKET,
                description=description,
                params={"macro_codes": [code], "accel_months": accel_months},
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        code = self.spec.params["macro_codes"][0]
        frame = ctx.macro.get(code)
        if frame is None or frame.empty:
            return pd.Series(float("nan"), index=ctx.dates)
        frame = frame.copy()
        # date-based lookback (positional shift breaks on gaps in history)
        year_ago = frame["value"].reindex(frame.index - pd.DateOffset(months=12))
        yoy = pd.Series(frame["value"].values / year_ago.values - 1.0, index=frame.index)
        accel = int(self.spec.params["accel_months"])
        if accel:
            earlier = yoy.reindex(frame.index - pd.DateOffset(months=accel))
            yoy = pd.Series(yoy.values - earlier.values, index=frame.index)
        frame["value"] = yoy
        return align_availability(frame, ctx.dates)


class MarketFeatureChange(FeatureCalculator):
    """Change in an upstream MARKET feature vs `window` trading sessions
    earlier (e.g. yield-curve steepening/flattening). PIT correctness is
    inherited from the upstream feature (publication lags already applied)."""

    def __init__(self, source: str, window: int, description: str) -> None:
        super().__init__(
            FeatureSpec(
                name=f"{source}_chg_{window}d",
                version=1,
                scope=FeatureScope.MARKET,
                description=description,
                params={"source": source, "window": window},
                lookback_sessions=window + 5,
                depends_on=(source,),
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        source = ctx.features[str(self.spec.params["source"])]
        return source - source.shift(int(self.spec.params["window"]))


class MacroPercentile(FeatureCalculator):
    """Rolling percentile of the latest observation within its window."""

    def __init__(self, name: str, code: str, window_obs: int, description: str) -> None:
        super().__init__(
            FeatureSpec(
                name=name,
                version=1,
                scope=FeatureScope.MARKET,
                description=description,
                params={"macro_codes": [code], "window_obs": window_obs},
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        code = self.spec.params["macro_codes"][0]
        frame = ctx.macro.get(code)
        if frame is None or frame.empty:
            return pd.Series(float("nan"), index=ctx.dates)
        # "trailing N observations" means N actual values: missing-value
        # markers (FRED '.' -> NULL) must not poison the rolling window
        frame = frame.dropna(subset=["value"]).copy()
        window = int(self.spec.params["window_obs"])
        frame["value"] = (
            frame["value"]
            .rolling(window)
            .apply(lambda arr: float((arr[-1] >= arr).mean()), raw=True)
        )
        return align_availability(frame, ctx.dates)
