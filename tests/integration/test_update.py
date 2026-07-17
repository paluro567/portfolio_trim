"""Daily Update Orchestrator against Postgres: full runs with fake
ingestion services (no live providers), idempotent reruns, partial and
critical failures, resume, locking, and the single assessment pass."""

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text
from typer.testing import CliRunner

from mip.core.config import Settings
from mip.core.db import session_scope
from mip.domain.enums import RunStatus, RunType
from mip.domain.models import IngestionRun, Prediction
from mip.repositories.ingestion_runs import IngestionRunRepository
from mip.update.market import EASTERN
from mip.update.orchestrator import ADVISORY_LOCK_KEY, UpdateOrchestrator, UpdateServices
from tests.integration.test_decision_evidence import build_features
from tests.integration.test_portfolio import (
    START,
    TODAY,
    import_everything,
    portfolio_env,  # noqa: F401
)
from tests.integration.test_research_engine import restore_logging  # noqa: F401

pytestmark = pytest.mark.integration

AFTER_CLOSE = datetime(TODAY.year, TODAY.month, TODAY.day, 20, 0, tzinfo=EASTERN)


class FakeIngest:
    """Stands in for any ingestion service: records a real child run and
    returns configurable outcomes — never touches a live provider."""

    def __init__(self, session, run_type, *, fail_symbols=(), explode=False):
        self._runs = IngestionRunRepository(session)
        self._run_type = run_type
        self._fail = tuple(fail_symbols)
        self._explode = explode

    def ingest(self, symbols=None):
        if self._explode:
            raise RuntimeError("provider unreachable")
        run = self._runs.start(self._run_type, "fake", "ALL")
        outcomes = [
            SimpleNamespace(symbol="AAA", error="boom" if "AAA" in self._fail else None),
            SimpleNamespace(symbol="BBB", error="boom" if "BBB" in self._fail else None),
        ]
        status = RunStatus.PARTIAL if self._fail else RunStatus.SUCCESS
        self._runs.complete(run, status, rows_inserted=0, rows_updated=0)
        return run, outcomes


def fakes(*, prices_fail=(), prices_explode=False) -> UpdateServices:
    return UpdateServices(
        prices=lambda s, cfg: FakeIngest(
            s, RunType.PRICES, fail_symbols=prices_fail, explode=prices_explode
        ),
        macro=lambda s, cfg: FakeIngest(s, RunType.MACRO),
        fundamentals=lambda s, cfg: FakeIngest(s, RunType.FUNDAMENTALS),
        earnings=lambda s, cfg: FakeIngest(s, RunType.EARNINGS),
    )


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url="postgresql+psycopg://ignored/ignored",
        rawdata_root=tmp_path,
        history_start_date=START,
        default_portfolio="main",
        report_root=tmp_path / "reports",
        _env_file=None,
    )


def make_orchestrator(factory, tmp_path, services=None) -> UpdateOrchestrator:
    return UpdateOrchestrator(
        factory, make_settings(tmp_path), services or fakes(), now=lambda: AFTER_CLOSE
    )


def prediction_count(factory) -> int:
    with session_scope(factory) as session:
        return len(session.scalars(select(Prediction.id)).all())


def prepare(portfolio_env, tmp_path) -> None:
    import_everything(portfolio_env, tmp_path)
    build_features(portfolio_env, tmp_path)


def test_full_run_success_then_idempotent_rerun(portfolio_env, tmp_path) -> None:
    prepare(portfolio_env, tmp_path)
    orch = make_orchestrator(portfolio_env, tmp_path)
    result = orch.run()

    assert result.status == "success", result.warnings
    executed = {n: r["status"] for n, r in result.stages.items()}
    assert set(executed.values()) == {"success"}
    assert list(result.stages) == list(executed)  # ordered stage records
    assert result.predictions_archived == 12  # 2 symbols x 6 horizons
    assert result.outcomes_evaluated == 0  # same-day predictions cannot be matured

    base = Path(result.report_directory)
    assert (base / "portfolio" / "main.md").is_file()
    assert (base / "portfolio" / "main.json").is_file()
    assert (base / "symbols" / "AAA.md").is_file()
    manifest = json.loads((base / "run_manifest.json").read_text())
    assert manifest["status"] == "success"
    assert "postgresql" not in json.dumps(manifest).lower()

    with session_scope(portfolio_env) as session:
        run = session.get(IngestionRun, result.run_id)
        assert run.run_type is RunType.UPDATE and run.status is RunStatus.SUCCESS
        assert run.scope == "main" and run.archive_path == str(base)

    # same resolved date again: refused without --force ...
    again = make_orchestrator(portfolio_env, tmp_path).run()
    assert again.status == "skipped" and again.run_id is None

    # ... and fully idempotent with it.
    before = prediction_count(portfolio_env)
    forced = make_orchestrator(portfolio_env, tmp_path).run(force=True)
    assert forced.status == "success"
    assert forced.predictions_archived == 0  # immutable archive deduped everything
    assert prediction_count(portfolio_env) == before
    assert forced.stages["portfolio"]["detail"]["snapshot_rows_changed"] == 0


