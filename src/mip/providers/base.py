"""Provider protocols and DTO column contracts (D1).

Nothing outside mip.providers may import a provider SDK. Adapters return
normalized pandas DataFrames with these exact column contracts; everything
downstream (validation, services, repositories) depends only on them.

PRICE_COLUMNS contract:
    price_date  datetime.date, ascending, unique
    open/high/low/close/adj_close  float (NaN allowed except close)
    volume      float/int (NaN allowed)

ACTION_COLUMNS contract:
    action_type  'split' | 'dividend'
    ex_date      datetime.date
    split_ratio  float (splits; NaN otherwise)
    cash_amount  float (dividends; NaN otherwise)
"""

from dataclasses import dataclass
from datetime import date
from typing import Protocol

import pandas as pd

PRICE_COLUMNS = ("price_date", "open", "high", "low", "close", "adj_close", "volume")
ACTION_COLUMNS = ("action_type", "ex_date", "split_ratio", "cash_amount")


def empty_price_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=list(PRICE_COLUMNS))


def empty_action_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=list(ACTION_COLUMNS))


@dataclass(frozen=True)
class PriceFetch:
    """One provider round-trip: prices plus corporate actions for a symbol."""

    prices: pd.DataFrame  # PRICE_COLUMNS contract
    actions: pd.DataFrame  # ACTION_COLUMNS contract


class PriceProvider(Protocol):
    """Daily price source. Implementations raise TransientError for
    retryable failures and PermanentError for non-retryable ones."""

    name: str

    def fetch_daily(self, symbol: str, start: date, end: date) -> PriceFetch: ...


# MACRO_COLUMNS contract:
#     obs_date  datetime.date, ascending, unique (reference period date)
#     value     float (NaN = published-but-missing, e.g. FRED '.')
MACRO_COLUMNS = ("obs_date", "value")


def empty_macro_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=list(MACRO_COLUMNS))


class MacroProvider(Protocol):
    """Macroeconomic series source. Same error contract as PriceProvider."""

    name: str

    def fetch_series(self, provider_code: str, start: date, end: date) -> pd.DataFrame: ...


# FUNDAMENTAL_FIELDS contract: a flat mapping of field -> float | int | None.
# Keys mirror company_fundamentals columns; None = provider has no value.
FUNDAMENTAL_FIELDS = (
    "market_cap",
    "trailing_pe",
    "forward_pe",
    "price_to_book",
    "trailing_eps",
    "forward_eps",
    "dividend_yield",
    "beta",
    "shares_outstanding",
    "revenue_ttm",
    "profit_margin",
    "debt_to_equity",
)


class FundamentalsProvider(Protocol):
    """Current-snapshot fundamentals source. Same error contract."""

    name: str

    def fetch_fundamentals(self, symbol: str) -> dict[str, float | None]: ...


# EARNINGS_COLUMNS contract:
#     earnings_date  datetime.date
#     time_of_day    'BMO' | 'AMC' | 'unknown'
#     eps_estimate   float (NaN allowed)
#     eps_actual     float (NaN allowed; present => the event happened)
EARNINGS_COLUMNS = ("earnings_date", "time_of_day", "eps_estimate", "eps_actual")


def empty_earnings_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=list(EARNINGS_COLUMNS))


class EarningsProvider(Protocol):
    """Earnings calendar source (past and announced future dates)."""

    name: str

    def fetch_earnings(self, symbol: str) -> pd.DataFrame: ...
