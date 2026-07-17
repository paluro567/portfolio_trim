"""Daily Update Orchestrator: one reliable `mip update`.

Orchestration only — every stage delegates to an existing, already
idempotent service; no statistical logic lives here. The assessment
stages share ONE AttributionEngine.assessed() pass whose in-memory
bundle feeds trim assessments, attribution, all reports, and the
prediction archive, so the seven intelligence models run exactly once
per symbol per update.

Stage graph (dependencies in brackets):

    preflight -> market_date
      -> prices | macro | fundamentals | earnings
      -> features [prices]   -> portfolio [prices]
      -> assess [features, portfolio]
      -> reports [assess]    -> archive [assess]
      -> evaluate [prices]

Audit: one ingestion_runs row with run_type='update' (scope = portfolio,
archive_path = report directory); the full stage manifest lives in its
JSONB detail column and in <report_dir>/run_manifest.json. Stage-level
child runs remain ordinary ingestion_runs rows, linked by id in the
manifest. Concurrency: a session-scoped Postgres advisory lock — a
crashed process releases it automatically (stale locks cannot outlive
their session).
"""

import json
import time as time_module
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from mip.core.config import Settings
from mip.core.exceptions import ConfigurationError
from mip.core.logging import get_logger
from mip.domain.enums import RunStatus, RunType
from mip.domain.models import IngestionRun, TradingDay
from mip.update.market import now_eastern, resolve_market_date

logger = get_logger(__name__)

STAGE_ORDER = (
    "preflight",
    "market_date",
    "prices",
    "macro",
    "fundamentals",
    "earnings",
    "features",
    "portfolio",
    "assess",
    "reports",
    "archive",
    "evaluate",
)
DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "features": ("prices",),
    "portfolio": ("prices",),
    "assess": ("features", "portfolio"),
    "reports": ("assess",),
    "archive": ("assess",),
    "evaluate": ("prices",),
}
CRITICAL_STAGES = {"preflight", "prices", "features", "portfolio", "assess"}
ADVISORY_LOCK_KEY = 0x6D697075  # 'mipu'


def _utcnow() -> str:
    return datetime.now(tz=UTC).isoformat()


