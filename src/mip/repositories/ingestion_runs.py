"""Repository for ingestion_runs — the audit spine (D7)."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mip.domain.enums import RunStatus, RunType
from mip.domain.models import IngestionRun


class IngestionRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def start(self, run_type: RunType, provider: str, scope: str | None) -> IngestionRun:
        run = IngestionRun(run_type=run_type, provider=provider, scope=scope)
        self._session.add(run)
        self._session.flush()  # id needed for lineage FKs immediately
        return run

    def complete(
        self,
        run: IngestionRun,
        status: RunStatus,
        rows_inserted: int,
        rows_updated: int,
        archive_path: str | None = None,
        error_detail: dict[str, Any] | None = None,
    ) -> None:
        run.status = status
        run.rows_inserted = rows_inserted
        run.rows_updated = rows_updated
        run.archive_path = archive_path
        run.error_detail = error_detail
        run.completed_at = func.now()
        self._session.flush()

    def recent(self, limit: int = 20) -> list[IngestionRun]:
        return list(
            self._session.scalars(
                select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(limit)
            )
        )
