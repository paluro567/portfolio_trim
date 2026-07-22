"""Market regime features (market scope; binary 0/1 values).

Thresholds are versioned params: changing one is a version bump, never a
silent redefinition. Rate regimes depend on dgs10_chg_63d — dependency
ordering is the registry's job."""

import pandas as pd

from mip.domain.enums import FeatureScope
from mip.features.base import FeatureCalculator, FeatureContext, FeatureSpec


class RegimeBull(FeatureCalculator):
    def __init__(self) -> None:
        super().__init__(
            FeatureSpec(
                name="regime_bull",
                version=1,
                scope=FeatureScope.MARKET,
                description="1 when SPY (adjusted) is above its 200-session moving average",
                params={"benchmark": "SPY", "window": 200},
                uses_adjusted_prices=True,
                lookback_sessions=210,
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        spy = ctx.benchmarks["SPY"]["adj_close"]
        ma200 = spy.rolling(int(self.spec.params["window"])).mean()
        signal = (spy > ma200).astype(float)
        return signal.where(ma200.notna()).reindex(ctx.dates)


class RegimeHighVol(FeatureCalculator):
    def __init__(self, threshold: float = 25.0) -> None:
        super().__init__(
            FeatureSpec(
                name="regime_high_vol",
                version=1,
                scope=FeatureScope.MARKET,
                description=f"1 when the VIX close exceeds {threshold}",
                params={"threshold": threshold},
                depends_on=("vix_level",),
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        vix = ctx.features["vix_level"]
        return (vix > float(self.spec.params["threshold"])).astype(float).where(vix.notna())


class RegimeRates(FeatureCalculator):
    def __init__(self, direction: str, threshold_pp: float = 0.25) -> None:
        rising = direction == "rising"
        super().__init__(
            FeatureSpec(
                name=f"regime_{direction}_rates",
                version=1,
                scope=FeatureScope.MARKET,
                description=(
                    f"1 when the 10y Treasury yield has "
                    f"{'risen' if rising else 'fallen'} more than "
                    f"{threshold_pp}pp over 63 observations"
                ),
                params={"direction": direction, "threshold_pp": threshold_pp},
                depends_on=("dgs10_chg_63d",),
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        change = ctx.features["dgs10_chg_63d"]
        threshold = float(self.spec.params["threshold_pp"])
        if self.spec.params["direction"] == "rising":
            signal = change > threshold
        else:
            signal = change < -threshold
        return signal.astype(float).where(change.notna())


class SectorBreadth(FeatureCalculator):
    """Share of sector ETFs trading above their 50-session moving average —
    a cross-sectional market-breadth measure built entirely from data the
    pipeline already loads."""

    def __init__(self, window: int = 50) -> None:
        super().__init__(
            FeatureSpec(
                name="sector_breadth_ma50",
                version=1,
                scope=FeatureScope.MARKET,
                description=(
                    "Share of the sector ETFs above their 50-session moving average "
                    "(market breadth)"
                ),
                params={"window": window, "universe": "sector ETFs"},
                uses_adjusted_prices=True,
                lookback_sessions=60,
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        window = int(self.spec.params["window"])
        flags = []
        for symbol, frame in sorted(ctx.benchmarks.items()):
            if symbol == "SPY":
                continue  # breadth of the sectors, not the index itself
            closes = frame["adj_close"]
            ma = closes.rolling(window).mean()
            flags.append((closes > ma).astype(float).where(ma.notna()).reindex(ctx.dates))
        if not flags:
            return pd.Series(float("nan"), index=ctx.dates)
        stacked = pd.concat(flags, axis=1)
        # require at least half the sector panel to be computable
        counts = stacked.notna().sum(axis=1)
        breadth = stacked.mean(axis=1)
        return breadth.where(counts >= max(1, stacked.shape[1] // 2))
