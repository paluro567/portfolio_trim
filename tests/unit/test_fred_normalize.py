"""normalize_series() contract tests — no network, fixture Series shaped
like fredapi get_series() output."""

from datetime import date

import pandas as pd

from mip.providers.base import MACRO_COLUMNS
from mip.providers.fred.macro import normalize_series


def fred_series() -> pd.Series:
    index = pd.DatetimeIndex(
        [pd.Timestamp("2026-06-01"), pd.Timestamp("2026-06-02"), pd.Timestamp("2026-06-03")]
    )
    return pd.Series([4.2, float("nan"), 4.25], index=index)  # NaN = FRED '.'


def test_maps_to_contract_columns() -> None:
    frame = normalize_series(fred_series())

    assert list(frame.columns) == list(MACRO_COLUMNS)
    assert list(frame["obs_date"]) == [date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 3)]


def test_missing_marker_preserved_as_nan_not_zero() -> None:
    frame = normalize_series(fred_series())

    assert pd.isna(frame["value"].iloc[1])  # '.' stays NaN -> stored NULL
    assert frame["value"].iloc[0] == 4.2
    assert frame["value"].iloc[2] == 4.25


def test_sorts_and_dedupes() -> None:
    index = pd.DatetimeIndex(
        [pd.Timestamp("2026-06-03"), pd.Timestamp("2026-06-01"), pd.Timestamp("2026-06-01")]
    )
    frame = normalize_series(pd.Series([4.3, 4.1, 9.9], index=index))

    assert list(frame["obs_date"]) == [date(2026, 6, 1), date(2026, 6, 3)]
    assert frame["value"].iloc[0] == 4.1  # first occurrence kept


def test_empty_and_none_inputs() -> None:
    assert normalize_series(None).empty
    assert normalize_series(pd.Series(dtype=float)).empty
    assert list(normalize_series(None).columns) == list(MACRO_COLUMNS)