@dataclass
class UpdateServices:
    """Injectable stage-service builders (tests pass fakes; defaults are
    the exact wiring the existing CLI commands use)."""

    prices: Callable[[Session, Settings], Any] = None  # type: ignore[assignment]
    macro: Callable[[Session, Settings], Any] = None  # type: ignore[assignment]
    fundamentals: Callable[[Session, Settings], Any] = None  # type: ignore[assignment]
    earnings: Callable[[Session, Settings], Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.prices = self.prices or _real_prices
        self.macro = self.macro or _real_macro
        self.fundamentals = self.fundamentals or _real_fundamentals
        self.earnings = self.earnings or _real_earnings


def _real_prices(session: Session, settings: Settings):
    from mip.ingestion.archive import RawDataArchive
    from mip.ingestion.price_service import PriceIngestionService
    from mip.providers.yfinance.prices import YFinancePriceProvider

    return PriceIngestionService(
        session=session,
        provider=YFinancePriceProvider(),
        archive=RawDataArchive(settings.rawdata_root),
        settings=settings,
    )


def _real_macro(session: Session, settings: Settings):
    from mip.ingestion.archive import RawDataArchive
    from mip.ingestion.fred_service import MacroIngestionService
    from mip.providers.fred.macro import FredMacroProvider
    from mip.reference.macro_catalog import parse_macro_catalog

    return MacroIngestionService(
        session=session,
        provider=FredMacroProvider(settings.fred_api_key),
        archive=RawDataArchive(settings.rawdata_root),
        settings=settings,
        catalog=parse_macro_catalog(Path("fred_series.yaml")),
    )


def _real_fundamentals(session: Session, settings: Settings):
    from mip.ingestion.archive import RawDataArchive
    from mip.ingestion.fundamental_service import FundamentalIngestionService
    from mip.providers.yfinance.fundamentals import YFinanceFundamentalsProvider

    return FundamentalIngestionService(
        session=session,
        provider=YFinanceFundamentalsProvider(),
        archive=RawDataArchive(settings.rawdata_root),
        settings=settings,
    )


def _real_earnings(session: Session, settings: Settings):
    from mip.ingestion.archive import RawDataArchive
    from mip.ingestion.earnings_service import EarningsIngestionService
    from mip.providers.yfinance.earnings import YFinanceEarningsProvider

    return EarningsIngestionService(
        session=session,
        provider=YFinanceEarningsProvider(),
        archive=RawDataArchive(settings.rawdata_root),
        settings=settings,
    )


@dataclass
class UpdateResult:
    run_id: int | None
    status: str  # success | partial | failed | skipped | dry-run
    portfolio: str
    requested_as_of: str | None
    resolved_market_date: str | None
    stages: dict[str, dict[str, Any]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    report_directory: str | None = None
    predictions_archived: int = 0
    outcomes_evaluated: int = 0
    started_at: str = ""
    completed_at: str = ""

    def manifest(self) -> dict[str, Any]:
        from mip import __version__
        from mip.engine.attribution import ENGINE_VERSION as ATTRIBUTION_ENGINE
        from mip.engine.trim import ENGINE_VERSION as TRIM_ENGINE

        return {
            "run_id": self.run_id,
            "status": self.status,
            "portfolio": self.portfolio,
            "requested_as_of": self.requested_as_of,
            "resolved_market_date": self.resolved_market_date,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "stages": self.stages,
            "warnings": self.warnings,
            "report_directory": self.report_directory,
            "predictions_archived": self.predictions_archived,
            "outcomes_evaluated": self.outcomes_evaluated,
            "versions": {
                "mip": __version__,
                "trim_engine": TRIM_ENGINE,
                "attribution_engine": ATTRIBUTION_ENGINE,
            },
        }


class UpdateLock:
    """Postgres advisory lock held for the duration of one update run.
    Session-scoped: if the process dies, Postgres releases it — a stale
    lock cannot survive its connection."""

    def __init__(self, session: Session, timeout_seconds: int) -> None:
        self._session = session
        self._timeout = timeout_seconds
        self._held = False

    def acquire(self) -> None:
        deadline = time_module.monotonic() + self._timeout
        while True:
            got = self._session.execute(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": ADVISORY_LOCK_KEY}
            ).scalar()
            if got:
                self._held = True
                return
            if time_module.monotonic() >= deadline:
                raise ConfigurationError(
                    "another `mip update` run holds the update lock — wait for it "
                    "to finish (a crashed run releases the lock automatically)"
                )
            time_module.sleep(0.5)

    def release(self) -> None:
        if self._held:
            self._session.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": ADVISORY_LOCK_KEY}
            )
            self._held = False


class UpdateOrchestrator:
    def __init__(
        self,
        session_factory,
        settings: Settings,
        services: UpdateServices | None = None,
        now: Callable[[], datetime] = now_eastern,
    ) -> None:
        self._factory = session_factory
        self._settings = settings
        self._services = services or UpdateServices()
        self._now = now
        self._bundle: dict[str, list] | None = None  # the single assessed() pass
        self._resume_records: dict[str, dict] = {}  # original stage audit on resume

    # -- public ------------------------------------------------------------

    def run(
        self,
        portfolio: str | None = None,
        as_of: date | None = None,
        force: bool = False,
        resume_run_id: int | None = None,
        dry_run: bool = False,
        skip: set[str] | None = None,
        from_stage: str | None = None,
        to_stage: str | None = None,
    ) -> UpdateResult:
        from mip.core.db import session_scope

        settings = self._settings
        portfolio = portfolio or settings.default_portfolio
        skip = set(skip or set())
        if not settings.update_macro_daily:
            skip.add("macro")
        if not settings.update_fundamentals_daily:
            skip.add("fundamentals")
        if not settings.update_earnings_daily:
            skip.add("earnings")
        for name in (from_stage, to_stage):
            if name is not None and name not in STAGE_ORDER:
                raise ConfigurationError(
                    f"unknown stage {name!r}; stages: {', '.join(STAGE_ORDER)}"
                )
        selected = self._selected_stages(from_stage, to_stage)

        result = UpdateResult(
            run_id=None,
            status="running",
            portfolio=portfolio,
            requested_as_of=as_of.isoformat() if as_of else None,
            resolved_market_date=None,
            started_at=_utcnow(),
        )

        # preflight + market date run before the audit row can exist.
        completed_previously: set[str] = set()
        try:
            with session_scope(self._factory) as session:
                self._stage_preflight(session, result)
                resolved = self._stage_market_date(session, result, as_of)
                if resume_run_id is not None:
                    resolved, portfolio, completed_previously = self._load_resume(
                        session, resume_run_id, result
                    )
                    result.portfolio = portfolio
                elif (
                    not force
                    and not dry_run
                    and self._already_updated(session, portfolio, resolved)
                ):
                    result.status = "skipped"
                    result.resolved_market_date = resolved.isoformat()
                    result.completed_at = _utcnow()
                    result.warnings.append(
                        f"a successful update for {resolved.isoformat()} and this "
                        "portfolio already exists — use --force to rerun"
                    )
                    return result
                result.resolved_market_date = resolved.isoformat()
        except ConfigurationError as exc:
            self._record_failure(result, "preflight", str(exc))
            result.status = "failed"
            result.completed_at = _utcnow()
            return result

        if dry_run:
            self._plan_only(result, selected, skip, completed_previously)
            result.status = "dry-run"
            result.completed_at = _utcnow()
            return result

        lock_session = self._factory()
        lock = UpdateLock(lock_session, settings.update_lock_timeout_seconds)
        try:
            lock.acquire()
            run_id = self._open_run(resume_run_id, portfolio, resolved)
            result.run_id = run_id
            self._execute_stages(result, resolved, portfolio, selected, skip, completed_previously)
            self._finalize(result)
        except ConfigurationError as exc:
            result.warnings.append(str(exc))
            result.status = "failed"
            result.completed_at = _utcnow()
        finally:
            lock.release()
            lock_session.close()
        if result.run_id is not None:
            self._persist_manifest(result)
        return result

    # -- planning ------------------------------------------------------------

    def _selected_stages(self, from_stage: str | None, to_stage: str | None) -> tuple[str, ...]:
        start = STAGE_ORDER.index(from_stage) if from_stage else 0
        end = STAGE_ORDER.index(to_stage) if to_stage else len(STAGE_ORDER) - 1
        window = set(STAGE_ORDER[start : end + 1])
        window.update(("preflight", "market_date"))  # always run
        return tuple(s for s in STAGE_ORDER if s in window)

    def _plan_only(
        self,
        result: UpdateResult,
        selected: tuple[str, ...],
        skip: set[str],
        completed: set[str],
    ) -> None:
        for stage in STAGE_ORDER[2:]:
            if stage not in selected:
                record = {"status": "skipped", "detail": {"reason": "outside stage window"}}
            elif stage in skip:
                record = {"status": "skipped", "detail": {"reason": "skipped by flag/config"}}
            elif stage in completed:
                record = {"status": "skipped", "detail": {"reason": "completed in resumed run"}}
            else:
                record = {"status": "planned", "detail": {}}
            result.stages[stage] = record

    # -- audit row -----------------------------------------------------------

    def _already_updated(self, session: Session, portfolio: str, resolved: date) -> bool:
        rows = session.scalars(
            select(IngestionRun).where(
                IngestionRun.run_type == RunType.UPDATE,
                IngestionRun.status == RunStatus.SUCCESS,
                IngestionRun.scope == portfolio,
            )
        ).all()
        iso = resolved.isoformat()
        return any((r.error_detail or {}).get("resolved_market_date") == iso for r in rows)

    def _load_resume(
        self, session: Session, run_id: int, result: UpdateResult
    ) -> tuple[date, str, set[str]]:
        run = session.get(IngestionRun, run_id)
        if run is None or run.run_type != RunType.UPDATE:
            raise ConfigurationError(f"run {run_id} is not an update run")
        if run.status == RunStatus.SUCCESS:
            raise ConfigurationError(f"run {run_id} already succeeded — use --force for a rerun")
        manifest = run.error_detail or {}
        resolved_str = manifest.get("resolved_market_date")
        if not resolved_str:
            raise ConfigurationError(f"run {run_id} has no resumable manifest")
        completed = {
            name
            for name, record in (manifest.get("stages") or {}).items()
            if record.get("status") == "success"
        }
        # Carry the original run's audit forward: completed stage records
        # and the report directory survive into the consolidated manifest.
        self._resume_records = {
            name: dict(record)
            for name, record in (manifest.get("stages") or {}).items()
            if name in completed
        }
        result.report_directory = manifest.get("report_directory")
        result.predictions_archived = manifest.get("predictions_archived", 0)
        result.outcomes_evaluated = manifest.get("outcomes_evaluated", 0)
        result.warnings.append(f"resuming run {run_id}: skipping {sorted(completed)}")
        return (
            date.fromisoformat(resolved_str),
            run.scope or self._settings.default_portfolio,
            completed,
        )

    def _open_run(self, resume_run_id: int | None, portfolio: str, resolved: date) -> int:
        from mip.core.db import session_scope

        with session_scope(self._factory) as session:
            if resume_run_id is not None:
                run = session.get(IngestionRun, resume_run_id)
                run.status = RunStatus.RUNNING
                return run.id
            run = IngestionRun(run_type=RunType.UPDATE, provider="orchestrator", scope=portfolio)
            session.add(run)
            session.flush()
            run.error_detail = {"resolved_market_date": resolved.isoformat()}
            return run.id

    def _persist_manifest(self, result: UpdateResult) -> None:
        from mip.core.db import session_scope

        status = {
            "success": RunStatus.SUCCESS,
            "partial": RunStatus.PARTIAL,
            "failed": RunStatus.FAILED,
        }.get(result.status, RunStatus.FAILED)
        with session_scope(self._factory) as session:
            run = session.get(IngestionRun, result.run_id)
            run.status = status
            run.completed_at = datetime.now(tz=UTC)
            run.archive_path = result.report_directory
            run.error_detail = result.manifest()

    # -- stage engine ----------------------------------------------------------

    def _stage_preflight(self, session: Session, result: UpdateResult) -> None:
        started = time_module.monotonic()
        session.execute(text("SELECT 1"))
        head_note = self._check_migrations(session)
        record = {
            "status": "success",
            "seconds": round(time_module.monotonic() - started, 3),
            "detail": {"database": "ok", "migrations": head_note},
        }
        result.stages["preflight"] = record

    def _check_migrations(self, session: Session) -> str:
        from sqlalchemy import inspect as sqla_inspect

        if not sqla_inspect(session.get_bind()).has_table("alembic_version"):
            return "no alembic_version table (metadata-created schema) — head check skipped"
        db_version = session.execute(text("SELECT version_num FROM alembic_version")).scalar()
        root = next(
            (p for p in Path(__file__).resolve().parents if (p / "alembic.ini").is_file()), None
        )
        if root is None:
            return f"db at {db_version}; alembic.ini not found — head check skipped"
        from alembic.config import Config as AlembicConfig
        from alembic.script import ScriptDirectory

        cfg = AlembicConfig(str(root / "alembic.ini"))
        cfg.set_main_option("script_location", str(root / "alembic"))
        head = ScriptDirectory.from_config(cfg).get_current_head()
        if db_version != head:
            raise ConfigurationError(
                f"database is at migration {db_version!r} but code expects {head!r} — "
                "run `mip db upgrade` first"
            )
        return f"at head {head}"

    def _stage_market_date(
        self, session: Session, result: UpdateResult, as_of: date | None
    ) -> date:
        sessions = list(
            session.scalars(select(TradingDay.calendar_date).order_by(TradingDay.calendar_date))
        )
        resolved = resolve_market_date(
            sessions, self._now(), self._settings.market_close_buffer_minutes, as_of
        )
        result.stages["market_date"] = {
            "status": "success",
            "detail": {"resolved": resolved.isoformat(), "requested": result.requested_as_of},
        }
        logger.info("update.market_date", resolved=resolved.isoformat())
        return resolved

    def _execute_stages(
        self,
        result: UpdateResult,
        resolved: date,
        portfolio: str,
        selected: tuple[str, ...],
        skip: set[str],
        completed: set[str],
    ) -> None:
        runners: dict[str, Callable[[Session], dict]] = {
            "prices": lambda s: self._ingest(s, self._services.prices),
            "macro": lambda s: self._ingest(s, self._services.macro),
            "fundamentals": lambda s: self._ingest(s, self._services.fundamentals),
            "earnings": lambda s: self._ingest(s, self._services.earnings),
            "features": lambda s: self._features(s, resolved),
            "portfolio": lambda s: self._portfolio(s, portfolio),
            "assess": lambda s: self._assess(s, portfolio, resolved),
            "reports": lambda s: self._reports(s, portfolio, resolved, result),
            "archive": lambda s: self._archive(s, result),
            "evaluate": lambda s: self._evaluate(s, result),
        }
        needs_bundle = any(
            stage in selected and stage not in skip and stage not in completed
            for stage in ("reports", "archive")
        )
        for stage in STAGE_ORDER[2:]:
            if stage not in selected:
                result.stages[stage] = {
                    "status": "skipped",
                    "detail": {"reason": "outside stage window"},
                }
                continue
            if stage in skip:
                result.stages[stage] = {
                    "status": "skipped",
                    "detail": {"reason": "skipped by flag/config"},
                }
                continue
            if stage in completed and not (stage == "assess" and needs_bundle):
                original = self._resume_records.get(stage, {"detail": {}})
                result.stages[stage] = {
                    **original,
                    "status": "success",
                    "resumed": "completed in original run",
                }
                continue
            blocker = self._failed_dependency(result, stage)
            if blocker:
                result.stages[stage] = {
                    "status": "skipped",
                    "detail": {"reason": f"dependency {blocker!r} did not succeed"},
                }
                result.warnings.append(f"{stage}: skipped because {blocker} did not succeed")
                continue
            result.stages[stage] = self._run_stage(stage, runners[stage])

    def _failed_dependency(self, result: UpdateResult, stage: str) -> str | None:
        for dependency in DEPENDENCIES.get(stage, ()):
            status = result.stages.get(dependency, {}).get("status")
            if status not in ("success", "partial"):
                return dependency
        return None

    def _run_stage(self, name: str, fn: Callable[[Session], dict]) -> dict[str, Any]:
        from mip.core.db import session_scope

        attempts = 0
        started = time_module.monotonic()
        logger.info("update.stage_started", stage=name)
        while True:
            attempts += 1
            try:
                with session_scope(self._factory) as session:
                    detail = fn(session)
                record = {
                    "status": detail.pop("_status", "success"),
                    "seconds": round(time_module.monotonic() - started, 3),
                    "attempts": attempts,
                    "detail": detail,
                }
                logger.info("update.stage_done", stage=name, **{"status": record["status"]})
                return record
            except Exception as exc:  # noqa: BLE001 - stage isolation is the point
                if attempts <= self._settings.stage_retry_limit:
                    logger.warning("update.stage_retry", stage=name, error=str(exc))
                    continue
                logger.error("update.stage_failed", stage=name, error=str(exc))
                return {
                    "status": "failed",
                    "seconds": round(time_module.monotonic() - started, 3),
                    "attempts": attempts,
                    "detail": {},
                    "error": f"{type(exc).__name__}: {exc}"[:500],
                }

    def _record_failure(self, result: UpdateResult, stage: str, error: str) -> None:
        result.stages[stage] = {"status": "failed", "detail": {}, "error": error[:500]}
        result.warnings.append(f"{stage}: {error}")

    # -- stage bodies ----------------------------------------------------------

    def _ingest(self, session: Session, builder) -> dict:
        service = builder(session, self._settings)
        run, outcomes = service.ingest(None)
        failures = [
            getattr(o, "symbol", getattr(o, "code", "?"))
            for o in outcomes
            if getattr(o, "error", None)
        ]
        return {
            "_status": run.status.value if run.status != RunStatus.RUNNING else "success",
            "run_id": run.id,
            "rows_inserted": run.rows_inserted,
            "rows_updated": run.rows_updated,
            "failed": failures[:10],
        }

    def _features(self, session: Session, resolved: date) -> dict:
        from mip.features.pipeline import FeaturePipeline

        pipeline = FeaturePipeline(session=session, settings=self._settings, today=lambda: resolved)
        run, _ = pipeline.build(None)
        if run.status == RunStatus.FAILED:
            raise ConfigurationError("feature build failed")
        return {
            "_status": run.status.value,
            "run_id": run.id,
            "rows_inserted": run.rows_inserted,
            "rows_updated": run.rows_updated,
        }

    def _portfolio(self, session: Session, portfolio: str) -> dict:
        from mip.portfolio.lots import rebuild_lots
        from mip.portfolio.snapshots import SnapshotBuilder

        lots, closures = rebuild_lots(session, portfolio)
        changed = SnapshotBuilder(session).build(portfolio)
        return {"lots": lots, "closures": closures, "snapshot_rows_changed": changed}

    def _assess(self, session: Session, portfolio: str, resolved: date) -> dict:
        from mip.engine.attribution import AttributionEngine

        self._bundle = AttributionEngine(session).assessed(portfolio=portfolio, as_of=resolved)
        horizons = sum(len(pairs) for pairs in self._bundle.values())
        return {"symbols": len(self._bundle), "assessments": horizons}

    def _report_dir(self, resolved: date) -> Path:
        return Path(self._settings.report_root) / resolved.isoformat()

    def _reports(
        self, session: Session, portfolio: str, resolved: date, result: UpdateResult
    ) -> dict:
        from mip.engine.report import (
            build_portfolio_report,
            build_symbol_report,
            render_portfolio_markdown,
            render_symbol_markdown,
        )

        assert self._bundle is not None
        base = self._report_dir(resolved)
        (base / "portfolio").mkdir(parents=True, exist_ok=True)
        (base / "symbols").mkdir(parents=True, exist_ok=True)

        files = 0
        portfolio_report = build_portfolio_report(self._bundle, portfolio)
        stem = base / "portfolio" / portfolio.replace(" ", "_")
        stem.with_suffix(".md").write_text(render_portfolio_markdown(portfolio_report))
        stem.with_suffix(".json").write_text(json.dumps(portfolio_report.to_dict(), indent=2))
        files += 2
        for symbol, pairs in sorted(self._bundle.items()):
            report = build_symbol_report(pairs)
            symbol_stem = base / "symbols" / symbol
            symbol_stem.with_suffix(".md").write_text(render_symbol_markdown(report))
            symbol_stem.with_suffix(".json").write_text(json.dumps(report.to_dict(), indent=2))
            files += 2
        result.report_directory = str(base)
        return {"directory": str(base), "files": files}

    def _archive(self, session: Session, result: UpdateResult) -> dict:
        from mip.evaluation.archive import PredictionArchiver

        assert self._bundle is not None
        assessments = [a for pairs in self._bundle.values() for a, _ in pairs]
        archived = PredictionArchiver(session).archive(assessments)
        result.predictions_archived = archived.inserted
        return {"inserted": archived.inserted, "already_recorded": archived.skipped}

    def _evaluate(self, session: Session, result: UpdateResult) -> dict:
        from mip.evaluation.outcomes import OutcomeEvaluator

        summary = OutcomeEvaluator(session).evaluate_matured()
        result.outcomes_evaluated = summary.evaluated
        return summary.to_dict()

    # -- finalize ---------------------------------------------------------------

    def _finalize(self, result: UpdateResult) -> None:
        statuses = {name: record.get("status") for name, record in result.stages.items()}
        executed_failed = [n for n, s in statuses.items() if s == "failed"]
        if any(n in CRITICAL_STAGES for n in executed_failed):
            result.status = "failed"
        elif executed_failed or any(s == "partial" for s in statuses.values()):
            result.status = "partial"
        else:
            result.status = "success"
        result.completed_at = _utcnow()
        for name in executed_failed:
            error = result.stages[name].get("error", "")
            result.warnings.append(f"{name}: failed — {error}")
        if result.report_directory:
            manifest_path = Path(result.report_directory) / "run_manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(result.manifest(), indent=2))
        logger.info(
            "update.completed",
            run_id=result.run_id,
            status=result.status,
            resolved=result.resolved_market_date,
            predictions_archived=result.predictions_archived,
            outcomes_evaluated=result.outcomes_evaluated,
        )
