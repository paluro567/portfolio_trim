"""normalize_history() contract tests — no network, fixture frames shaped
like yfinance history() output."""

from datetime import date

import pandas as pd

from mip.providers.base import ACTION_COLUMNS, PRICE_COLUMNS
from mip.providers.yfinance.prices import normalize_history


def yf_frame() -> pd.DataFrame:
    index = pd.DatetimeIndex(
        [
            pd.Timestamp("2026-06-01", tz="America/New_York"),
            pd.Timestamp("2026-06-02", tz="America/New_York"),
            pd.Timestamp("2026-06-03", tz="America/New_York"),
        ]
    )
    return pd.DataFrame(
        {
            "Open": [99.0, 100.0, float("nan")],
            "High": [101.0, 102.0, float("nan")],
            "Low": [98.0, 99.5, float("nan")],
            "Close": [100.0, 101.5, float("nan")],  # last row: stray all-NaN
            "Adj Close": [99.0, 100.5, float("nan")],
            "Volume": [1_000_000, 1_100_000, float("nan")],
            "Dividends": [0.0, 0.25, 0.0],
            "Stock Splits": [0.0, 0.0, 0.0],
        },
        index=index,
    )


def test_maps_columns_and_strips_timezone() -> None:
    fetch = normalize_history(yf_frame())

    assert list(fetch.prices.columns) == list(PRICE_COLUMNS)
    assert list(fetch.prices["price_date"]) == [date(2026, 6, 1), date(2026, 6, 2)]
    assert fetch.prices["close"].tolist() == [100.0, 101.5]
    assert fetch.prices["adj_close"].tolist() == [99.0, 100.5]


def test_drops_stray_all_nan_rows() -> None:
    fetch = normalize_history(yf_frame())
    assert len(fetch.prices) == 2  # NaN-close row removed


def test_extracts_dividend_actions() -> None:
    fetch = normalize_history(yf_frame())

    assert list(fetch.actions.columns) == list(ACTION_COLUMNS)
    assert len(fetch.actions) == 1
    action = fetch.actions.iloc[0]
    assert action["action_type"] == "dividend"
    assert action["ex_date"] == date(2026, 6, 2)
    assert action["cash_amount"] == 0.25


def test_extracts_split_actions() -> None:
    raw = yf_frame()
    raw.loc[raw.index[0], "Stock Splits"] = 4.0
    fetch = normalize_history(raw)

    splits = fetch.actions[fetch.actions["action_type"] == "split"]
    assert len(splits) == 1
    assert splits.iloc[0]["ex_date"] == date(2026, 6, 1)
    assert splits.iloc[0]["split_ratio"] == 4.0


def test_empty_input_yields_empty_contract_frames() -> None:
    fetch = normalize_history(pd.DataFrame())
    assert fetch.prices.empty and list(fetch.prices.columns) == list(PRICE_COLUMNS)
    assert fetch.actions.empty and list(fetch.actions.columns) == list(ACTION_COLUMNS)
