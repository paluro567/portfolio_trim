"""Shared ingestion-run orchestration: start run -> iterate items with
per-item failure isolation -> aggregate -> complete run.

Used by the Phase 4+ services. (The Phase 2/3 services predate this helper
and keep their own equivalent loops; unifying them is deliberate Phase 7
hardening, not something to churn while their gates are closed.)"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from mip.core.exceptions import MIPError
from mip.core.logging import get_logger
from mip.domain.enums import RunStatus, RunType
from mip.domain.models import IngestionRun
from mip.repositories.ingestion_runs import IngestionRunRepository

logger = get_logger(__name__)


@dataclass
class IngestOutcome:
    key: str  # symbol or series code
    status: str = "ok"  # 'ok' | 'failed'
    inserted: int = 0
    updated: int = 0
    quarantined: int = 0
    warnings: int = 0
    revisions: int = 0
    error: str | None = None


def run_ingestion[T](
    session: Session,
    run_type: RunType,
    provider_name: str,
    items: Iterable[tuple[str, T | None]],
    worker: Callable[[IngestionRun, str, T], IngestOutcome],
    archive_path: str,
    missing_error: str = "unknown symbol",
) -> tuple[IngestionRun, list[IngestOutcome]]:
    items = list(items)
    runs = IngestionRunRepository(session)
    run = runs.start(run_type, provider_name, ",".join(key for key, _ in items))
    logger.info("ingest.run_started", run_id=run.id, run_type=run_type.value, items=len(items))

    outcomes: list[IngestOutcome] = []
    for key, item in items:
        if item is None:
            outcomes.append(IngestOutcome(key=key, status="failed", error=missing_error))
            continue
        try:
            outcomes.append(worker(run, key, item))
        except MIPError as exc:
            logger.error(
                "ingest.item_failed",
                run_id=run.id,
                run_type=run_type.value,
                key=key,
                error=str(exc),
            )
            outcomes.append(IngestOutcome(key=key, status="failed", error=str(exc)))

    failed = {o.key: o.error for o in outcomes if o.status == "failed"}
    if not outcomes or len(failed) == len(outcomes):
        status = RunStatus.FAILED
    elif failed:
        status = RunStatus.PARTIAL
    else:
        status = RunStatus.SUCCESS

    runs.complete(
        run,
        status=status,
        rows_inserted=sum(o.inserted for o in outcomes),
        rows_updated=sum(o.updated for o in outcomes),
        archive_path=archive_path,
        error_detail={"failed": failed} if failed else None,
    )
    logger.info(
        "ingest.run_completed",
        run_id=run.id,
        run_type=run_type.value,
        status=status.value,
        inserted=run.rows_inserted,
        updated=run.rows_updated,
        failed=len(failed),
    )
    return run, outcomes
