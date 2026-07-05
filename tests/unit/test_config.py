from datetime import date
from pathlib import Path

import pytest

from mip.core.config import Settings, get_settings
from mip.core.exceptions import ConfigurationError

DSN = "postgresql+psycopg://user:pw@localhost:5432/mip"


def test_loads_from_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)  # no stray .env
    monkeypatch.setenv("MIP_DATABASE_URL", DSN)
    monkeypatch.setenv("MIP_RETRY_MAX_ATTEMPTS", "7")
    monkeypatch.setenv("MIP_HISTORY_START_DATE", "2012-06-01")

    settings = get_settings(env_file=None)

    assert settings.database_url == DSN
    assert settings.retry_max_attempts == 7
    assert settings.history_start_date == date(2012, 6, 1)
    assert settings.log_format == "console"  # default


def test_loads_from_env_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("MIP_DATABASE_URL", raising=False)
    (tmp_path / ".env").write_text(f"MIP_DATABASE_URL={DSN}\nMIP_LOG_FORMAT=json\n")
    monkeypatch.chdir(tmp_path)

    settings = get_settings()

    assert settings.database_url == DSN
    assert settings.log_format == "json"


def test_environment_overrides_env_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("MIP_DATABASE_URL=postgresql+psycopg://file@h/db\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MIP_DATABASE_URL", DSN)

    assert get_settings().database_url == DSN


def test_missing_required_setting_fails_loudly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MIP_DATABASE_URL", raising=False)

    with pytest.raises(ConfigurationError, match="MIP_DATABASE_URL"):
        get_settings(env_file=None)


def test_invalid_log_format_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MIP_DATABASE_URL", DSN)
    monkeypatch.setenv("MIP_LOG_FORMAT", "xml")

    with pytest.raises(ConfigurationError):
        get_settings(env_file=None)


def test_defaults_are_sane() -> None:
    settings = Settings(database_url=DSN, _env_file=None)
    assert settings.rawdata_root == Path("RawData")
    assert settings.retry_max_attempts == 4
    assert settings.retry_backoff_seconds == 1.0
    assert settings.fred_api_key is None
