"""Relative performance vs SPY and vs the sector ETF (FK-resolved, D11).

Industry-ETF relative return is intentionally absent: the frozen schema
has no industry->ETF mapping (architecture amendment required)."""

import pandas as pd

from mip.domain.enums import FeatureScope
from mip.features.base import FeatureCalculator, FeatureContext, FeatureSpec, sessions_return


class RelativeReturn(FeatureCalculator):
    def __init__(self, benchmark: str, window: int) -> None:  # 'SPY' | 'sector'
        super().__init__(
            FeatureSpec(
                name=f"rel_ret_{benchmark.lower()}_{window}d",
                version=1,
                scope=FeatureScope.INSTRUMENT,
                description=(
                    f"{window}-session return minus the "
                    f"{'S&P 500 (SPY)' if benchmark == 'SPY' else 'sector ETF'} return"
                ),
                params={"benchmark": benchmark, "window": window, "price": "adj_close"},
                uses_adjusted_prices=True,
                lookback_sessions=window + 5,
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        window = int(self.spec.params["window"])
        own = sessions_return(ctx.prices["adj_close"], window)

        benchmark = str(self.spec.params["benchmark"])
        symbol = ctx.sector_etf if benchmark == "sector" else benchmark
        frame = ctx.benchmarks.get(symbol) if symbol else None
        if frame is None or frame.empty:
            return pd.Series(float("nan"), index=own.index)  # no benchmark -> absent

        bench = sessions_return(frame["adj_close"], window).reindex(own.index)
        return own - bench


class RelativeReturnAccel(FeatureCalculator):
    """Momentum acceleration: how the N-session relative return vs SPY has
    changed since N sessions earlier. Positive = relative momentum building,
    negative = fading. Derived from rel_ret_spy_{N}d, so PIT correctness is
    inherited (adjusted closes only, no external data)."""

    def __init__(self, window: int) -> None:
        super().__init__(
            FeatureSpec(
                name=f"rel_ret_spy_accel_{window}d",
                version=1,
                scope=FeatureScope.INSTRUMENT,
                description=(
                    f"Change in the {window}-session relative return vs SPY "
                    f"compared with {window} sessions earlier (momentum acceleration)"
                ),
                params={"benchmark": "SPY", "window": window, "price": "adj_close"},
                uses_adjusted_prices=True,
                lookback_sessions=2 * window + 5,
                depends_on=(f"rel_ret_spy_{window}d",),
            )
        )

    def compute(self, ctx: FeatureContext) -> pd.Series:
        window = int(self.spec.params["window"])
        rel = ctx.features[f"rel_ret_spy_{window}d"]
        return rel - rel.shift(window)