def test_partial_prices_do_not_block_healthy_symbols(portfolio_env, tmp_path) -> None:
    prepare(portfolio_env, tmp_path)
    orch = make_orchestrator(portfolio_env, tmp_path, fakes(prices_fail=("BBB",)))
    result = orch.run()
    assert result.stages["prices"]["status"] == "partial"
    assert result.stages["features"]["status"] == "success"  # proceeded
    assert result.stages["assess"]["status"] == "success"
    assert result.status == "partial"


def test_critical_failure_skips_dependents_and_resume_completes(portfolio_env, tmp_path) -> None:
    prepare(portfolio_env, tmp_path)
    broken = make_orchestrator(portfolio_env, tmp_path, fakes(prices_explode=True))
    failed = broken.run()
    assert failed.status == "failed"
    assert failed.stages["prices"]["status"] == "failed"
    assert failed.stages["prices"]["attempts"] == 2  # one retry, then fail
    for dependent in ("features", "portfolio", "assess", "reports", "archive", "evaluate"):
        assert failed.stages[dependent]["status"] == "skipped"
    assert failed.stages["macro"]["status"] == "success"  # independent stage unharmed

    resumed = make_orchestrator(portfolio_env, tmp_path).run(resume_run_id=failed.run_id)
    assert resumed.run_id == failed.run_id  # same audit row
    assert resumed.status == "success"
    # completed stages carry their ORIGINAL audit records forward
    assert resumed.stages["macro"]["status"] == "success"
    assert resumed.stages["macro"]["resumed"] == "completed in original run"
    assert "run_id" in resumed.stages["macro"]["detail"]
    assert resumed.stages["prices"]["status"] == "success"
    assert resumed.stages["assess"]["status"] == "success"
    with session_scope(portfolio_env) as session:
        assert session.get(IngestionRun, failed.run_id).status is RunStatus.SUCCESS


def test_concurrent_runs_are_locked_out(portfolio_env, tmp_path) -> None:
    prepare(portfolio_env, tmp_path)
    holder = portfolio_env()
    try:
        got = holder.execute(
            text("SELECT pg_try_advisory_lock(:k)"), {"k": ADVISORY_LOCK_KEY}
        ).scalar()
        assert got is True
        result = make_orchestrator(portfolio_env, tmp_path).run()
        assert result.status == "failed"
        assert any("update lock" in w for w in result.warnings)
    finally:
        holder.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": ADVISORY_LOCK_KEY})
        holder.close()


def test_models_run_exactly_once_per_symbol(portfolio_env, tmp_path, monkeypatch) -> None:
    prepare(portfolio_env, tmp_path)
    from mip.models.rates import InterestRateModel

    calls: list[str] = []
    original = InterestRateModel.evaluate

    def counting(self, symbol, as_of=None):
        calls.append(symbol)
        return original(self, symbol, as_of=as_of)

    monkeypatch.setattr(InterestRateModel, "evaluate", counting)
    result = make_orchestrator(portfolio_env, tmp_path).run()
    assert result.status == "success"
    # one assessed() pass feeds trim + attribution + reports + archive
    assert sorted(calls) == ["AAA", "BBB"]


def test_dry_run_plans_without_writing(portfolio_env, tmp_path) -> None:
    prepare(portfolio_env, tmp_path)
    result = make_orchestrator(portfolio_env, tmp_path).run(
        dry_run=True, skip={"macro"}, from_stage="features"
    )
    assert result.status == "dry-run" and result.run_id is None
    assert result.stages["prices"]["detail"]["reason"] == "outside stage window"
    assert result.stages["features"]["status"] == "planned"
    assert not (tmp_path / "reports").exists()
    with session_scope(portfolio_env) as session:
        update_runs = session.scalars(
            select(IngestionRun).where(IngestionRun.run_type == RunType.UPDATE)
        ).all()
        assert update_runs == []


def test_cli_dry_run_table_and_json(
    portfolio_env, tmp_path, monkeypatch, test_database_url, restore_logging
) -> None:
    prepare(portfolio_env, tmp_path)
    monkeypatch.setenv("MIP_DATABASE_URL", test_database_url)
    monkeypatch.setenv("MIP_DEFAULT_PORTFOLIO", "main")
    monkeypatch.setenv("MIP_REPORT_ROOT", str(tmp_path / "cli-reports"))
    from mip.cli.main import app

    runner = CliRunner()
    table = runner.invoke(app, ["update", "--dry-run"])
    assert table.exit_code == 0, table.output
    assert "[dry-run]" in table.output and "assess" in table.output

    as_json = runner.invoke(app, ["update", "--dry-run", "--only", "prices", "--json"])
    assert as_json.exit_code == 0, as_json.output
    payload = json.loads(as_json.output[as_json.output.index("{") :])
    assert payload["status"] == "dry-run"
    assert payload["stages"]["prices"]["status"] == "planned"
    assert payload["stages"]["features"]["detail"]["reason"] == "outside stage window"

    conflict = runner.invoke(app, ["update", "--only", "prices", "--from-stage", "features"])
    assert conflict.exit_code == 2
