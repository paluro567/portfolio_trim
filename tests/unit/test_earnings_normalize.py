from datetime import date

import pandas as pd

from mip.providers.base import EARNINGS_COLUMNS
from mip.providers.yfinance.earnings import normalize_earnings


def yf_earnings() -> pd.DataFrame:
    index = pd.DatetimeIndex(
        [
            pd.Timestamp("2026-07-30 16:30:00", tz="America/New_York"),  # AMC
            pd.Timestamp("2026-04-29 08:00:00", tz="America/New_York"),  # BMO
            pd.Timestamp("2026-10-28 00:00:00", tz="America/New_York"),  # unknown
        ]
    )
    return pd.DataFrame(
        {
            "EPS Estimate": [1.55, 1.42, float("nan")],
            "Reported EPS": [float("nan"), 1.47, float("nan")],
        },
        index=index,
    )


def test_maps_to_contract_sorted() -> None:
    frame = normalize_earnings(yf_earnings())

    assert list(frame.columns) == list(EARNINGS_COLUMNS)
    assert list(frame["earnings_date"]) == [
        date(2026, 4, 29),
        date(2026, 7, 30),
        date(2026, 10, 28),
    ]


def test_time_of_day_inferred() -> None:
    frame = normalize_earnings(yf_earnings())
    by_date = dict(zip(frame["earnings_date"], frame["time_of_day"], strict=True))

    assert by_date[date(2026, 4, 29)] == "BMO"
    assert by_date[date(2026, 7, 30)] == "AMC"
    assert by_date[date(2026, 10, 28)] == "unknown"


def test_reported_and_estimate_nan_preserved() -> None:
    frame = normalize_earnings(yf_earnings())
    april = frame[frame["earnings_date"] == date(2026, 4, 29)].iloc[0]
    july = frame[frame["earnings_date"] == date(2026, 7, 30)].iloc[0]

    assert april["eps_actual"] == 1.47  # reported -> happened
    assert pd.isna(july["eps_actual"])  # future -> NaN


def test_duplicate_event_rows_deduped() -> None:
    raw = yf_earnings()
    doubled = pd.concat([raw, raw.head(1)])
    frame = normalize_earnings(doubled)
    assert list(frame["earnings_date"]).count(date(2026, 7, 30)) == 1


def test_empty_input() -> None:
    frame = normalize_earnings(None)
    assert frame.empty and list(frame.columns) == list(EARNINGS_COLUMNS)
