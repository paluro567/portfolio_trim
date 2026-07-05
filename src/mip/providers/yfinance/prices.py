"""yfinance price adapter.

The ONLY module that imports yfinance for prices. normalize_history() is a
pure function so the column mapping is unit-testable without network.

yfinance notes:
- auto_adjust=False keeps raw Close alongside Adj Close (the platform
  stores both; features choose per feature_definitions.uses_adjusted_prices).
- history(end=...) is exclusive, so the adapter adds one day.
- Dividends / Stock Splits arrive as columns of the same frame.
"""

from datetime import date, timedelta

import pandas as pd

from mip.core.exceptions import TransientError
from mip.providers.base import (
    PriceFetch,
    empty_action_frame,
    empty_price_frame,
)

_COLUMN_MAP = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adj_close",
    "Volume": "volume",
}


def normalize_history(raw: pd.DataFrame) -> PriceFetch:
    """Map a yfinance history() frame onto the platform DTO contracts."""
    if raw.empty:
        return PriceFetch(prices=empty_price_frame(), actions=empty_action_frame())

    frame = raw.copy()
    # tz-aware DatetimeIndex -> plain dates
    dates = pd.Series([ts.date() for ts in frame.index], index=frame.index)

    prices = pd.DataFrame({"price_date": dates})
    for src, dst in _COLUMN_MAP.items():
        prices[dst] = frame[src].values if src in frame.columns else float("nan")
    prices = prices[prices["close"].notna()]  # yfinance emits stray all-NaN rows
    prices = prices.drop_duplicates(subset="price_date", keep="first")
    prices = prices.sort_values("price_date").reset_index(drop=True)

    actions: list[dict[str, object]] = []
    if "Dividends" in frame.columns:
        for ts, amount in frame["Dividends"].items():
            if pd.notna(amount) and amount != 0:
                actions.append(
                    {
                        "action_type": "dividend",
                        "ex_date": ts.date(),
                        "split_ratio": float("nan"),
                        "cash_amount": float(amount),
                    }
                )
    if "Stock Splits" in frame.columns:
        for ts, ratio in frame["Stock Splits"].items():
            if pd.notna(ratio) and ratio != 0:
                actions.append(
                    {
                        "action_type": "split",
                        "ex_date": ts.date(),
                        "split_ratio": float(ratio),
                        "cash_amount": float("nan"),
                    }
                )
    action_frame = pd.DataFrame(actions) if actions else empty_action_frame()

    return PriceFetch(prices=prices, actions=action_frame)


class YFinancePriceProvider:
    name = "yfinance"

    def fetch_daily(self, symbol: str, start: date, end: date) -> PriceFetch:
        import yfinance as yf

        try:
            raw = yf.Ticker(symbol).history(
                start=start,
                end=end + timedelta(days=1),  # yfinance end is exclusive
                interval="1d",
                auto_adjust=False,
                actions=True,
                raise_errors=False,
            )
        except Exception as exc:
            # yfinance surfaces network/rate-limit failures as assorted
            # exception types; classify them all retryable.
            raise TransientError(f"yfinance fetch failed for {symbol}: {exc}") from exc
        return normalize_history(raw)
