"""yfinance earnings-calendar adapter.

normalize_earnings() is pure. Time-of-day is inferred from the event
timestamp (before noon exchange-local = BMO, after = AMC, midnight =
unknown). yfinance's calendar is spotty — the append-only observation
model upstream is what makes that survivable."""

import pandas as pd

from mip.core.exceptions import TransientError
from mip.providers.base import EARNINGS_COLUMNS, empty_earnings_frame


def _time_of_day(ts: pd.Timestamp) -> str:
    if ts.hour == 0 and ts.minute == 0:
        return "unknown"
    return "BMO" if ts.hour < 12 else "AMC"


def normalize_earnings(raw: pd.DataFrame | None) -> pd.DataFrame:
    """Map a yfinance get_earnings_dates() frame onto EARNINGS_COLUMNS."""
    if raw is None or raw.empty:
        return empty_earnings_frame()

    records: list[dict[str, object]] = []
    for ts, row in raw.iterrows():
        estimate = row.get("EPS Estimate")
        actual = row.get("Reported EPS")
        records.append(
            {
                "earnings_date": ts.date(),
                "time_of_day": _time_of_day(ts),
                "eps_estimate": float(estimate) if pd.notna(estimate) else float("nan"),
                "eps_actual": float(actual) if pd.notna(actual) else float("nan"),
            }
        )
    frame = pd.DataFrame(records)
    # one state per earnings_date per fetch: keep the first (yfinance
    # occasionally duplicates the row for the same event)
    frame = frame.drop_duplicates(subset="earnings_date", keep="first")
    frame = frame.sort_values("earnings_date").reset_index(drop=True)
    return frame[list(EARNINGS_COLUMNS)]


class YFinanceEarningsProvider:
    name = "yfinance"

    def fetch_earnings(self, symbol: str) -> pd.DataFrame:
        import yfinance as yf

        try:
            raw = yf.Ticker(symbol).get_earnings_dates(limit=24)
        except Exception as exc:
            raise TransientError(f"yfinance earnings fetch failed for {symbol}: {exc}") from exc
        return normalize_earnings(raw)
