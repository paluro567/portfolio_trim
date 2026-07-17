"""Daily Update Orchestrator: market-date resolution, stage planning,
status aggregation, and manifest sanitization — pure logic, no database."""

import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from mip.core.config import Settings
from mip.core.exceptions import ConfigurationError
from mip.update.market import EASTERN, resolve_market_date
from mip.update.orchestrator import STAGE_ORDER, UpdateOrchestrator, UpdateResult

UTC = ZoneInfo("UTC")

# Mon 13th – Fri 17th July 2026, with Wed 15th a holiday, plus prior Friday.
SESSIONS = [
    date(2026, 7, 10),
    date(2026, 7, 13),
    date(2026, 7, 14),
    date(2026, 7, 16),
    date(2026, 7, 17),
]
BUFFER = 90  # cutoff 17:30 ET


def eastern(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=EASTERN)


def settings(**overrides) -> Settings:
    return Settings(database_url="postgresql+psycopg://unit/test", _env_file=None, **overrides)


# -- market-date resolution ----------------------------------------------------------


def test_before_close_uses_previous_session() -> None:
    now = eastern(date(2026, 7, 14), 10)  # Tuesday morning
    assert resolve_market_date(SESSIONS, now, BUFFER) == date(2026, 7, 13)


def test_before_buffer_expires_still_previous_session() -> None:
    now = eastern(date(2026, 7, 14), 17, 29)  # after close, inside the buffer
    assert resolve_market_date(SESSIONS, now, BUFFER) == date(2026, 7, 13)


def test_after_close_plus_buffer_uses_today() -> None:
    now = eastern(date(2026, 7, 14), 17, 31)
    assert resolve_market_date(SESSIONS, now, BUFFER) == date(2026, 7, 14)


def test_weekend_resolves_to_friday() -> None:
    now = eastern(date(2026, 7, 18), 12)  # Saturday
    assert resolve_market_date(SESSIONS, now, BUFFER) == date(2026, 7, 17)


def test_holiday_resolves_to_prior_session() -> None:
    now = eastern(date(2026, 7, 15), 10)  # holiday Wednesday, not a session
    assert resolve_market_date(SESSIONS, now, BUFFER) == date(2026, 7, 14)


def test_utc_input_is_converted() -> None:
    # 20:00 UTC on Tue 14th = 16:00 ET — before the 17:30 cutoff.
    now = datetime(2026, 7, 14, 20, 0, tzinfo=UTC)
    assert resolve_market_date(SESSIONS, now, BUFFER) == date(2026, 7, 13)


def test_explicit_as_of_resolves_to_last_session() -> None:
    now = eastern(date(2026, 7, 17), 20)
    assert resolve_market_date(SESSIONS, now, BUFFER, as_of=date(2026, 7, 15)) == date(2026, 7, 14)
    assert resolve_market_date(SESSIONS, now, BUFFER, as_of=date(2026, 7, 18)) == date(2026, 7, 17)


def test_resolution_errors_are_explicit() -> None:
    with pytest.raises(ConfigurationError, match="calendar is empty"):
        resolve_market_date([], eastern(date(2026, 7, 14), 18), BUFFER)
    with pytest.raises(ConfigurationError, match="no trading session"):
        resolve_market_date(
            SESSIONS, eastern(date(2026, 7, 14), 18), BUFFER, as_of=date(2026, 7, 9)
        )
    with pytest.raises(ConfigurationError, match="no completed trading session"):
        resolve_market_date([date(2026, 7, 20)], eastern(date(2026, 7, 14), 18), BUFFER)


# -- stage planning ------------------------------------------------------------------


def orchestrator() -> UpdateOrchestrator:
    return UpdateOrchestrator(session_factory=None, settings=settings())


def test_stage_windows() -> None:
    orch = orchestrator()
    assert orch._selected_stages(None, None) == STAGE_ORDER
    from_features = orch._selected_stages("features", None)
    assert from_features == ("preflight", "market_date") + STAGE_ORDER[6:]
    only_prices = orch._selected_stages("prices", "prices")
    assert only_prices == ("preflight", "market_date", "prices")
    with pytest.raises(ConfigurationError, match="unknown stage"):
        orch.run(from_stage="nope")


def test_dependency_blocking() -> None:
    orch = orchestrator()
    result = UpdateResult(
        run_id=1, status="running", portfolio="p", requested_as_of=None, resolved_market_date=None
    )
    result.stages["prices"] = {"status": "failed"}
    assert orch._failed_dependency(result, "features") == "prices"
    result.stages["prices"] = {"status": "partial"}  # healthy symbols proceed
    assert orch._failed_dependency(result, "features") is None
    result.stages["features"] = {"status": "success"}
    assert orch._failed_dependency(result, "assess") == "portfolio"  # not yet run


def test_status_aggregation() -> None:
    orch = orchestrator()

    def result_with(statuses: dict[str, str]) -> UpdateResult:
        r = UpdateResult(
            run_id=1,
            status="running",
            portfolio="p",
            requested_as_of=None,
            resolved_market_date="2026-07-16",
        )
        r.stages = {name: {"status": status} for name, status in statuses.items()}
        return r

    ok = result_with({"prices": "success", "assess": "success"})
    orch._finalize(ok)
    assert ok.status == "success"

    soft = result_with({"prices": "success", "macro": "failed", "assess": "success"})
    orch._finalize(soft)
    assert soft.status == "partial"  # non-critical failure

    hard = result_with({"prices": "failed", "features": "skipped"})
    orch._finalize(hard)
    assert hard.status == "failed"  # critical failure

    per_symbol = result_with({"prices": "partial", "assess": "success"})
    orch._finalize(per_symbol)
    assert per_symbol.status == "partial"


def test_manifest_is_sanitized_and_json_safe() -> None:
    result = UpdateResult(
        run_id=9,
        status="success",
        portfolio="Peter Real Portfolio",
        requested_as_of=None,
        resolved_market_date="2026-07-16",
    )
    result.stages["prices"] = {"status": "success", "detail": {"rows_inserted": 5}}
    payload = json.dumps(result.manifest())
    assert json.loads(payload)["versions"]["trim_engine"] == 1
    for secret in ("postgresql", "database_url", "api_key", "password"):
        assert secret not in payload.lower()
