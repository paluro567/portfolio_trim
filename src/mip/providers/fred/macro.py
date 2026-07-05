"""FRED macro adapter — the ONLY module that imports fredapi.

normalize_series() is a pure function so the mapping is unit-testable
without network. fredapi already converts FRED's '.' missing-value marker
to NaN; NaN is preserved here and stored as NULL downstream (never zero).
"""

from datetime import date

import pandas as pd

from mip.core.exceptions import ConfigurationError, PermanentError, TransientError
from mip.providers.base import MACRO_COLUMNS, empty_macro_frame


def normalize_series(raw: pd.Series | None) -> pd.DataFrame:
    """Map a fredapi get_series() result onto the MACRO_COLUMNS contract."""
    if raw is None or raw.empty:
        return empty_macro_frame()
    frame = pd.DataFrame(
        {
            "obs_date": [ts.date() for ts in raw.index],
            "value": [float(v) if pd.notna(v) else float("nan") for v in raw.values],
        }
    )
    frame = frame.drop_duplicates(subset="obs_date", keep="first")
    frame = frame.sort_values("obs_date").reset_index(drop=True)
    return frame[list(MACRO_COLUMNS)]


class FredMacroProvider:
    name = "FRED"

    def __init__(self, api_key: str | None) -> None:
        if not api_key:
            raise ConfigurationError(
                "MIP_FRED_API_KEY is not set — get a free key at "
                "https://fred.stlouisfed.org/docs/api/api_key.html"
            )
        self._api_key = api_key

    def fetch_series(self, provider_code: str, start: date, end: date) -> pd.DataFrame:
        from fredapi import Fred

        client = Fred(api_key=self._api_key)
        try:
            raw = client.get_series(provider_code, observation_start=start, observation_end=end)
        except ValueError as exc:
            # fredapi raises ValueError for bad series ids / bad requests
            raise PermanentError(f"FRED rejected series {provider_code}: {exc}") from exc
        except Exception as exc:
            raise TransientError(f"FRED fetch failed for {provider_code}: {exc}") from exc
        return normalize_series(raw)
