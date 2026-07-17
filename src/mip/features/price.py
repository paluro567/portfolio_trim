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


class OvernightGap(FeatureCalculator):
    """Opening gap: today's raw open vs yesterday's raw close, minus 1.
    Raw prices (what an observer saw); the earnings model uses it to
    classify post-report gap reactions."""

    def __init__(self) -> None:
        super().__init__(
            FeatureSpec(
                name="gap_1d",
                version=1,
                scope=FeatureScope.INSTRUMENT,
                description="Overnight gap: raw open vs previous raw close, minus 1",
                params={"price": "raw_open_close"},
                uses_adjusted_prices=False,
                lookback_sessions=5,
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        return ctx.prices["open"] / ctx.prices["close"].shift(1) - 1.0


class VolatilityRatio(FeatureCalculator):
    """Short-window volatility relative to a longer window, minus 1:
    positive = volatility expanding, negative = contracting. Scale-free,
    so one threshold convention works across instruments. Derived from the
    registered vol features, so PIT correctness is inherited."""

    def __init__(self, fast: int = 21, slow: int = 63) -> None:
        super().__init__(
            FeatureSpec(
                name=f"vol_ratio_{fast}_{slow}",
                version=1,
                scope=FeatureScope.INSTRUMENT,
                description=(
                    f"{fast}-session volatility over {slow}-session volatility, minus 1 "
                    "(positive = volatility expanding)"
                ),
                params={"fast": fast, "slow": slow, "price": "adj_close"},
                uses_adjusted_prices=True,
                lookback_sessions=slow + 10,
                depends_on=(f"vol_{fast}d", f"vol_{slow}d"),
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        fast = ctx.features[f"vol_{int(self.spec.params['fast'])}d"]
        slow = ctx.features[f"vol_{int(self.spec.params['slow'])}d"]
        return (fast / slow - 1.0).where(slow > 0)


class MASpreadChange(FeatureCalculator):
    """Change in the MA spread vs `window` sessions earlier: positive =
    the bullish cross is widening, negative = narrowing. Derived from the
    registered spread feature, so PIT correctness is inherited."""

    def __init__(self, fast: int = 50, slow: int = 200, window: int = 21) -> None:
        super().__init__(
            FeatureSpec(
                name=f"ma{fast}_ma{slow}_spread_chg_{window}d",
                version=1,
                scope=FeatureScope.INSTRUMENT,
                description=(
                    f"Change in the {fast}/{slow}-session MA spread vs {window} sessions "
                    "earlier (positive = trend cross widening)"
                ),
                params={"fast": fast, "slow": slow, "window": window, "price": "adj_close"},
                uses_adjusted_prices=True,
                lookback_sessions=slow + window + 10,
                depends_on=(f"ma{fast}_ma{slow}_spread",),
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        spread = ctx.features[f"ma{self.spec.params['fast']}_ma{self.spec.params['slow']}_spread"]
        return spread - spread.shift(int(self.spec.params["window"]))


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
