"""Application settings (Pydantic Settings).

All configuration comes from the environment or a .env file, prefixed
MIP_. Secrets never live in code. Missing required settings fail loudly
at startup via ConfigurationError.
"""

from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from mip.core.exceptions import ConfigurationError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MIP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    fred_api_key: str | None = None
    rawdata_root: Path = Path("RawData")
    history_start_date: date = date(2010, 1, 1)
    retry_max_attempts: int = 4
    retry_backoff_seconds: float = 1.0
    log_format: Literal["console", "json"] = "console"

    # Ingestion (Phase 2)
    overlap_trading_days: int = 10  # re-fetched each run for revision detection
    return_jump_threshold: float = 0.40  # |daily return| above this w/o corp action -> error
    stale_close_run_length: int = 5  # N identical consecutive closes -> warning

    # Features (Phase 5): trailing window recomputed each run so upstream
    # price/macro revisions propagate into stored features.
    feature_rebuild_overlap_sessions: int = 30

    # Daily update orchestrator
    default_portfolio: str = "Peter Real Portfolio"
    report_root: Path = Path("data/reports")
    market_close_buffer_minutes: int = 90  # NYSE close + provider availability
    update_macro_daily: bool = True
    update_fundamentals_daily: bool = True
    update_earnings_daily: bool = True
    stage_retry_limit: int = 1  # extra attempts per stage on transient errors
    update_lock_timeout_seconds: int = 0  # 0 = fail immediately if locked


def get_settings(env_file: str | Path | None = ".env") -> Settings:
    """Load settings, converting validation failures into a readable error."""
    try:
        return Settings(_env_file=env_file)
    except ValidationError as exc:
        missing = ", ".join(
            "MIP_" + str(err["loc"][0]).upper() for err in exc.errors() if err["type"] == "missing"
        )
        detail = f"missing required settings: {missing}" if missing else str(exc)
        raise ConfigurationError(
            f"Invalid configuration — {detail}. See .env.example for reference."
        ) from exc
