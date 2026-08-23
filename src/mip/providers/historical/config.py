"""Credentials and configuration for historical providers.

The key is read at call time from the environment, falling back to ``./.env``
for consistency with the rest of the platform. It is never stored on a
serialisable object, never logged, and never required by a unit test —
``tests/unit/conftest.py`` neutralises the ``.env`` fallback for the whole unit
suite.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_KEY_ENV = "SHARADAR_API_KEY"

# Nasdaq Data Link table codes. Declared here so the rest of the application
# never spells a vendor table name.
SHARADAR_TABLES = {
    "tickers": "SHARADAR/TICKERS",
    "prices": "SHARADAR/SEP",
    "fundamentals": "SHARADAR/SF1",
    "actions": "SHARADAR/ACTIONS",
    "daily_metrics": "SHARADAR/DAILY",
    "sp500": "SHARADAR/SP500",
    "events": "SHARADAR/EVENTS",
    "fund_prices": "SHARADAR/SFP",
}


def _dotenv(name: str) -> str | None:
    """Read one value from ``./.env``. Never logged. Mirrors mip.core.config."""
    path = Path(".env")
    if not path.is_file():
        return None
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() != name:
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            return value or None
    except OSError:
        return None
    return None


def _env(name: str) -> str | None:
    raw = os.environ.get(name)
    if raw is not None and raw.strip():
        return raw
    return _dotenv(name)


@dataclass(frozen=True, slots=True)
class HistoricalProviderSettings:
    """Everything the ingestion layer needs except the secret itself."""

    provider: str
    api_key_present: bool
    base_url: str

    @property
    def configured(self) -> bool:
        return self.api_key_present

    def blocked_reason(self) -> str | None:
        if not self.api_key_present:
            return f"{_KEY_ENV} is not set; no historical provider is configured"
        return None

    def to_dict(self) -> dict:
        """Serialisable form. Deliberately contains no secret."""
        return {
            "api_key_present": self.api_key_present,
            "base_url": self.base_url,
            "provider": self.provider,
        }


def load_provider_settings() -> HistoricalProviderSettings:
    key = _env(_KEY_ENV) or ""
    return HistoricalProviderSettings(
        provider=(_env("MIP_HISTORICAL_PROVIDER") or "sharadar").strip().lower(),
        api_key_present=bool(key.strip()),
        base_url=(_env("SHARADAR_BASE_URL") or "https://data.nasdaq.com/api/v3").strip(),
    )


def read_api_key() -> str | None:
    """Fetch the key at call time. Callers must never store or log the result."""
    key = (_env(_KEY_ENV) or "").strip()
    return key or None
