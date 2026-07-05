from mip.providers.base import FUNDAMENTAL_FIELDS
from mip.providers.yfinance.fundamentals import normalize_info

INFO = {
    "marketCap": 3_200_000_000_000,
    "trailingPE": 33.5,
    "forwardPE": 29.1,
    "priceToBook": 48.2,
    "trailingEps": 6.42,
    "forwardEps": 7.10,
    "dividendYield": 0.0055,
    "beta": 1.24,
    "sharesOutstanding": 15_200_000_000,
    "totalRevenue": 391_000_000_000,
    "profitMargins": 0.2531,
    "debtToEquity": 154.5,
}


def test_maps_all_contract_fields() -> None:
    snapshot = normalize_info(INFO)

    assert set(snapshot) == set(FUNDAMENTAL_FIELDS)
    assert snapshot["market_cap"] == 3_200_000_000_000
    assert snapshot["trailing_pe"] == 33.5
    assert snapshot["shares_outstanding"] == 15_200_000_000
    assert snapshot["revenue_ttm"] == 391_000_000_000
    assert snapshot["profit_margin"] == 0.2531


def test_missing_keys_become_none() -> None:
    snapshot = normalize_info({"marketCap": 1_000_000})

    assert snapshot["market_cap"] == 1_000_000
    assert snapshot["trailing_pe"] is None
    assert snapshot["beta"] is None


def test_non_numeric_and_nan_become_none() -> None:
    snapshot = normalize_info({"trailingPE": "Infinity", "beta": float("nan"), "marketCap": None})
    assert snapshot["trailing_pe"] is None
    assert snapshot["beta"] is None
    assert snapshot["market_cap"] is None


def test_empty_and_none_inputs() -> None:
    assert all(v is None for v in normalize_info({}).values())
    assert all(v is None for v in normalize_info(None).values())
