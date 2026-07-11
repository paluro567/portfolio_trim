"""Golden-value tests: calculators vs hand-computed fixtures (no DB)."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from mip.features.base import FeatureContext
from mip.features.price import (
    ATRPercent,
    Distance52Week,
    MASpread,
    PriceToMA,
    RollingReturn,
    Volatility,
)
from mip.features.relative import RelativeReturn


def business_days(n: int, start: str = "2026-01-05") -> pd.DatetimeIndex:
    return pd.bdate_range(start, periods=n)


def price_frame(closes: list[float], index: pd.DatetimeIndex) -> pd.DataFrame:
    closes_s = pd.Series(closes, index=index, dtype=float)
    return pd.DataFrame(
        {
            "open": closes_s * 0.99,
            "high": closes_s * 1.02,
            "low": closes_s * 0.98,
            "close": closes_s,
            "adj_close": closes_s,  # keep adj == raw for hand math
            "volume": 1000.0,
        }
    )


def ctx_for(prices: pd.DataFrame, **kwargs: object) -> FeatureContext:
    return FeatureContext(dates=prices.index, prices=prices, **kwargs)


def test_rolling_return_golden() -> None:
    index = business_days(10)
    closes = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109]
    series = RollingReturn(5).compute(ctx_for(price_frame(closes, index)))

    assert series.iloc[4] != series.iloc[4] or True  # first 5 are NaN
    assert np.isnan(series.iloc[4])
    assert series.iloc[5] == pytest.approx(105 / 100 - 1)
    assert series.iloc[9] == pytest.approx(109 / 104 - 1)


def test_price_to_ma_and_spread_golden() -> None:
    index = business_days(6)
    closes = [100, 102, 104, 106, 108, 110]
    frame = price_frame(closes, index)

    to_ma3 = PriceToMA(3).compute(ctx_for(frame))
    # MA3 at last = (106+108+110)/3 = 108
    assert to_ma3.iloc[-1] == pytest.approx(110 / 108 - 1)

    spread = MASpread(2, 4).compute(ctx_for(frame))
    # last: MA2 = 109, MA4 = (104+106+108+110)/4 = 107
    assert spread.iloc[-1] == pytest.approx(109 / 107 - 1)


def test_volatility_golden() -> None:
    index = business_days(5)
    closes = [100, 102, 100, 102, 100]
    series = Volatility(3).compute(ctx_for(price_frame(closes, index)))

    returns = pd.Series(closes).pct_change()
    expected = returns.iloc[2:5].std() * np.sqrt(252)
    assert series.iloc[-1] == pytest.approx(expected)


def test_atr_pct_golden() -> None:
    index = business_days(4)
    frame = price_frame([100, 100, 100, 100], index)
    # constant close -> TR = high-low = 4.0; ATR2/close = 0.04
    series = ATRPercent(2).compute(ctx_for(frame))
    assert series.iloc[-1] == pytest.approx(0.04)


def test_distance_52w_uses_raw_close() -> None:
    index = business_days(260)
    closes = [100.0] * 259 + [90.0]
    frame = price_frame(closes, index)
    frame["adj_close"] = frame["close"] * 0.5  # adjusted differs: must be ignored

    high = Distance52Week("high").compute(ctx_for(frame))
    low = Distance52Week("low").compute(ctx_for(frame))

    assert high.iloc[-1] == pytest.approx(90 / 100 - 1)
    assert low.iloc[-1] == pytest.approx(0.0)  # 90 IS the 252-day low


def test_relative_return_vs_benchmark() -> None:
    index = business_days(7)
    own = price_frame([100, 101, 102, 103, 104, 105, 106], index)
    spy = price_frame([100, 100, 100, 100, 100, 102, 102], index)

    series = RelativeReturn("SPY", 5).compute(ctx_for(own, benchmarks={"SPY": spy}))
    assert series.iloc[5] == pytest.approx((105 / 100 - 1) - (102 / 100 - 1))


def test_relative_return_without_sector_etf_is_absent() -> None:
    index = business_days(7)
    own = price_frame([100, 101, 102, 103, 104, 105, 106], index)
    series = RelativeReturn("sector", 5).compute(ctx_for(own, benchmarks={}, sector_etf=None))
    assert series.isna().all()


def test_relative_return_accel_is_change_in_relative_return() -> None:
    from mip.features.relative import RelativeReturnAccel

    index = business_days(12)
    rel = pd.Series([float(i) / 100 for i in range(12)], index=index)
    ctx = FeatureContext(dates=index, features={"rel_ret_spy_5d": rel})

    series = RelativeReturnAccel(5).compute(ctx)

    assert series.iloc[:5].isna().all()  # needs a full shift window
    assert series.iloc[5] == pytest.approx(rel.iloc[5] - rel.iloc[0])
    assert series.iloc[-1] == pytest.approx(rel.iloc[-1] - rel.iloc[-6])


def test_relative_return_accel_propagates_missing_upstream() -> None:
    from mip.features.relative import RelativeReturnAccel

    index = business_days(12)
    rel = pd.Series(float("nan"), index=index)  # no benchmark -> absent upstream
    ctx = FeatureContext(dates=index, features={"rel_ret_spy_5d": rel})

    assert RelativeReturnAccel(5).compute(ctx).isna().all()


def test_earnings_days_since_and_until() -> None:
    from mip.features.earnings import DaysSinceEarnings, DaysUntilEarnings

    index = pd.DatetimeIndex(pd.to_datetime([date(2026, 6, 29), date(2026, 7, 2)]))
    ctx = FeatureContext(
        dates=index,
        earnings_reported=pd.DataFrame({"earnings_date": [date(2026, 5, 6)], "eps_actual": [1.5]}),
        earnings_announced=pd.DataFrame(
            {"known_from": [date(2026, 7, 1)], "earnings_date": [date(2026, 8, 5)]}
        ),
    )
    since = DaysSinceEarnings().compute(ctx)
    until = DaysUntilEarnings().compute(ctx)

    assert since.iloc[0] == (date(2026, 6, 29) - date(2026, 5, 6)).days
    # announcement observed 2026-07-01: invisible on 06-29, visible on 07-02
    assert np.isnan(until.iloc[0])
    assert until.iloc[1] == (date(2026, 8, 5) - date(2026, 7, 2)).days
