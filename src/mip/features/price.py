"""Price features. Returns/MAs/volatility use ADJUSTED close (historically
correct for returns); level features (52-week distance, ATR) use RAW
prices per the frozen architecture's adjusted-vs-raw rule (§5.5 of the
review; feature_definitions.uses_adjusted_prices documents each)."""

import numpy as np
import pandas as pd

from mip.domain.enums import FeatureScope
from mip.features.base import FeatureCalculator, FeatureContext, FeatureSpec, sessions_return


class RollingReturn(FeatureCalculator):
    def __init__(self, window: int) -> None:
        super().__init__(
            FeatureSpec(
                name=f"ret_{window}d",
                version=1,
                scope=FeatureScope.INSTRUMENT,
                description=f"Total return over the last {window} trading sessions",
                params={"window": window, "price": "adj_close"},
                uses_adjusted_prices=True,
                lookback_sessions=window + 5,
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        return sessions_return(ctx.prices["adj_close"], int(self.spec.params["window"]))


class LogReturn1d(FeatureCalculator):
    def __init__(self) -> None:
        super().__init__(
            FeatureSpec(
                name="log_ret_1d",
                version=1,
                scope=FeatureScope.INSTRUMENT,
                description="One-session log return (adjusted close)",
                params={"price": "adj_close"},
                uses_adjusted_prices=True,
                lookback_sessions=5,
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        adj = ctx.prices["adj_close"]
        return np.log(adj / adj.shift(1))


class PriceToMA(FeatureCalculator):
    def __init__(self, window: int) -> None:
        super().__init__(
            FeatureSpec(
                name=f"price_to_ma{window}",
                version=1,
                scope=FeatureScope.INSTRUMENT,
                description=f"Adjusted close vs its {window}-session moving average, minus 1",
                params={"window": window, "price": "adj_close"},
                uses_adjusted_prices=True,
                lookback_sessions=window + 5,
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        adj = ctx.prices["adj_close"]
        return adj / adj.rolling(int(self.spec.params["window"])).mean() - 1.0


class MASpread(FeatureCalculator):
    def __init__(self, fast: int = 50, slow: int = 200) -> None:
        super().__init__(
            FeatureSpec(
                name=f"ma{fast}_ma{slow}_spread",
                version=1,
                scope=FeatureScope.INSTRUMENT,
                description=f"{fast}-session MA vs {slow}-session MA, minus 1 (trend cross)",
                params={"fast": fast, "slow": slow, "price": "adj_close"},
                uses_adjusted_prices=True,
                lookback_sessions=slow + 10,
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        adj = ctx.prices["adj_close"]
        fast = adj.rolling(int(self.spec.params["fast"])).mean()
        slow = adj.rolling(int(self.spec.params["slow"])).mean()
        return fast / slow - 1.0


class Volatility(FeatureCalculator):
    def __init__(self, window: int) -> None:
        super().__init__(
            FeatureSpec(
                name=f"vol_{window}d",
                version=1,
                scope=FeatureScope.INSTRUMENT,
                description=f"Annualized volatility of daily returns over {window} sessions",
                params={"window": window, "annualization": 252, "price": "adj_close"},
                uses_adjusted_prices=True,
                lookback_sessions=window + 5,
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        returns = ctx.prices["adj_close"].pct_change()
        window = int(self.spec.params["window"])
        return returns.rolling(window).std() * float(np.sqrt(252))


class ATRPercent(FeatureCalculator):
    def __init__(self, window: int = 14) -> None:
        super().__init__(
            FeatureSpec(
                name=f"atr{window}_pct",
                version=1,
                scope=FeatureScope.INSTRUMENT,
                description=f"{window}-session Average True Range as a fraction of close",
                params={"window": window, "price": "raw_ohlc"},
                uses_adjusted_prices=False,
                lookback_sessions=window + 5,
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        high, low, close = ctx.prices["high"], ctx.prices["low"], ctx.prices["close"]
        prev_close = close.shift(1)
        true_range = pd.concat(
            [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
        ).max(axis=1)
        atr = true_range.rolling(int(self.spec.params["window"])).mean()
        return atr / close


class Distance52Week(FeatureCalculator):
    def __init__(self, kind: str) -> None:  # 'high' | 'low'
        super().__init__(
            FeatureSpec(
                name=f"dist_52w_{kind}",
                version=1,
                scope=FeatureScope.INSTRUMENT,
                description=(
                    f"Raw close vs its 252-session rolling {kind}, minus 1 "
                    "(raw prices: what an observer saw at the time)"
                ),
                params={"window": 252, "kind": kind, "price": "close"},
                uses_adjusted_prices=False,
                lookback_sessions=260,
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        close = ctx.prices["close"]
        rolling = close.rolling(252)
        reference = rolling.max() if self.spec.params["kind"] == "high" else rolling.min()
        return close / reference - 1.0
