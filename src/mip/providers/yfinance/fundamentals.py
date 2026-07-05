"""yfinance fundamentals adapter.

normalize_info() is pure: maps a Ticker.info dict onto FUNDAMENTAL_FIELDS.
Missing/absent keys become None (stored as NULL — the snapshot is never
quarantined for gaps; yfinance coverage varies wildly by company)."""

import math

from mip.core.exceptions import TransientError
from mip.providers.base import FUNDAMENTAL_FIELDS

_INFO_MAP = {
    "market_cap": "marketCap",
    "trailing_pe": "trailingPE",
    "forward_pe": "forwardPE",
    "price_to_book": "priceToBook",
    "trailing_eps": "trailingEps",
    "forward_eps": "forwardEps",
    "dividend_yield": "dividendYield",
    "beta": "beta",
    "shares_outstanding": "sharesOutstanding",
    "revenue_ttm": "totalRevenue",
    "profit_margin": "profitMargins",
    "debt_to_equity": "debtToEquity",
}


def normalize_info(info: dict[str, object] | None) -> dict[str, float | None]:
    """Map yfinance info keys onto the FUNDAMENTAL_FIELDS contract."""
    info = info or {}
    snapshot: dict[str, float | None] = {}
    for field in FUNDAMENTAL_FIELDS:
        raw = info.get(_INFO_MAP[field])
        if isinstance(raw, (int, float)) and not (isinstance(raw, float) and math.isnan(raw)):
            snapshot[field] = float(raw)
        else:
            snapshot[field] = None
    return snapshot


class YFinanceFundamentalsProvider:
    name = "yfinance"

    def fetch_fundamentals(self, symbol: str) -> dict[str, float | None]:
        import yfinance as yf

        try:
            info = yf.Ticker(symbol).get_info()
        except Exception as exc:
            raise TransientError(f"yfinance info fetch failed for {symbol}: {exc}") from exc
        return normalize_info(info)
